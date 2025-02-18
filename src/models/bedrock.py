"""
Bedrock モデルの設定と操作を担当するクラス
"""
import boto3
from typing import Dict, List, Any


class BedrockModel:
    def __init__(self):
        """Bedrock クライアントの初期化"""
        self.client = boto3.client('bedrock-runtime')

    def generate_response(
        self,
        model_id: str,
        messages: List[Dict],
        system_prompt: List[Dict],
        inference_config: Dict[str, Any],
        tool_config: Dict = None,
    ) -> Dict:
        """
        AIモデルを使用してレスポンスを生成

        Args:
            model_id: 使用するモデルのID
            messages: 会話履歴
            system_prompt: システムプロンプト
            inference_config: 推論設定
            tool_config: ツール設定（オプション）

        Returns:
            Dict: モデルからのレスポンス
        """
        kwargs = {
            'modelId': model_id,
            'messages': messages,
            'system': system_prompt,
            'inferenceConfig': inference_config,
        }

        if tool_config:
            kwargs['toolConfig'] = tool_config

        return self.client.converse(**kwargs)
