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
        self.tool_handler = ToolHandler(logger, base_filename)
        self.data_collector = DataCollector(self.model, self.tool_handler, logger)
        self.report_builder = ReportBuilder(self.model, logger, base_filename)
        self.conversation = {"A": [], "I": [], "F": []}
        self.source_manager = SourceReferenceManager()
        self.mode = "standard"  # デフォルトは標準モード
        self.current_image_dir = None
        self.basefilename = base_filename

    def execute_research(
        self, user_prompt: str, mode: str = "standard"
    ) -> Tuple[str, str, str]:
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
                collected_data, user_prompt, strategy_text
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
        self.conversation["F"] = []
        self.conversation["F"].append(
            {"role": "user", "content": [{"text": pre_research_prompt}]}
        )

        # モードに応じた最大検索回数を設定
        max_searches = (
            SUMMARY_PRE_RESEARCH_SEARCHES
            if self.mode == "summary"
            else MAX_PRE_RESEARCH_SEARCHES
        )

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
        qualification_prompt = self._create_qualification_prompt()

        # モードに応じた最大会話ターン数を設定
        max_turns = (
            SUMMARY_CONVERSATION_TURNS
            if self.mode == "summary"
            else MAX_CONVERSATION_TURNS
        )
        self._conduct_conversation(qualification_prompt, max_turns)

        strategy_prompt = self._create_strategy_prompt(user_prompt)
        strategy_response = self.model.generate_response(
            MODEL_CONFIG[PRIMARY_MODEL],
            self.conversation["A"],
            strategy_prompt,
            {"temperature": 0},
        )

        strategy_text = strategy_response["output"]["message"]["content"][0]["text"]
        self.logger.log("調査戦略:")
        self.logger.log(strategy_text)

        return strategy_text

    def _prepare_report_visualizations(
        self, collected_data: List[str], user_prompt: str, strategy_text: str
    ) -> Dict[str, Any]:
        """
        レポート事前準備フェーズ - データの可視化

        収集したデータから表やグラフを作成し、視覚的な情報を準備します。
        改善版では、より意味のあるグラフ作成とmermaid図の活用を強化しています。

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
            "graphs": [],
            "tables": [],
            "mermaid_diagrams": [],
            "images_with_context": [],  # 画像とその文脈情報を保存する新しいフィールド
        }

        # 収集したデータを結合
        combined_data = "\n\n".join(collected_data)

        # 画像の文脈情報を抽出
        self._extract_image_context(collected_data, visualization_data)

        # Mermaid図の抽出とレンダリング
        # 調査戦略からMermaid図を抽出
        strategy_diagrams = self.tool_handler.extract_mermaid_diagrams(strategy_text)
        if strategy_diagrams:
            self.logger.log(
                f"調査戦略から {len(strategy_diagrams)} 個のMermaid図を抽出しました"
            )

            for title, mermaid_code in strategy_diagrams:
                result = self.tool_handler.render_mermaid(mermaid_code, title)

                try:
                    result_data = json.loads(result)
                    if "mermaid_path" in result_data:
                        self.logger.log(
                            f"Mermaid図をレンダリングしました: {result_data['mermaid_path']}"
                        )
                        visualization_data["mermaid_diagrams"].append(result_data)
                except:
                    self.logger.log("Mermaid図のレンダリング結果の解析に失敗しました")

        # 収集データからMermaid図を抽出
        for data_item in collected_data:
            diagrams = self.tool_handler.extract_mermaid_diagrams(data_item)
            if diagrams:
                self.logger.log(
                    f"収集データから {len(diagrams)} 個のMermaid図を抽出しました"
                )

                for title, mermaid_code in diagrams:
                    result = self.tool_handler.render_mermaid(mermaid_code, title)

                    try:
                        result_data = json.loads(result)
                        if "mermaid_path" in result_data:
                            self.logger.log(
                                f"Mermaid図をレンダリングしました: {result_data['mermaid_path']}"
                            )
                            visualization_data["mermaid_diagrams"].append(result_data)
                    except:
                        self.logger.log(
                            "Mermaid図のレンダリング結果の解析に失敗しました"
                        )

        # LLMとの対話を通じて視覚化の計画を立てる
        visualization_plan = self._create_visualization_plan(
            user_prompt, strategy_text, combined_data
        )

        # 視覚化計画に基づいてグラフとMermaid図を生成
        try:
            self._generate_visualizations_from_plan(
                visualization_plan, visualization_data, combined_data
            )
        except Exception as e:
            self.logger.log(f"視覚化計画からの生成中にエラーが発生しました: {str(e)}")
            # エラーが発生しても処理を続行

        # 数値データの抽出とグラフ化のためのプロンプト
        visualization_prompt = self._create_visualization_prompt(
            user_prompt, strategy_text, combined_data
        )

        # 会話履歴の初期化
        visualization_conversation = []
        visualization_conversation.append(
            {"role": "user", "content": [{"text": visualization_prompt}]}
        )

        # AIモデルに視覚化の指示を出す
        response = self.model.generate_response(
            MODEL_CONFIG[PRIMARY_MODEL],
            visualization_conversation,
            [
                {
                    "text": """あなたは優秀なデータ可視化の専門家です。
ユーザーは <title> タグに関する調査データと、<strategy> タグで調査戦略、<data> タグで収集したデータの一部を与えます。
効果的な視覚化計画を立ててください。
ただし <consideration> タグで与える点を考慮した上で、視覚化計画を立ててください。特に <contemplation> タグで与える視覚化タイプを検討してください。
<consideration>
- どのような種類のデータが視覚化に適しているか（定量的データ、定性的データ、比較データ、時系列データなど）
- 最も効果的な視覚化の種類（グラフ、チャート、図表、フロー図など）
- 各視覚化の目的と意図（何を伝えたいのか）
- 視覚化に必要なデータ要素
</consideration>
<contemplation>
- 時系列データの推移を示す折れ線グラフ
- 比較データを示す棒グラフ
- 割合を示す円グラフ
- プロセスや関係性を示すフロー図（mermaid）
- 概念や構造を示す図表（mermaid）
- 分類や階層を示すマインドマップ（mermaid）
</contemplation>

<mermaid> で与える Mermaid に関する利用ルールに注意を払ってください。
<mermaid>
Mermaid は様々なグラフやチャートの出力形式に対応したフォーマットです。

#Mermaid出力形式・図表タイプのガイドとgraph_type

##適切な図表タイプの選び方と各タイプの正確な宣言方法

###プロセスとフロー
フローチャート：意思決定や処理の流れを示す
graph TD  // または LR, TB, RL, BT
,
シーケンス図：時間順の相互作用やメッセージのやり取りを示す
sequenceDiagram
,
状態図：システムの状態遷移を示す
stateDiagram-v2

###関係性とデータモデル

クラス図：オブジェクト指向設計やデータモデルを示す
classDiagram
,
ER図：データベースのエンティティと関係を示す
erDiagram
,
C4コンテキスト図：システムアーキテクチャを示す
C4Context

###計画と進捗

ガントチャート：プロジェクトのタイムラインと進捗を示す
gantt
,
カンバンボード：タスクの状態と進行状況を示す
kanban

###データ分析と比較

円グラフ：全体に対する割合を示す
pie
,
象限チャート：2つの軸による分類を示す
quadrantChart
,
XYチャート：数値データの関係や傾向を示す
xychart-beta
,
サンキー図：フローの量や変換を示す
sankey-beta

###概念と構造
マインドマップ：アイデアや概念の階層関係を示す
mindmap
,
タイムライン：時系列の出来事を示す
timeline
,
ブロック図：システムコンポーネントの構造を示す
block-beta

###技術的図表
Gitグラフ：バージョン管理の履歴とブランチを示す
gitGraph
,
パケット図：データ構造やプロトコルを示す
packet-beta
,
アーキテクチャ図：システムの構成要素と関係を示す
architecture-beta
,
要件図：システム要件と関係を示す
requirementDiagram
,
ZenUML：シーケンス図の代替表現
zenuml
</mermaid>

出力は JSON で </rule> で与えるルールを遵守してください。
<rule>
"type"："graph","mermaid"のどちらかを選択してください。
"graph_type": typeがgraphの場合は matplotlib のグラフタイプを、type が mermaid の場合は、上記の Mermaid 用の graph_type をいれてください。

JSON形式で視覚化計画を出力してください。以下は出力形式の例です:
'''json
{
    "visualizations": [
        {
            "type": "graph",
            "graph_type": "line",
            "title": "年間売上推移",
            "purpose": "過去5年間の売上傾向を示す",
            "data_needed": "年度と売上額のデータ",
            "x_label": "年度",
            "y_label": "売上額（百万円）"
        },
        {
            "type": "mermaid",
            "diagram_type": "flowchart",
            "title": "製品開発プロセス",
            "purpose": "製品開発の各段階と関係者を示す",
            "description": "企画から販売までのプロセスフロー"
        }
    ]
}
'''
</rule>
上記の出力フォーマット以外の出力だけしてください。
視覚化計画を作成してください。
"""
                }
            ],
            {"temperature": 0},
            TOOL_CONFIG,
        )

        # AIの思考プロセスを出力
        self.logger.log("AI の視覚化計画:")
        for content in response["output"]["message"]["content"]:
            if "text" in content:
                self.logger.log(content["text"])
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
                "role": "assistant",
                "content": response["output"]["message"]["content"],
            }
        )

        # グラフ生成ツールの使用を処理
        if tool_use["name"] == "generate_graph":
            result = self.tool_handler.generate_graph(**tool_use["input"])

            try:
                result_data = json.loads(result)
                if "graph_path" in result_data:
                    self.logger.log(
                        f"グラフを生成しました: {result_data['graph_path']}"
                    )
                    visualization_data["graphs"].append(result_data)
            except:
                self.logger.log("グラフ生成結果の解析に失敗しました")

            # ツール結果を追加
            visualization_conversation.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": tool_use["toolUseId"],
                                "content": [{"text": result}],
                            }
                        }
                    ],
                }
            )

            # 追加のグラフ生成を試みる
            for _ in range(3):  # 最大3回の追加グラフ生成を試みる（元の2回から増加）
                response = self.model.generate_response(
                    MODEL_CONFIG[PRIMARY_MODEL],
                    visualization_conversation,
                    [
                        {
                            "text": "他にも視覚化できるデータがあれば、グラフを生成してください。特に時系列データ、比較データ、割合データなど、グラフ化に適したデータを探してください。"
                        }
                    ],
                    {"temperature": 0},
                    TOOL_CONFIG,
                )

                tool_use = self.tool_handler.process_tool_response(response)
                if not tool_use or tool_use["name"] != "generate_graph":
                    break

                visualization_conversation.append(
                    {
                        "role": "assistant",
                        "content": response["output"]["message"]["content"],
                    }
                )

                result = self.tool_handler.generate_graph(**tool_use["input"])

                try:
                    result_data = json.loads(result)
                    if "graph_path" in result_data:
                        self.logger.log(
                            f"追加のグラフを生成しました: {result_data['graph_path']}"
                        )
                        visualization_data["graphs"].append(result_data)
                except:
                    self.logger.log("追加のグラフ生成結果の解析に失敗しました")

                visualization_conversation.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "toolResult": {
                                    "toolUseId": tool_use["toolUseId"],
                                    "content": [{"text": result}],
                                }
                            }
                        ],
                    }
                )

        # 表データの抽出
        tables = self._extract_tables_from_data(combined_data)
        if tables:
            visualization_data["tables"] = tables
            self.logger.log(f"{len(tables)} 個の表データを抽出しました")

        self.logger.log(
            f"視覚化データの準備完了: グラフ {len(visualization_data['graphs'])} 個, 表 {len(visualization_data['tables'])} 個, Mermaid図 {len(visualization_data['mermaid_diagrams'])} 個, 文脈付き画像 {len(visualization_data['images_with_context'])} 個"
        )
        return visualization_data

    def _extract_image_context(
        self, collected_data: List[str], visualization_data: Dict[str, Any]
    ) -> None:
        """
        収集したデータから画像とその文脈情報を抽出

        Args:
            collected_data: 収集したデータのリスト
            visualization_data: 視覚化データ辞書（更新される）
        """
        for data_item in collected_data:
            # 画像パスを検索
            image_paths = re.findall(
                r"([^/\s]+_images/[^)\s]+\.(png|jpg|jpeg|gif))", data_item
            )

            for img_path_tuple in image_paths:
                img_path = img_path_tuple[0]

                # 画像の前後のテキストを抽出（コンテキスト）
                # 画像パスの前後約200文字を取得
                img_index = data_item.find(img_path)
                if img_index >= 0:
                    start_index = max(0, img_index - 200)
                    end_index = min(len(data_item), img_index + len(img_path) + 200)
                    context = data_item[start_index:end_index]

                    # 画像の説明を抽出（キャプションらしき部分）
                    caption = ""
                    caption_match = re.search(
                        r"(?:図|画像|イメージ|Figure)[:：]?\s*([^\n.。]+)[.。]?",
                        context,
                    )
                    if caption_match:
                        caption = caption_match.group(1).strip()

                    # 画像と文脈情報を保存
                    visualization_data["images_with_context"].append(
                        {"path": img_path, "context": context, "caption": caption}
                    )

                    self.logger.log(f"画像の文脈情報を抽出しました: {img_path}")

    def _create_visualization_plan(
        self, user_prompt: str, strategy_text: str, data: str
    ) -> Dict[str, Any]:
        """
        視覚化計画を作成するためにLLMと対話

        Args:
            user_prompt: ユーザーの研究テーマ
            strategy_text: 調査戦略テキスト
            data: 収集したデータ

        Returns:
            Dict[str, Any]: 視覚化計画
        """
        self.logger.log("視覚化計画の作成を開始します")

        # 視覚化計画作成のためのプロンプト
        planning_prompt = f"""<title>
{user_prompt}
</title>
<strategy>
{strategy_text[:1000]}
</strategy>
<data>
{data[:5000]}
</data>"""

        # 会話履歴の初期化
        planning_conversation = []
        planning_conversation.append(
            {"role": "user", "content": [{"text": planning_prompt}]}
        )

        # AIモデルに視覚化計画の作成を依頼
        response = self.model.generate_response(
            MODEL_CONFIG[PRIMARY_MODEL],
            planning_conversation,
            [
                {
                    "text": """あなたは優秀なデータ可視化の専門家です。
ユーザーは <title> タグに関する調査データと、<strategy> タグで調査戦略、<data> タグで収集したデータの一部を与えます。
効果的な視覚化計画を立ててください。
ただし <consideration> タグで与える点を考慮した上で、視覚化計画を立ててください。特に <contemplation> タグで与える視覚化タイプを検討してください。
<consideration>
- どのような種類のデータが視覚化に適しているか（定量的データ、定性的データ、比較データ、時系列データなど）
- 最も効果的な視覚化の種類（グラフ、チャート、図表、フロー図など）
- 各視覚化の目的と意図（何を伝えたいのか）
- 視覚化に必要なデータ要素
</consideration>
<contemplation>
- 時系列データの推移を示す折れ線グラフ
- 比較データを示す棒グラフ
- 割合を示す円グラフ
- プロセスや関係性を示すフロー図（mermaid）
- 概念や構造を示す図表（mermaid）
- 分類や階層を示すマインドマップ（mermaid）
</contemplation>

<mermaid> で与える Mermaid に関する利用ルールに注意を払ってください。
<mermaid>
Mermaid は様々なグラフやチャートの出力形式に対応したフォーマットです。

#Mermaid出力形式・図表タイプのガイドとgraph_type

##適切な図表タイプの選び方と各タイプの正確な宣言方法

###プロセスとフロー
フローチャート：意思決定や処理の流れを示す
graph TD  // または LR, TB, RL, BT
,
シーケンス図：時間順の相互作用やメッセージのやり取りを示す
sequenceDiagram
,
状態図：システムの状態遷移を示す
stateDiagram-v2

###関係性とデータモデル

クラス図：オブジェクト指向設計やデータモデルを示す
classDiagram
,
ER図：データベースのエンティティと関係を示す
erDiagram
,
C4コンテキスト図：システムアーキテクチャを示す
C4Context

###計画と進捗

ガントチャート：プロジェクトのタイムラインと進捗を示す
gantt
,
カンバンボード：タスクの状態と進行状況を示す
kanban

###データ分析と比較

円グラフ：全体に対する割合を示す
pie
,
象限チャート：2つの軸による分類を示す
quadrantChart
,
XYチャート：数値データの関係や傾向を示す
xychart-beta
,
サンキー図：フローの量や変換を示す
sankey-beta

###概念と構造
マインドマップ：アイデアや概念の階層関係を示す
mindmap
,
タイムライン：時系列の出来事を示す
timeline
,
ブロック図：システムコンポーネントの構造を示す
block-beta

###技術的図表
Gitグラフ：バージョン管理の履歴とブランチを示す
gitGraph
,
パケット図：データ構造やプロトコルを示す
packet-beta
,
アーキテクチャ図：システムの構成要素と関係を示す
architecture-beta
,
要件図：システム要件と関係を示す
requirementDiagram
,
ZenUML：シーケンス図の代替表現
zenuml
</mermaid>

出力は JSON で </rule> で与えるルールを遵守してください。
<rule>
"type"："graph","mermaid"のどちらかを選択してください。
"graph_type": typeがgraphの場合は matplotlib のグラフタイプを、type が mermaid の場合は、上記の Mermaid 用の graph_type をいれてください。

JSON形式で視覚化計画を出力してください。以下は出力形式の例です:
'''json
{
    "visualizations": [
        {
            "type": "graph",
            "graph_type": "line",
            "title": "年間売上推移",
            "purpose": "過去5年間の売上傾向を示す",
            "data_needed": "年度と売上額のデータ",
            "x_label": "年度",
            "y_label": "売上額（百万円）"
        },
        {
            "type": "mermaid",
            "diagram_type": "flowchart",
            "title": "製品開発プロセス",
            "purpose": "製品開発の各段階と関係者を示す",
            "description": "企画から販売までのプロセスフロー"
        }
    ]
}
'''
</rule>
視覚化計画を作成してください。"""
                }
            ],
            {"temperature": 0.2},  # 少し創造性を持たせる
        )

        self.logger.log(f"AIの視覚化計画：{response}")

        # AIの回答からJSON部分を抽出
        plan_text = ""
        for content in response["output"]["message"]["content"]:
            if "text" in content:
                plan_text += content["text"]

        # JSON部分を抽出
        json_match = re.search(r"```json\s*(.*?)\s*```", plan_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            try:
                plan = json.loads(json_str)
                self.logger.log("視覚化計画を作成しました")
                return plan
            except json.JSONDecodeError:
                self.logger.log("視覚化計画のJSON解析に失敗しました")
        else:
            # JSON形式でない場合は全体をパースしてみる
            try:
                # 波括弧で囲まれた部分を探す
                json_match = re.search(r"\{.*\}", plan_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    plan = json.loads(json_str)
                    self.logger.log("視覚化計画を作成しました（代替パース）")
                    return plan
            except:
                self.logger.log("視覚化計画の代替パースにも失敗しました")

        # 失敗した場合は空の計画を返す
        return {"visualizations": []}

    def _generate_visualizations_from_plan(
        self, plan: Dict[str, Any], visualization_data: Dict[str, Any], data: str
    ) -> None:
        """
        視覚化計画に基づいてグラフとMermaid図を生成

        Args:
            plan: 視覚化計画
            visualization_data: 視覚化データ辞書（更新される）
            data: 収集したデータ
        """
        if "visualizations" not in plan:
            self.logger.log("視覚化計画に 'visualizations' キーがありません")
            return

        for viz in plan["visualizations"]:
            try:
                viz_type = viz.get("type", "")

                if viz_type == "graph":
                    self._generate_graph_from_plan(viz, visualization_data, data)
                elif viz_type == "mermaid":
                    self._generate_mermaid_from_plan(viz, visualization_data, data)
                else:
                    self.logger.log(f"不明な視覚化タイプ: {viz_type}、スキップします")
            except Exception as e:
                self.logger.log(f"視覚化の生成中にエラーが発生しました: {str(e)}")
                # エラーが発生しても次の視覚化の処理を続行

    def _generate_graph_from_plan(
        self, viz: Dict[str, Any], visualization_data: Dict[str, Any], data: str
    ) -> None:
        """
        計画に基づいてグラフを生成

        Args:
            viz: グラフの視覚化計画
            visualization_data: 視覚化データ辞書（更新される）
            data: 収集したデータ
        """
        try:
            graph_type = viz.get("graph_type", "")
            title = viz.get("title", "")
            purpose = viz.get("purpose", "")
            data_needed = viz.get("data_needed", "")
            x_label = viz.get("x_label", "")
            y_label = viz.get("y_label", "")

            if not graph_type or not title:
                self.logger.log("グラフタイプまたはタイトルが指定されていません")
                return

            # データ抽出のためのプロンプト
            data_extraction_prompt = f"""<title>{title}</title>
<graph-type>{graph_type}</graph-type>
<purpose>{purpose}</purpose>
<data-needed>{data_needed}</data-needed>
<x-label>{x_label}</x-label>
<y-label>{y_label}</y-label>
<data>{data[:10000]}</data>"""

            # 会話履歴の初期化
            extraction_conversation = []
            extraction_conversation.append(
                {"role": "user", "content": [{"text": data_extraction_prompt}]}
            )

            # AIモデルにデータ抽出を依頼
            response = self.model.generate_response(
                MODEL_CONFIG[PRIMARY_MODEL],
                extraction_conversation,
                [
                    {
                        "text": """あなたはデータ抽出の専門家です。
ユーザーは <title> でグラフのタイトルを、<graph-type> でグラフ種類を、<purpose> でグラフの目的を、<data_needed> で必要なデータを、<x-label> で X 軸のラベルを、<y-label> で Y 軸のラベルを、<data> でデータを与えます。
以下の JSON 形式でデータを出力してください。
```json
{
  "labels": ["ラベル1", "ラベル2", ...],
  "data": [値1, 値2, ...],
  "series_labels": ["系列1", "系列2", ...],  // 複数系列の場合のみ
  "multi_data": [[系列1の値], [系列2の値], ...],  // 複数系列の場合のみ
}
```
ただし、データが見つからない場合は空の JSON を返してください。
出力は ```json から始め ``` で必ず終えてください。"""
                    }
                ],
                {"temperature": 0},
            )

            # AIの回答からJSON部分を抽出
            extraction_text = ""
            for content in response["output"]["message"]["content"]:
                if "text" in content:
                    extraction_text += content["text"]

            # JSON部分を抽出
            json_match = re.search(r"```json\s*(.*?)\s*```", extraction_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                try:
                    extracted_data = json.loads(json_str)

                    # 抽出したデータでグラフを生成
                    if "labels" in extracted_data and (
                        "data" in extracted_data or "multi_data" in extracted_data
                    ):
                        graph_params = {
                            "graph_type": graph_type,
                            "title": title,
                            "x_label": x_label,
                            "y_label": y_label,
                            "labels": extracted_data.get("labels", []),
                        }

                        # 単一系列か複数系列かを判断
                        if (
                            "multi_data" in extracted_data
                            and "series_labels" in extracted_data
                        ):
                            graph_params["multi_data"] = extracted_data["multi_data"]
                            graph_params["series_labels"] = extracted_data[
                                "series_labels"
                            ]
                        elif "data" in extracted_data:
                            graph_params["data"] = extracted_data["data"]

                        # グラフ生成
                        result = self.tool_handler.generate_graph(**graph_params)

                        try:
                            result_data = json.loads(result)
                            if "graph_path" in result_data:
                                # 目的情報を追加
                                result_data["purpose"] = purpose
                                visualization_data["graphs"].append(result_data)
                                self.logger.log(
                                    f"計画に基づいてグラフを生成しました: {result_data['graph_path']}"
                                )
                        except:
                            self.logger.log("グラフ生成結果の解析に失敗しました")

                except json.JSONDecodeError:
                    self.logger.log("データ抽出のJSON解析に失敗しました")
        except Exception as e:
            self.logger.log(f"グラフ生成中にエラーが発生しました: {str(e)}")

    def _generate_mermaid_from_plan(
        self, viz: Dict[str, Any], visualization_data: Dict[str, Any], data: str
    ) -> None:
        """
        計画に基づいてMermaid図を生成

        Args:
            viz: Mermaid図の視覚化計画
            visualization_data: 視覚化データ辞書（更新される）
            data: 収集したデータ
        """
        try:
            # 必要なパラメータを取得（存在しない場合はデフォルト値を使用）
            diagram_type = ""
            if "diagram_type" in viz:
                diagram_type = viz["diagram_type"]
            elif "graph_type" in viz:
                diagram_type = viz["graph_type"]
            title = viz.get("title", "Mermaid Diagram")
            purpose = viz.get("purpose", "")
            description = viz.get("description", "")

            if not diagram_type:
                self.logger.log(f"Mermaid図のタイプが指定されていません:{viz}")
                return

            # Mermaid図生成のためのプロンプト
            mermaid_prompt = f"""<title>{title}</title>
<diagram-type>{diagram_type}</diagram-type>
<purpose>{purpose}</purpose>
<description>{description}</description>
<data>{data[:5000]}</data>
"""

            # 会話履歴の初期化
            mermaid_conversation = []
            mermaid_conversation.append(
                {"role": "user", "content": [{"text": mermaid_prompt}]}
            )

            # AIモデルにMermaid図の生成を依頼
            response = self.model.generate_response(
                MODEL_CONFIG[PRIMARY_MODEL],
                mermaid_conversation,
                [
                    {
                        "text": """あなたは Mermaid 図の専門家です。ユーザーが <title> タグで与える Mermaid 図を作成してください。
図の種類は <diagram-type> タグで、目的は <purpose> タグで、説明は <description> タグで、データは <data> タグで、それぞれユーザーが与えます。
ただし <rules> で与えるルールを遵守してください。
<rules>
* <diagram-type> タグで与えた図の記法を遵守すること。
* 図は明確で読みやすいこと
* 必要に応じて色やスタイルを適用すること
* 複雑すぎず、シンプルで理解しやすいこと
* 図の目的に沿っていること
<rules>
コードの前後に```mermaidや```などのマークダウン記法は不要です。Mermaid図のコードのみを出力してください。"""
                    }
                ],
                {"temperature": 0.2},  # 少し創造性を持たせる
            )

            # AIの回答からMermaidコードを抽出
            mermaid_text = ""
            for content in response["output"]["message"]["content"]:
                if "text" in content:
                    mermaid_text += content["text"]

            # Mermaidコードを抽出（マークダウンコードブロックがある場合とない場合の両方に対応）
            mermaid_match = re.search(
                r"```mermaid\s*(.*?)\s*```", mermaid_text, re.DOTALL
            )
            if mermaid_match:
                mermaid_code = mermaid_match.group(1)
            else:
                # コードブロックがない場合は全体をMermaidコードとして扱う
                mermaid_code = mermaid_text.strip()

            # Mermaid図をレンダリング
            result = self.tool_handler.render_mermaid(mermaid_code, title)

            try:
                result_data = json.loads(result)
                if "mermaid_path" in result_data:
                    # 目的情報を追加
                    result_data["purpose"] = purpose
                    visualization_data["mermaid_diagrams"].append(result_data)
                    self.logger.log(
                        f"計画に基づいてMermaid図を生成しました: {result_data['mermaid_path']}"
                    )
            except:
                self.logger.log("Mermaid図のレンダリング結果の解析に失敗しました")
        except Exception as e:
            self.logger.log(f"Mermaid図生成中にエラーが発生しました: {str(e)}")

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
        markdown_tables = re.findall(
            r"(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n)+)", data
        )

        for i, table in enumerate(markdown_tables):
            # 表のタイトルを抽出（表の前の行がタイトルっぽい場合）
            title = f"表 {i+1}"
            table_pos = data.find(table)
            if table_pos > 0:
                # 表の前の行を取得
                prev_text = data[:table_pos].strip()
                last_line = prev_text.split("\n")[-1]
                # 行が短く、「表」や「一覧」などの単語を含む場合はタイトルとして使用
                if len(last_line) < 50 and (
                    "表" in last_line or "一覧" in last_line or "リスト" in last_line
                ):
                    title = last_line

            tables.append(
                {
                    "type": "markdown",
                    "content": table,
                    "id": f"table_{i+1}",
                    "title": title,
                }
            )

        return tables

    def _create_visualization_prompt(
        self, user_prompt: str, strategy_text: str, data: str
    ) -> str:
        """
        視覚化プロンプトの作成

        Args:
            user_prompt: ユーザーの研究テーマ
            strategy_text: 調査戦略テキスト
            data: 収集したデータ

        Returns:
            str: 視覚化プロンプト
        """
        return f"""<title>
{user_prompt}
</title>
<strategy>
{strategy_text}
</strategy>
<data>
{data[:10000]}  # データが長い場合は一部を使用
</data>"""

    def _initialize_conversation(self, user_prompt: str, pre_research_data: str):
        """会話の初期化"""
        self.conversation["A"] = [
            {
                "role": "user",
                "content": [
                    {
                        "text": f"""今回のトピックと事前調査結果は以下の通りです。
<topic>
{user_prompt}
</topic>
<pre-research>
{pre_research_data}
<pre-research>
一緒に調査内容を検討しましょう。よろしくお願いします。まずは何かアイデアはありますか？"""
                    }
                ],
            }
        ]
        self.conversation["I"] = []

    def _conduct_conversation(self, system_prompt: List[Dict], max_turns: int):
        """AIモデル間の会話を実行"""
        for turn in range(max_turns):
            self.logger.subsection(f"討議ターン {turn + 1}")

            # Primary AIの応答
            primary_response = self._get_model_response(
                PRIMARY_MODEL, self.conversation["A"], system_prompt
            )
            self._update_conversation(primary_response, "A", "I")

            # Secondary AIの応答
            secondary_response = self._get_model_response(
                SECONDARY_MODEL, self.conversation["I"], system_prompt
            )
            self._update_conversation(secondary_response, "I", "A")

    def _get_model_response(
        self, model_name: str, messages: List[Dict], system_prompt: List[Dict]
    ) -> str:
        """モデルからのレスポンスを取得"""
        self.logger.log(f"=== {model_name} の発言 ===")
        response = self.model.generate_response(
            MODEL_CONFIG[model_name],
            messages,
            system_prompt,
            {"temperature": 1},
        )
        response_text = response["output"]["message"]["content"][0]["text"]
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
        return user_prompt

    def _create_qualification_prompt(self) -> List[Dict]:
        """資格確認プロンプトの作成"""
        # モードに応じた最大会話ターン数を設定
        max_turns = (
            SUMMARY_CONVERSATION_TURNS
            if self.mode == "summary"
            else MAX_CONVERSATION_TURNS
        )

        return [
            {
                "text": f"""あなたは優秀なリサーチャーです。
会話相手はあなたと同じ調査内容で依頼を受けている同僚の AI さんです。
最初に <topic> タグで調査のトピックを、<pre-research> タグで事前の調査内容が与えらます。
調査内容はキーワードや意味の列挙なので、調査の粒度や観点などは仮説を持って調査をした後調査結果を作成し、調査結果のフィードバックをもらうことでしか改善できません。
AI さんはあなたの思考の枠を外して広い視野を提供してくれます。
あなたも調査内容を自由に広げて網羅性を高め、その後どんなことを調べるのかを深めていってください。
特に反対意見や出ていない意見は大事です。既出の意見はそんなに重要ではありません。
お互いの網羅性や深さの不足を指摘しながらAI さんとの会話を重ね、リサーチする内容を決めていってください。
会話はお互い {max_turns} 回までしかできないので、それまでに議論をまとめてください。
ただし会話は <rules> を遵守してください。
<rules>
* 具体的にどんなことをするのか actionable にまとめる必要があります。
* 予算や人員については触れてはいけません。調査する内容にだけフォーカスしてください。
* 調査対象に関わるだろう人の観点を複数入れてください。例えば料理であれば、調理器具をつくる人、食材を売る人、食材を買う人、食材を運ぶ人、料理を作る人、料理を運ぶ人、食べる人、口コミを書く人、ゴミを捨てる人、などです。与えられたお題に反しない限り様々な人に思いを巡らせてください。
* 会話を始める前に、自分がどのように考えたのか、を述べてから結論を述べてください。
* さまざまな観点から内容をブラッシュアップしてください。
* 事前調査に基づき、画像取得や作成したグラフ画像などの視覚的な情報をできるだけ活用することを検討してください。
* 説明をよりわかりやすく整理するために mermaid 形式を必要に応じて利用し、sequence / class / er diagram / mindmap / pie / gantt / quadrant / gitgraph / timeline / sankey-beta / architecture-beta などを議論上の整理に用いてください。
</rules>
また、発言する際は最初に必ず x 回目の発言です、と言ってください。発言回数は自分の発言回数であり、相手の発言はカウントしてはいけません。
"""
            }
        ]

    def _create_strategy_prompt(self, user_prompt: str) -> List[Dict]:
        """戦略プロンプトの作成"""
        return [
            {
                "text": f"""あなたは優秀なリサーチャーです。
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
"""
            }
        ]

    def _extract_conversation_text(self) -> str:
        """会話履歴からテキストを抽出"""
        extracted_text = ""
        for c in self.conversation["F"]:
            if "content" in c:
                for item in c["content"]:
                    if "text" in item:
                        extracted_text += item["text"] + "\n\n"
                    elif "toolResult" in item and "content" in item["toolResult"]:
                        for content_item in item["toolResult"]["content"]:
                            if "text" in content_item:
                                extracted_text += content_item["text"] + "\n\n"
        return extracted_text

    def _log_research_summary(self, research_text: str):
        """研究サマリーのログ出力"""
        self.logger.section("収集データの整理")
        self.logger.log("収集データのサマリー:")
        summary = (
            research_text[:500] + "..." if len(research_text) > 500 else research_text
        )
        self.logger.log(summary)
