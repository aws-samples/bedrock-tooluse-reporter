"""
Bedrock モデルの設定と操作を担当するクラス（複数アカウント対応版）
"""

import boto3
import itertools
import time
import logging
from typing import Dict, List, Any, Optional
from botocore.config import Config
from botocore.exceptions import ClientError
from ..utils.exceptions import ModelError
from ..config.settings import LLM_CONNECTION


class BedrockModel:
    """
    AWS Bedrock APIを使用してLLMモデルとの対話を処理するクラス（複数アカウント対応）

    機能:
    - 複数AWSアカウント/プロファイルのラウンドロビン
    - Throttling発生時の自動クライアント切り替え
    - 指数バックオフ付きリトライ
    """

    def __init__(self, logger):
        """
        初期化処理（複数クライアント対応版）
        """
        self.logger = logger
        self._validate_settings()
        self.clients = self._initialize_clients()
        self.client_cycle = itertools.cycle(self.clients)
        self.max_retries = LLM_CONNECTION["max_retries"]
        self.base_delay = LLM_CONNECTION["base_delay"]
        self.max_delay = LLM_CONNECTION["max_delay"]

    def _validate_settings(self):
        """設定値のバリデーション"""
        required_keys = ["timeout", "max_retries", "base_delay", "max_delay", "profiles"]
        for key in required_keys:
            if key not in LLM_CONNECTION:
                raise ModelError(f"Missing required config key: {key}")

    def _initialize_clients(self):
        """
        複数AWSプロファイルからクライアントを初期化
        設定ファイルのprofilesリストに基づいてクライアントを生成
        """
        clients = []
        for profile in LLM_CONNECTION["profiles"]:
            try:
                session = boto3.Session(profile_name=profile)
                client = session.client(
                    "bedrock-runtime",
                    config=Config(
                        connect_timeout=LLM_CONNECTION["timeout"],
                        read_timeout=LLM_CONNECTION["timeout"],
                    )
                )
                client.meta.profile_name = profile  # プロファイル名を保持
                clients.append(client)
                self.logger.log(f"Initialized client for profile: {profile}")
            except Exception as e:
                self.logger.log(
                    f"Failed to initialize client for profile {profile}: {str(e)}",
                    level=logging.ERROR
                )
                raise ModelError(f"Client initialization failed: {str(e)}")
        return clients

    def _exponential_backoff(self, retry_count: int) -> float:
        """指数バックオフ計算（最大遅延時間付き）"""
        return min(self.max_delay, self.base_delay * (2 ** retry_count))

    def _rotate_client(self, current_client):
        """クライアントをローテーションしログ出力"""
        next_client = next(self.client_cycle)
        self.logger.log(
            f"Rotating client: {current_client.meta.profile_name} → {next_client.meta.profile_name}"
        )
        return next_client

    def generate_response(
        self,
        model_id: str,
        messages: List[Dict],
        system_prompt: List[Dict],
        inference_config: Dict[str, Any],
        tool_config: Optional[Dict] = None,
    ) -> Dict:
        """
        レスポンス生成（複数クライアント対応版）
        """
        kwargs = {
            "modelId": model_id,
            "messages": messages,
            "system": system_prompt,
            "inferenceConfig": inference_config,
        }

        if tool_config:
            kwargs["toolConfig"] = tool_config

        retry_count = 0
        current_client = next(self.client_cycle)

        while retry_count <= self.max_retries:
            try:
                response = current_client.converse(**kwargs)
                return response
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code in ["ThrottlingException", "ServiceUnavailable", "InternalServerError"]:
                    if retry_count == self.max_retries:
                        raise ModelError(f"Max retries ({self.max_retries}) exceeded. Last error: {str(e)}")

                    # クライアントローテーション
                    prev_client = current_client
                    current_client = self._rotate_client(current_client)
                    
                    wait_time = self._exponential_backoff(retry_count)
                    self.logger.log(
                        f"Error on {prev_client.meta.profile_name}: {str(e)}. "
                        f"Retrying with {current_client.meta.profile_name} in {wait_time}s..."
                    )
                    
                    time.sleep(wait_time)
                    retry_count += 1
                else:
                    raise ModelError(f"API error: {str(e)}")
            except Exception as e:
                raise ModelError(f"Unexpected error: {str(e)}")

    def process_pdf(self, pdf_content: bytes, model_id: str) -> str:
        """
        PDF処理（複数クライアント対応版）
        """
        try:
            prompt = "あなたは優秀なリサーチャーです。PDFの内容から、コンテキストを全て維持した状態で、中の図や文字列を解釈して内容を長文で説明するようにお願いします。"

            kwargs = {
                "modelId": model_id,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"document": {"name": "PDF", "format": "pdf", "source": {"bytes": pdf_content}}},
                        {"text": prompt}
                    ]
                }]
            }

            retry_count = 0
            current_client = next(self.client_cycle)

            while retry_count <= self.max_retries:
                try:
                    response = current_client.converse(**kwargs)
                    if (output := response.get("output")) and (message := output.get("message")):
                        for content in message.get("content", []):
                            if "text" in content:
                                return content["text"]
                    return ""
                except ClientError as e:
                    error_code = e.response["Error"]["Code"]
                    if error_code in ["ThrottlingException", "ServiceUnavailable", "InternalServerError"]:
                        if retry_count == self.max_retries:
                            raise ModelError(f"Max retries ({self.max_retries}) exceeded. Last error: {str(e)}")

                        # クライアントローテーション
                        prev_client = current_client
                        current_client = self._rotate_client(current_client)
                        
                        wait_time = self._exponential_backoff(retry_count)
                        self.logger.log(
                            f"PDF Error on {prev_client.meta.profile_name}: {str(e)}. "
                            f"Retrying with {current_client.meta.profile_name} in {wait_time}s..."
                        )
                        
                        time.sleep(wait_time)
                        retry_count += 1
                    else:
                        raise ModelError(f"API error: {str(e)}")
                except Exception as e:
                    raise ModelError(f"Unexpected error: {str(e)}")

        except Exception as e:
            raise ModelError(f"PDF processing failed: {str(e)}")
