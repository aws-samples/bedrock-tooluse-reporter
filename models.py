import boto3
from typing import Dict, List, Any


class BedrockModel:
    def __init__(self):
        self.client = boto3.client('bedrock-runtime')

    def generate_response(
        self,
        model_id: str,
        messages: List[Dict],
        system_prompt: List[Dict],
        inference_config: Dict[str, Any],
        tool_config: Dict = None,
    ) -> Dict:
        """AIモデルを使用してレスポンスを生成"""
        kwargs = {
            'modelId': model_id,
            'messages': messages,
            'system': system_prompt,
            'inferenceConfig': inference_config,
        }

        if tool_config:
            kwargs['toolConfig'] = tool_config

        return self.client.converse(**kwargs)
