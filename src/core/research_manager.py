"""
Research Manager Module

This module contains the ResearchManager class which orchestrates the entire research process.
It manages the interaction between different components of the system, including data collection,
AI model interaction, and report generation.

The research process includes:
1. Pre-research data collection
2. Initial discussion to determine research strategy
3. Detailed data collection based on the strategy
4. Report generation from collected data
"""

from typing import Dict, List, Tuple
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
)


class ResearchManager:
    def __init__(self, logger):
        """
        研究マネージャーの初期化

        Args:
            logger: ロガーインスタンス
        """
        self.logger = logger
        self.model = BedrockModel(logger)
        self.tool_handler = ToolHandler(logger)
        self.data_collector = DataCollector(self.model, self.tool_handler, logger)
        self.report_builder = ReportBuilder(self.model, logger)
        self.conversation = {'A': [], 'I': [], 'F': []}
        self.source_manager = SourceReferenceManager()
        self.mode = "standard"  # デフォルトは標準モード

    def execute_research(self, user_prompt: str, mode: str = "standard") -> Tuple[str, str]:
        """
        研究プロセスの実行

        Args:
            user_prompt: ユーザーの研究テーマ
            mode: 研究モード ("standard" または "summary")

        Returns:
            Tuple[str, str]: 生成されたHTMLとMarkdownレポートのパス

        Raises:
            ResearchError: 研究プロセス中のエラー
        """
        try:
            self.mode = mode.lower()
            if self.mode not in ["standard", "summary"]:
                self.mode = "standard"  # 不明なモードの場合はデフォルトに設定
                
            self.logger.section(f"リサーチ開始: {user_prompt} (モード: {self.mode})")

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
            )

            # レポート保存
            return self.report_builder.save_report(
                final_report,
                f"調査レポート: {user_prompt}",
            )

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
2. 関連する用語や関連するコンテキスト
3. 用語に関連する最新の動向や傾向や話題
4. 用語に関連する最新の研究や、最新のニュース
5. 用語に関連する事例

Web検索とコンテンツ取得を使用して、これらの情報を収集してください。
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
