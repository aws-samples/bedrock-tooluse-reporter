"""
データ収集を担当するクラス
"""

from typing import Dict, List, Optional
from ..models.bedrock import BedrockModel
from ..utils.tool_handler import ToolHandler
from ..utils.exceptions import DataCollectionError
from ..config.settings import MODEL_CONFIG, PRIMARY_MODEL, TOOL_CONFIG


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

    def collect_research_data(
        self,
        conversation: Dict,
        strategy_text: str,
        user_prompt: str,
    ) -> List[str]:
        """
        情報収集を実行

        Args:
            conversation: 会話履歴
            strategy_text: 調査戦略テキスト
            user_prompt: ユーザーのプロンプト

        Returns:
            List[str]: 収集したデータのリスト

        Raises:
            DataCollectionError: データ収集時のエラー
        """
        self.logger.section("情報収集フェーズ開始")

        research_prompt = self._create_research_prompt(user_prompt)
        conversation['F'] = []
        conversation['F'].append({"role": "user", "content": [{"text": strategy_text}]})

        collected_data = []
        try:
            for i in range(100):  # 最大100回の情報収集試行
                self.logger.subsection(f"情報収集ステップ {i+1}")

                response = self.model.generate_response(
                    MODEL_CONFIG[PRIMARY_MODEL],
                    conversation['F'],
                    research_prompt,
                    {'temperature': 0},
                    TOOL_CONFIG,
                )

                # AIの思考プロセスを出力
                self._log_ai_thinking(response)

                conversation['F'].append(
                    {
                        'role': 'assistant',
                        'content': response['output']['message']['content'],
                    }
                )

                tool_use = self.tool_handler.process_tool_response(response)
                if not tool_use:
                    self.logger.log("情報収集完了（ツール使用なし）")
                    break

                if tool_use['name'] == 'is_finished':
                    self.logger.log("情報収集完了（明示的終了）")
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
                    break

                # ツールの実行と結果の処理
                result = self._execute_tool(tool_use)
                if result:
                    collected_data.append(result)
                    self._update_conversation(conversation, tool_use, result)

        except Exception as e:
            raise DataCollectionError(f"Error during data collection: {str(e)}")

        self.logger.section("情報収集フェーズ完了")
        return collected_data

    def _create_research_prompt(self, user_prompt: str) -> List[Dict]:
        """研究プロンプトの作成"""
        return [
            {
                'text': f'''あなたは優秀なリサーチャーです。
あなたは「{user_prompt}」 という調査依頼を受けとっています。
ユーザーはレポートのフレームワーク与えます。
ただしあなたは Web 検索をするか、検索結果の URL にアクセスをして情報を取得し、その結果を元に自分自身で考察する以外のことはできません。
あなたは、どうやって調査を進めるか考えたかと保持しているツールを使用して、必要な情報をすべて集めてください。
'''
            }
        ]

    def _log_ai_thinking(self, response: Dict):
        """AIの思考プロセスをログに記録"""
        self.logger.log("AI の思考:")
        for content in response['output']['message']['content']:
            if 'text' in content:
                self.logger.log(content['text'])
        self.logger.log("")

    def _execute_tool(self, tool_use: Dict) -> Optional[str]:
        """
        ツールを実行して結果を取得

        Args:
            tool_use: ツール使用情報

        Returns:
            Optional[str]: ツールの実行結果
        """
        self.logger.log(f"使用ツール: {tool_use['name']}")
        self.logger.log(f"入力パラメータ: {tool_use['input']}")

        result = None
        if tool_use['name'] == 'search':
            result = self.tool_handler.search(**tool_use['input'])
            self.logger.log("\n検索結果:")
        elif tool_use['name'] == 'get_content':
            result = self.tool_handler.get_content(**tool_use['input'])
            self.logger.log("\nコンテンツ取得結果:")

        if result:
            display_result = result[:500] + "..." if len(result) > 500 else result
            self.logger.log(display_result)

        return result

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
