"""
Data Collector Module

This module contains the DataCollector class which is responsible for gathering research data
from various sources using available tools. It manages the interaction between AI models
and external tools to collect relevant information based on the research strategy.

The data collection process includes:
1. Executing search queries
2. Retrieving content from URLs
3. Processing and organizing collected data
4. Tracking source references
5. Searching and saving images
6. Generating graphs from data
"""

from datetime import datetime
import os
import json
from typing import Dict, List, Optional, Tuple, Set
from ..models.bedrock import BedrockModel
from ..models.source_reference import SourceReference, SourceReferenceManager
from ..utils.tool_handler import ToolHandler
from ..utils.exceptions import DataCollectionError
from ..config.settings import (
    MODEL_CONFIG,
    PRIMARY_MODEL,
    TOOL_CONFIG,
    MAX_RESEARCH_SEARCHES,
    SUMMARY_RESEARCH_SEARCHES,
)


class DataCollector:
    def __init__(self, model: BedrockModel, tool_handler: ToolHandler, logger):
        """
        データコレクターの初期化

        Args:
            model: BedrockModelインスタンス
            tool_handler: ToolHandlerインスタンス
            logger: ロガーインスタンス
        """
        self.model = model
        self.tool_handler = tool_handler
        self.logger = logger
        self.source_manager = SourceReferenceManager()
        self.current_image_dir = None
        self.has_retrieved_image = False  # 画像取得フラグ

    def set_image_directory(self, image_dir: str) -> None:
        """
        画像ディレクトリを設定

        Args:
            image_dir: 画像を保存するディレクトリのパス
        """
        self.current_image_dir = image_dir
        self.tool_handler.set_image_directory(image_dir)
        self.logger.log(f"DataCollector: 画像ディレクトリを設定: {image_dir}")

    def collect_research_data(
        self,
        conversation: Dict,
        strategy_text: str,
        user_prompt: str,
        mode: str = "standard",
        max_iterations: Optional[int] = None,
    ) -> Tuple[List[str], SourceReferenceManager]:
        """
        情報収集を実行

        Args:
            conversation: 会話履歴
            strategy_text: 調査戦略テキスト
            user_prompt: ユーザーのプロンプト
            mode: 研究モード ("standard" または "summary")
            max_iterations: 最大反復回数（指定がない場合はモードに基づいて決定）

        Returns:
            Tuple[List[str], SourceReferenceManager]: 収集したデータのリストとソース参照マネージャー

        Raises:
            DataCollectionError: データ収集時のエラー
        """
        self.logger.section("情報収集フェーズ開始")
        self.has_retrieved_image = False  # 画像取得フラグをリセット

        research_prompt = self._create_research_prompt()
        conversation['F'] = []
        conversation['F'].append({"role": "user", "content": [{"text": strategy_text}]})

        # モードに基づいて最大反復回数を決定
        if max_iterations is None:
            max_iterations = (
                SUMMARY_RESEARCH_SEARCHES
                if mode == "summary"
                else MAX_RESEARCH_SEARCHES
            )

        self.logger.log(f"情報収集モード: {mode}, 最大反復回数: {max_iterations}")

        collected_data = []
        try:
            for i in range(max_iterations):  # モードに基づいた最大反復回数
                self.logger.subsection(f"情報収集ステップ {i+1}/{max_iterations}")

                # 画像が取得されていない場合、最後の反復で強制的に画像検索を促す
                if not self.has_retrieved_image and i == max_iterations - 1:
                    self.logger.log("画像が取得されていないため、画像検索を促します")
                    image_prompt = self._create_image_search_prompt(user_prompt)
                    conversation['F'].append(
                        {"role": "user", "content": [{"text": image_prompt}]}
                    )

                response = self.model.generate_response(
                    MODEL_CONFIG[PRIMARY_MODEL],
                    conversation['F'],
                    research_prompt,
                    {'temperature': 0},
                    TOOL_CONFIG,
                )

                # AIの思考プロセスを出力
                self._log_ai_thinking(response)

                tool_use = self.tool_handler.process_tool_response(response)

                if not tool_use:
                    self.logger.log("情報収集完了（ツール使用なし）")
                    break

                # まずアシスタントメッセージを追加（ツール使用を含む）
                conversation['F'].append(
                    {
                        'role': 'assistant',
                        'content': response['output']['message']['content'],
                    }
                )

                if tool_use['name'] == 'is_finished':
                    # 画像が取得されていない場合、終了せずに画像検索を促す
                    if not self.has_retrieved_image and i < max_iterations - 1:
                        self.logger.log(
                            "画像が取得されていないため、終了せずに画像検索を促します"
                        )
                        image_prompt = self._create_image_search_prompt(user_prompt)
                        conversation['F'].append(
                            {
                                'role': 'user',
                                'content': [
                                    {
                                        'toolResult': {
                                            'toolUseId': tool_use['toolUseId'],
                                            'content': [{'text': image_prompt}],
                                        }
                                    }
                                ],
                            }
                        )
                        continue
                    else:
                        conversation['F'].append(
                            {
                                'role': 'user',
                                'content': [
                                    {
                                        'toolResult': {
                                            'toolUseId': tool_use['toolUseId'],
                                            'content': [{'text': 'finished'}],
                                        }
                                    }
                                ],
                            }
                        )
                        self.logger.log("情報収集完了（明示的終了）")
                        break

                # ツールの実行と結果の処理
                result, citation = self._execute_tool(tool_use)
                if result:
                    # Add citation mark to the collected data if available
                    if citation:
                        result = f"{result}\n\n{citation}"
                    collected_data.append(result)
                # ツール結果を追加
                self._update_conversation(conversation, tool_use, result)

            # 最終チェック: 画像が取得されていない場合は強制的に画像検索を実行
            if not self.has_retrieved_image:
                self.logger.log(
                    "最終チェック: 画像が取得されていないため、強制的に画像検索を実行します"
                )
                image_result = self._force_image_search(user_prompt)
                if image_result:
                    collected_data.append(image_result)

        except Exception as e:
            raise DataCollectionError(f"Error during data collection: {str(e)}")

        self.logger.section("情報収集フェーズ完了")
        return collected_data, self.source_manager

    def _force_image_search(self, user_prompt: str) -> Optional[str]:
        """
        強制的に画像検索を実行

        Args:
            user_prompt: ユーザーのプロンプト

        Returns:
            Optional[str]: 画像検索結果。失敗した場合はNone
        """
        try:
            self.logger.log(f"強制的に画像検索を実行: '{user_prompt}'")
            result = self.tool_handler.image_search(query=user_prompt, max_results=3)

            # 結果をJSONとしてパース
            result_data = json.loads(result)

            # 画像が取得できたかチェック
            if 'images' in result_data and result_data['images']:
                self.has_retrieved_image = True
                self.logger.log(
                    f"強制的な画像検索で {len(result_data['images'])} 枚の画像を取得しました"
                )
                return f"強制的な画像検索の結果:\n{result}"
            else:
                self.logger.log("強制的な画像検索でも画像を取得できませんでした")
                return None

        except Exception as e:
            self.logger.log(f"強制的な画像検索中にエラーが発生しました: {str(e)}")
            return None

    def _create_research_prompt(self) -> List[Dict]:
        """研究プロンプトの作成"""
        return [
            {
                'text': f'''あなたは優秀なリサーチャーです。
ユーザーはトピックを提供します。詳細なレポート作成は後段で行うので、まず必要な情報について包括的な調査を徹底的にしてください。

与えられたトピックについて、<point-of-view> タグで与えた点を明らかにするための情報を収集します。
また、<tools> で与えたツールのみを使用して粛々と情報収集します。
<rules> で与えた制約事項は大切なので遵守してください。
<point-of-view>
1. 主要な概念や用語の定義
2. 最新のニュースや画像
3. 関連する用語や関連するコンテキスト
4. 関連する最新の動向や傾向や話題
5. 関連する最新の研究
6. データポイント
7. 関連する事例
</point-of-view>
<tools>
1. search: Webで情報を検索する
2. get_content: URLからコンテンツを取得する
3. image_search: 関連する画像を検索して取得して保存する
4. generate_graph: 数値データからグラフ画像（折れ線グラフ・棒グラフ・円グラフ）を生成する
5. render_mermaid: Mermaid形式の文字列を渡すと図を作成する
6. is_finished: 情報収集を完了する
</tools>
<rules>
- あなたが賢いのは知っていますが、一旦すべてのバイアスを除去と最新情報を得るために、例え知っているトピックだったとしてもすべての知識を忘れ、与えられたトピックについて貪欲に学んでください。
- 必ず1つ以上の画像を取得すること
- 数値データがある場合はグラフ画像を作成すること
- 視覚的な情報を積極的に活用すること
- 情報引用時は [※N] の形式で出典を明記すること
- コンテキストがわからない用語も含めてキーワードに分割して調査すること
</rules>

ユーザーがトピックを与えたら調査を開始してください。
'''
            }
        ]

    def _create_image_search_prompt(self, user_prompt: str) -> str:
        """画像検索を促すプロンプトの作成"""
        return f'''
レポートの視覚的な情報を充実させるために、「{user_prompt}」に関連する画像を検索して取得してください。
image_searchツールを使用して、関連する画像を少なくとも1つ以上取得することが重要です。
取得した画像はレポートで参照できるようになります。
'''

    def _log_ai_thinking(self, response: Dict):
        """AIの思考プロセスをログに記録"""
        self.logger.log("AI の思考:")
        for content in response['output']['message']['content']:
            if 'text' in content:
                self.logger.log(content['text'])
        self.logger.log("")

    def _execute_tool(self, tool_use: Dict) -> Tuple[Optional[str], Optional[str]]:
        """
        ツールを実行して結果と引用マークを取得

        Args:
            tool_use: ツール使用情報

        Returns:
            Tuple[Optional[str], Optional[str]]: ツールの実行結果と引用マーク
        """
        self.logger.log(f"使用ツール: {tool_use['name']}")
        self.logger.log(f"入力パラメータ: {tool_use['input']}")

        result = None
        citation = None

        if tool_use['name'] == 'search':
            result = self.tool_handler.search(**tool_use['input'])
            self.logger.log("\n検索結果:")

        elif tool_use['name'] == 'get_content':
            result, title = self.tool_handler.get_content(**tool_use['input'])
            if result:
                # Add source reference and get citation mark
                url = tool_use['input'].get('url', '')
                citation = self.source_manager.add_reference(
                    SourceReference(
                        url=url,
                        title=title,
                        accessed_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    )
                )
            self.logger.log("\nコンテンツ取得結果:")

        elif tool_use['name'] == 'image_search':
            # 画像ディレクトリが設定されていることを確認
            if self.current_image_dir:
                result = self.tool_handler.image_search(**tool_use['input'])
                # 画像が取得できたかチェック
                try:
                    result_data = json.loads(result)
                    if 'images' in result_data and result_data['images']:
                        self.has_retrieved_image = True
                        self.logger.log(
                            f"\n画像検索結果: {len(result_data['images'])} 枚の画像を取得しました"
                        )
                    else:
                        self.logger.log("\n画像検索結果: 画像を取得できませんでした")
                except:
                    self.logger.log("\n画像検索結果: 結果の解析に失敗しました")
            else:
                result = '{"error": "画像ディレクトリが設定されていません"}'
                self.logger.log("\n画像ディレクトリが設定されていません")

        elif tool_use['name'] == 'generate_graph':
            # 画像ディレクトリが設定されていることを確認
            if self.current_image_dir:
                result = self.tool_handler.generate_graph(**tool_use['input'])
                # グラフが生成できたかチェック
                try:
                    result_data = json.loads(result)
                    if 'graph_path' in result_data:
                        self.has_retrieved_image = True  # グラフも画像として扱う
                        self.logger.log("\nグラフ生成結果: グラフを生成しました")
                    else:
                        self.logger.log("\nグラフ生成結果: グラフの生成に失敗しました")
                except:
                    self.logger.log("\nグラフ生成結果: 結果の解析に失敗しました")
            else:
                result = '{"error": "画像ディレクトリが設定されていません"}'
                self.logger.log("\n画像ディレクトリが設定されていません")

        if result:
            display_result = result[:500] + "..." if len(result) > 500 else result
            self.logger.log(display_result)
            if citation:
                self.logger.log(f"\n引用マーク: {citation}")

        return result, citation

    def _extract_title(self, content: str) -> Optional[str]:
        """Extract title from HTML content"""
        import re

        title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
        if title_match:
            return title_match.group(1)
        return None

    def _update_conversation(self, conversation: Dict, tool_use: Dict, result: str):
        """会話履歴の更新"""
        conversation['F'].append(
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
