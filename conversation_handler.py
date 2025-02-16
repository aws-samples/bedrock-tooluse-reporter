from typing import Dict, List
from models import BedrockModel
from config import MODEL_CONFIG, PRIMARY_MODEL, SECONDARY_MODEL, MAX_CONVERSATION_TURNS
from logger import DualLogger


class ConversationHandler:
    def __init__(self, model: BedrockModel, logger: DualLogger):
        self.model = model
        self.logger = logger
        self.conversation = {'A': [], 'I': [], 'F': []}

    def initialize_conversation(self, user_prompt: str):
        """
        会話を初期化

        Args:
            user_prompt: ユーザーから受け取った調査テーマ
        """
        self.conversation['A'] = [
            {
                "role": "user",
                "content": [
                    {
                        "text": f'「{user_prompt}」って大変なお題をもらっちゃいましたね。どうしましょうか。'
                    }
                ],
            }
        ]
        self.conversation['I'] = []

    def conduct_conversation(self, system_prompt: List[Dict]) -> Dict:
        """AIモデル間の会話を実行"""
        self.logger.section("AI間の討議開始")

        for turn in range(MAX_CONVERSATION_TURNS):
            self.logger.subsection(f"討議ターン {turn + 1}")

            # Primary AIの応答
            self.logger.log(f"=== {PRIMARY_MODEL} の発言 ===")
            primary_response = self._get_model_response(
                MODEL_CONFIG[PRIMARY_MODEL], self.conversation['A'], system_prompt
            )
            self.logger.log(primary_response)
            self._update_conversation_history(primary_response, 'A', 'I')

            # Secondary AIの応答
            self.logger.log(f"\n=== {SECONDARY_MODEL} の発言 ===")
            secondary_response = self._get_model_response(
                MODEL_CONFIG[SECONDARY_MODEL], self.conversation['I'], system_prompt
            )
            self.logger.log(secondary_response)
            self._update_conversation_history(secondary_response, 'I', 'A')

        self.logger.section("AI間の討議完了")
        return self.conversation

    def _get_model_response(
        self, model_id: str, messages: List[Dict], system_prompt: List[Dict]
    ) -> str:
        """
        モデルからレスポンスを取得

        Args:
            model_id: 使用するモデルのID
            messages: 会話履歴
            system_prompt: システムプロンプト

        Returns:
            str: モデルの応答テキスト
        """
        response = self.model.generate_response(
            model_id=model_id,
            messages=messages,
            system_prompt=system_prompt,
            inference_config={'temperature': 1},
        )
        return response['output']['message']['content'][0]['text']

    def _update_conversation_history(
        self, response: str, current_model: str, next_model: str
    ):
        """
        会話履歴を更新

        Args:
            response: モデルの応答
            current_model: 現在のモデルの識別子
            next_model: 次のモデルの識別子
        """
        self.conversation[current_model].append(
            {"role": "assistant", "content": [{"text": response}]}
        )
        self.conversation[next_model].append(
            {"role": "user", "content": [{"text": response}]}
        )
