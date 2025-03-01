"""
Research Manager Module

This module contains the ResearchManager class which orchestrates the entire research process.
It manages the interaction between different components of the system, including data collection,
AI model interaction, and report generation.

The research process includes:
1. Pre-research data collection
2. Initial discussion to determine research strategy
3. Detailed data collection based on the strategy
4. Report preparation to create visualizations from collected data
5. Report generation from collected data
"""

from typing import Dict, List, Tuple, Any, Optional
import json
import re
from ..models.bedrock import BedrockModel
from ..models.source_reference import SourceReferenceManager
from ..utils.tool_handler import ToolHandler
from ..utils.exceptions import ResearchError
from ..core.data_collector import DataCollector
from ..core.report_builder import ReportBuilder
from ..config.settings import (
    MODEL_CONFIG,
    PRIMARY_MODEL,
    SECONDARY_MODEL,
    MAX_CONVERSATION_TURNS,
    SUMMARY_CONVERSATION_TURNS,
    MAX_PRE_RESEARCH_SEARCHES,
    SUMMARY_PRE_RESEARCH_SEARCHES,
    TOOL_CONFIG,
)


class ResearchManager:
    def __init__(self, logger, base_filename):
        """
        研究マネージャーの初期化

        Args:
            logger: ロガーインスタンス
        """
        self.logger = logger
        self.model = BedrockModel(logger)
        self.tool_handler = ToolHandler(logger,base_filename)
        self.data_collector = DataCollector(self.model, self.tool_handler, logger)
        self.report_builder = ReportBuilder(self.model, logger, base_filename)
        self.conversation = {'A': [], 'I': [], 'F': []}
        self.source_manager = SourceReferenceManager()
        self.mode = "standard"  # デフォルトは標準モード
        self.current_image_dir = None
        self.basefilename = base_filename

    def execute_research(self, user_prompt: str, mode: str = "standard") -> Tuple[str, str, str]:
        """
        研究プロセスの実行

        Args:
            user_prompt: ユーザーの研究テーマ
            mode: 研究モード ("standard" または "summary")

        Returns:
            Tuple[str, str, str]: 生成されたHTML、Markdown、PDFレポートのパス

        Raises:
            ResearchError: 研究プロセス中のエラー
        """
        try:
            self.mode = mode.lower()
            if self.mode not in ["standard", "summary"]:
                self.mode = "standard"  # 不明なモードの場合はデフォルトに設定
                
            self.logger.section(f"リサーチ開始: {user_prompt} (モード: {self.mode})")

            # 画像ディレクトリを取得して設定
            # レポートのファイル名から画像ディレクトリ名を取得（拡張子を除く）
            # DataCollectorに画像ディレクトリを設定
            self.data_collector.set_image_directory(f"{self.basefilename}_images")

            # 事前調査
            pre_research_data = self._conduct_pre_research(user_prompt)

            # 初期討議
            strategy_text = self._conduct_initial_discussion(
                user_prompt, pre_research_data
            )

            # データ収集
            collected_data, source_manager = self.data_collector.collect_research_data(
                self.conversation,
                strategy_text,
                user_prompt,
                self.mode,
            )
            self.source_manager = source_manager

            # レポート事前準備（データの可視化）
            visualization_data = self._prepare_report_visualizations(
                collected_data,
                user_prompt,
                strategy_text
            )

            # 収集データの整理
            research_text = self._extract_conversation_text()
            self._log_research_summary(research_text)

            # レポート生成
            final_report = self.report_builder.generate_final_report(
                research_text,
                strategy_text,
                user_prompt,
                self.source_manager,
                self.mode,
                visualization_data,
            )

            # レポート保存
            html_path, md_path, pdf_path = self.report_builder.save_report(
                final_report,
                f"調査レポート: {user_prompt}",
            )
            
            return html_path, md_path, pdf_path

        except Exception as e:
            raise ResearchError(f"Error during research process: {str(e)}")

    def _conduct_pre_research(self, user_prompt: str) -> str:
        """
        事前調査の実行

        Args:
            user_prompt: ユーザーの研究テーマ

        Returns:
            str: 事前調査で収集したデータ
        """
        self.logger.section("事前調査フェーズ")
        self.logger.log("目的: コンテキスト情報の収集")

        pre_research_prompt = self._create_pre_research_prompt(user_prompt)
        self.conversation['F'] = []
        self.conversation['F'].append(
            {"role": "user", "content": [{"text": pre_research_prompt}]}
        )

        # モードに応じた最大検索回数を設定
        max_searches = SUMMARY_PRE_RESEARCH_SEARCHES if self.mode == "summary" else MAX_PRE_RESEARCH_SEARCHES
        
        collected_data, source_manager = self.data_collector.collect_research_data(
            self.conversation,
            pre_research_prompt,
            user_prompt,
            self.mode,
            max_searches,
        )
        self.source_manager = source_manager

        result = "\n\n".join(collected_data)
        self.logger.log("事前調査結果のサマリー:")
        summary = result[:500] + "..." if len(result) > 500 else result
        self.logger.log(summary)

        return result

    def _conduct_initial_discussion(
        self, user_prompt: str, pre_research_data: str
    ) -> str:
        """
        初期討議の実行

        Args:
            user_prompt: ユーザーの研究テーマ
            pre_research_data: 事前調査で収集したデータ

        Returns:
            str: 生成された調査戦略テキスト
        """
        self.logger.section("初期討議フェーズ")
        self.logger.log("目的: 調査方針の検討と決定")

        self._initialize_conversation(user_prompt, pre_research_data)
        qualification_prompt = self._create_qualification_prompt(
            user_prompt, pre_research_data
        )
        
        # モードに応じた最大会話ターン数を設定
        max_turns = SUMMARY_CONVERSATION_TURNS if self.mode == "summary" else MAX_CONVERSATION_TURNS
        self._conduct_conversation(qualification_prompt, max_turns)

        strategy_prompt = self._create_strategy_prompt(user_prompt)
        strategy_response = self.model.generate_response(
            MODEL_CONFIG[PRIMARY_MODEL],
            self.conversation['A'],
            strategy_prompt,
            {'temperature': 0},
        )

        strategy_text = strategy_response['output']['message']['content'][0]['text']
        self.logger.log("調査戦略:")
        self.logger.log(strategy_text)

        return strategy_text

    def _prepare_report_visualizations(
        self, collected_data: List[str], user_prompt: str, strategy_text: str
    ) -> Dict[str, Any]:
        """
        レポート事前準備フェーズ - データの可視化

        収集したデータから表やグラフを作成し、視覚的な情報を準備します。

        Args:
            collected_data: 収集したデータのリスト
            user_prompt: ユーザーの研究テーマ
            strategy_text: 調査戦略テキスト

        Returns:
            Dict[str, Any]: 作成した視覚化データ（グラフパスなど）
        """
        self.logger.section("レポート事前準備フェーズ")
        self.logger.log("目的: データの可視化と視覚的情報の準備")

        visualization_data = {
            'graphs': [],
            'tables': [],
        }

        # 収集したデータを結合
        combined_data = "\n\n".join(collected_data)

        # 数値データの抽出とグラフ化のためのプロンプト
        visualization_prompt = self._create_visualization_prompt(user_prompt, strategy_text, combined_data)
        
        # 会話履歴の初期化
        visualization_conversation = []
        visualization_conversation.append(
            {"role": "user", "content": [{"text": visualization_prompt}]}
        )

        # AIモデルに視覚化の指示を出す
        response = self.model.generate_response(
            MODEL_CONFIG[PRIMARY_MODEL],
            visualization_conversation,
            [{"text": "あなたは優秀なデータ分析者です。収集したデータから視覚的な情報を作成してください。"}],
            {'temperature': 0},
            TOOL_CONFIG,
        )

        # AIの思考プロセスを出力
        self.logger.log("AI の視覚化計画:")
        for content in response['output']['message']['content']:
            if 'text' in content:
                self.logger.log(content['text'])
        self.logger.log("")

        # ツール使用の処理
        tool_use = self.tool_handler.process_tool_response(response)
        
        # ツール使用がない場合は終了
        if not tool_use:
            self.logger.log("視覚化のためのツール使用なし")
            return visualization_data

        # アシスタントメッセージを追加
        visualization_conversation.append(
            {
                'role': 'assistant',
                'content': response['output']['message']['content'],
            }
        )

        # グラフ生成ツールの使用を処理
        if tool_use['name'] == 'generate_graph':
            result = self.tool_handler.generate_graph(**tool_use['input'])
            
            try:
                result_data = json.loads(result)
                if 'graph_path' in result_data:
                    self.logger.log(f"グラフを生成しました: {result_data['graph_path']}")
                    visualization_data['graphs'].append(result_data)
            except:
                self.logger.log("グラフ生成結果の解析に失敗しました")
                
            # ツール結果を追加
            visualization_conversation.append(
                {
                    'role': 'user',
                    'content': [
                        {
                            'toolResult': {
                                'toolUseId': tool_use['toolUseId'],
                                'content': [{'text': result}],
                            }
                        }
                    ],
                }
            )
            
            # 追加のグラフ生成を試みる
            for _ in range(2):  # 最大2回の追加グラフ生成を試みる
                response = self.model.generate_response(
                    MODEL_CONFIG[PRIMARY_MODEL],
                    visualization_conversation,
                    [{"text": "他にも視覚化できるデータがあれば、グラフを生成してください。"}],
                    {'temperature': 0},
                    TOOL_CONFIG,
                )
                
                tool_use = self.tool_handler.process_tool_response(response)
                if not tool_use or tool_use['name'] != 'generate_graph':
                    break
                    
                visualization_conversation.append(
                    {
                        'role': 'assistant',
                        'content': response['output']['message']['content'],
                    }
                )
                
                result = self.tool_handler.generate_graph(**tool_use['input'])
                
                try:
                    result_data = json.loads(result)
                    if 'graph_path' in result_data:
                        self.logger.log(f"追加のグラフを生成しました: {result_data['graph_path']}")
                        visualization_data['graphs'].append(result_data)
                except:
                    self.logger.log("追加のグラフ生成結果の解析に失敗しました")
                    
                visualization_conversation.append(
                    {
                        'role': 'user',
                        'content': [
                            {
                                'toolResult': {
                                    'toolUseId': tool_use['toolUseId'],
                                    'content': [{'text': result}],
                                }
                            }
                        ],
                    }
                )

        # 表データの抽出
        tables = self._extract_tables_from_data(combined_data)
        if tables:
            visualization_data['tables'] = tables
            self.logger.log(f"{len(tables)} 個の表データを抽出しました")

        self.logger.log(f"視覚化データの準備完了: グラフ {len(visualization_data['graphs'])} 個, 表 {len(visualization_data['tables'])} 個")
        return visualization_data

    def _extract_tables_from_data(self, data: str) -> List[Dict[str, Any]]:
        """
        データから表を抽出

        Args:
            data: 収集したデータテキスト

        Returns:
            List[Dict[str, Any]]: 抽出した表データのリスト
        """
        tables = []
        
        # マークダウン形式の表を検出
        markdown_tables = re.findall(r'(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n)+)', data)
        
        for i, table in enumerate(markdown_tables):
            tables.append({
                'type': 'markdown',
                'content': table,
                'id': f'table_{i+1}'
            })
            
        return tables

    def _create_visualization_prompt(self, user_prompt: str, strategy_text: str, data: str) -> str:
        """
        視覚化プロンプトの作成

        Args:
            user_prompt: ユーザーの研究テーマ
            strategy_text: 調査戦略テキスト
            data: 収集したデータ

        Returns:
            str: 視覚化プロンプト
        """
        return f'''あなたは優秀なデータ分析者です。
「{user_prompt}」に関する調査データから、視覚的な情報を作成してください。

調査戦略:
{strategy_text}

収集したデータ:
{data[:10000]}  # データが長い場合は一部を使用

以下の点に注意してください:
1. 収集したデータから数値データを見つけ、グラフ化できるものを特定してください
2. 表形式のデータがあれば、それをグラフに変換することを検討してください
3. 時系列データ、比較データ、割合データなど、グラフ化に適したデータを探してください
4. generate_graphツールを使用して、適切なグラフ（棒グラフ、折れ線グラフ、円グラフなど）を作成してください
5. グラフのタイトル、軸ラベル、凡例などを適切に設定してください
6. 作成したグラフは最終レポートで使用されます

データを分析し、グラフ化できるデータがあれば、generate_graphツールを使用してグラフを作成してください。
グラフ化できるデータがない場合は、その旨を説明してください。
'''

    def _initialize_conversation(self, user_prompt: str, pre_research_data: str):
        """会話の初期化"""
        self.conversation['A'] = [
            {
                "role": "user",
                "content": [
                    {
                        "text": f'「{user_prompt}」について、以下の事前調査結果をもとに検討しましょう：\n\n事前に収集した調査結果はこちらです：{pre_research_data}'
                    }
                ],
            }
        ]
        self.conversation['I'] = []

    def _conduct_conversation(self, system_prompt: List[Dict], max_turns: int):
        """AIモデル間の会話を実行"""
        for turn in range(max_turns):
            self.logger.subsection(f"討議ターン {turn + 1}")

            # Primary AIの応答
            primary_response = self._get_model_response(
                PRIMARY_MODEL, self.conversation['A'], system_prompt
            )
            self._update_conversation(primary_response, 'A', 'I')

            # Secondary AIの応答
            secondary_response = self._get_model_response(
                SECONDARY_MODEL, self.conversation['I'], system_prompt
            )
            self._update_conversation(secondary_response, 'I', 'A')

    def _get_model_response(
        self, model_name: str, messages: List[Dict], system_prompt: List[Dict]
    ) -> str:
        """モデルからのレスポンスを取得"""
        self.logger.log(f"=== {model_name} の発言 ===")
        response = self.model.generate_response(
            MODEL_CONFIG[model_name],
            messages,
            system_prompt,
            {'temperature': 1},
        )
        response_text = response['output']['message']['content'][0]['text']
        self.logger.log(response_text)
        return response_text

    def _update_conversation(self, response: str, current_model: str, next_model: str):
        """会話履歴の更新"""
        self.conversation[current_model].append(
            {"role": "assistant", "content": [{"text": response}]}
        )
        self.conversation[next_model].append(
            {"role": "user", "content": [{"text": response}]}
        )

    def _create_pre_research_prompt(self, user_prompt: str) -> str:
        """事前調査プロンプトの作成"""
        return f'''あなたは優秀なリサーチャーです。
「{user_prompt}」について、コンテキストがわからない用語も含めてキーワードに分割した上で、以下の点を明らかにするための情報を収集してください：

1. 主要な概念や用語の定義
2. 最新のニュースや画像
3. 関連する用語や関連するコンテキスト
4. 用語に関連する最新の動向や傾向や話題
5. 用語に関連する最新の研究
6. データポイント
7. 用語に関連する事例

Web検索とコンテンツ取得と画像取得ツールを使用して、これらの情報を収集してください。
数値データからグラフ画像を作成することもできるので、生の数値データが取れそうななども確認してください。
数値データが取得できた場合は、グラフ生成ツールで作成した画像を使用して視覚的に表現することも検討してください。
必ず1つ以上の画像を取得するようにしてください。
'''

    def _create_qualification_prompt(
        self, user_prompt: str, pre_research_prompt: str
    ) -> List[Dict]:
        """資格確認プロンプトの作成"""
        # モードに応じた最大会話ターン数を設定
        max_turns = SUMMARY_CONVERSATION_TURNS if self.mode == "summary" else MAX_CONVERSATION_TURNS
        
        return [
            {
                'text': f'''あなたは優秀なリサーチャーです。
会話相手はあなたと同じ {user_prompt} という調査依頼を受けとった同僚の AI さんです。

事前の調査内容として {pre_research_prompt} が与えられています。
調査内容はキーワードや意味の列挙なので、調査の粒度や観点などは仮説を持って調査をした後調査結果を作成し、調査結果のフィードバックをもらうことでしか改善できません。
AI さんはあなたの思考の枠を外して広い視野を提供してくれます。
あなたも調査内容を自由に広げて網羅性を高め、その後どんなことを調べるのかを深めていってください。
特に反対意見は大事です。お互いの網羅性や深さの不足を指摘しながらAI さんとの会話を重ね、リサーチする内容を決めていってください。
会話はお互い {max_turns} 回までしかできないので、それまでに議論をまとめてください。
ただし会話は以下の内容をまとめてください。

* 具体的にどんなことをするのか actionable にまとめる必要があります。
* 予算や人員については触れてはいけません。調査する内容にだけフォーカスしてください。
* 調査対象に関わるだろう人の観点を複数入れてください。例えば料理であれば、調理器具をつくる人、食材を運ぶ人、料理を作る人、料理を運ぶ人、食べる人、口コミを書く人などです。与えられたお題に反しない限り様々な人に思いを巡らせてください。
* 会話を始める前に、自分がどのように考えたのか、を述べてから結論を述べてください。
* さまざまな観点から内容をブラッシュアップしてください。
* 事前調査に基づき、画像取得や作成したグラフ画像などの視覚的な情報をできるだけ活用することを検討してください。

また、発言する際は最初に必ず x 回目の発言です、と言ってください。発言回数は自分の発言回数であり、相手の発言はカウントしてはいけません。
'''
            }
        ]

    def _create_strategy_prompt(self, user_prompt: str) -> List[Dict]:
        """戦略プロンプトの作成"""
        return [
            {
                'text': f'''あなたは優秀なリサーチャーです。
あなたは「{user_prompt}」 という調査依頼を受けとっています。
調査内容は雑なので、調査の粒度や観点などは仮説を持って調査をした後調査結果を作成し、調査結果のフィードバックをもらうことでしか改善できません。
どのように調査を進めるかの方針をまとめた会話を渡します。
調査の方針をまとめてください。
ただし出力する内容は調査の方針だけで、会話を続ける必要はありません。

調査の方針には、以下の点も含めてください：
1. どのような情報（テキスト・画像・生データ）を収集するか
2. どのようなツール（Web検索、コンテンツ取得、画像検索と画像取得、グラフ画像作成など）を使用するか
3. 収集した情報をどのように整理・分析するか。必要に応じて、あるいはグラフ画像を作成が有効か
4. 最終的なレポートにどのような視覚的要素（画像取得ツールでダウンロードした画像、グラフ画像作成ツールで生成した画像）を含めるか
'''
            }
        ]

    def _extract_conversation_text(self) -> str:
        """会話履歴からテキストを抽出"""
        extracted_text = ""
        for c in self.conversation['F']:
            if 'content' in c:
                for item in c['content']:
                    if 'text' in item:
                        extracted_text += item['text'] + "\n\n"
                    elif 'toolResult' in item and 'content' in item['toolResult']:
                        for content_item in item['toolResult']['content']:
                            if 'text' in content_item:
                                extracted_text += content_item['text'] + "\n\n"
        return extracted_text

    def _log_research_summary(self, research_text: str):
        """研究サマリーのログ出力"""
        self.logger.section("収集データの整理")
        self.logger.log("収集データのサマリー:")
        summary = (
            research_text[:500] + "..." if len(research_text) > 500 else research_text
        )
        self.logger.log(summary)
