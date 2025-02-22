"""
Bedrock モデルの設定と操作を担当するクラス
"""
import boto3
import time
from typing import Dict, List, Any
from botocore.exceptions import ClientError
from src.utils.exceptions import ModelError


class BedrockModel:
    def __init__(self):
        """Bedrock クライアントの初期化"""
        self.client = boto3.client('bedrock-runtime')
        self.max_retries = 5
        self.base_delay = 20  # Initial delay in seconds

    def _exponential_backoff(self, retry_count: int) -> float:
        """
        指数バックオフの待機時間を計算

        Args:
            retry_count: 現在のリトライ回数

        Returns:
            float: 待機すべき秒数
        """
        return min(300, self.base_delay * (2 ** retry_count))  # Max delay capped at 300 seconds

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
        エラー時は指数バックオフでリトライ

        Args:
            model_id: 使用するモデルのID
            messages: 会話履歴
            system_prompt: システムプロンプト
            inference_config: 推論設定
            tool_config: ツール設定（オプション）

        Returns:
            Dict: モデルからのレスポンス

        Raises:
            ModelError: 最大リトライ回数を超えた場合やその他のエラー
        """
        kwargs = {
            'modelId': model_id,
            'messages': messages,
            'system': system_prompt,
            'inferenceConfig': inference_config,
        }

        if tool_config:
            kwargs['toolConfig'] = tool_config

        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                response = self.client.converse(**kwargs)
                return response  # Successful response, return immediately
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code in ['ThrottlingException', 'ServiceUnavailable', 'InternalServerError']:
                    if retry_count == self.max_retries:
                        raise ModelError(f"Maximum retries ({self.max_retries}) exceeded. Last error: {str(e)}")
                    
                    wait_time = self._exponential_backoff(retry_count)
                    time.sleep(wait_time)
                    retry_count += 1
                else:
                    # For other types of errors, raise immediately
                    raise ModelError(f"Bedrock API error: {str(e)}")
            except Exception as e:
                # For any other unexpected errors
                raise ModelError(f"Unexpected error during API call: {str(e)}")
