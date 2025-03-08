"""
Bedrock モデルの設定と操作を担当するクラス
"""

import boto3
from botocore.config import Config
import time
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError
from ..utils.exceptions import ModelError
from ..config.settings import LLM_CONNECTION
import logging


class BedrockModel:
    """
    AWS Bedrock APIを使用してLLMモデルとの対話を処理するクラス

    このクラスは、AWS Bedrockサービスへのリクエストを管理し、
    エラー処理と再試行ロジックを提供します。
    """

    def __init__(self,logger):
        """
        Bedrock クライアントの初期化

        設定されたタイムアウト値でBedrock RuntimeクライアントをセットアップしLLM接続設定を適用します。
        """
        self.client = boto3.client(
            'bedrock-runtime',
            config=Config(
                connect_timeout=LLM_CONNECTION['timeout'],
                read_timeout=LLM_CONNECTION['timeout'],
            ),
        )
        self.max_retries = LLM_CONNECTION['max_retries']
        self.base_delay = LLM_CONNECTION['base_delay']
        self.max_delay = LLM_CONNECTION['max_delay']
        self.logger = logger

    def _exponential_backoff(self, retry_count: int) -> float:
        """
        指数バックオフの待機時間を計算

        リトライ回数に基づいて、次の試行までの待機時間を指数関数的に増加させます。
        これにより、一時的なサービス障害からの回復が容易になります。

        Args:
            retry_count: 現在のリトライ回数

        Returns:
            float: 待機すべき秒数（base_delayと2のretry_count乗の積と、max_delayの小さい方）
        """
        return min(self.max_delay, self.base_delay * (2**retry_count))

    def generate_response(
        self,
        model_id: str,
        messages: List[Dict],
        system_prompt: List[Dict],
        inference_config: Dict[str, Any],
        tool_config: Optional[Dict] = None,
    ) -> Dict:
        """
        AIモデルを使用してレスポンスを生成
        エラー時は指数バックオフでリトライ

        AWS Bedrock APIを呼び出してAIモデルからのレスポンスを取得します。
        一時的なエラーが発生した場合は、指数バックオフ戦略を使用して再試行します。

        Args:
            model_id: 使用するモデルのID
            messages: 会話履歴
            system_prompt: システムプロンプト
            inference_config: 推論設定（temperature、max_tokensなど）
            tool_config: ツール設定（オプション）

        Returns:
            Dict: モデルからのレスポンス

        Raises:
            ModelError: 最大リトライ回数を超えた場合やその他のエラー
        """
        # APIリクエストのパラメータを構築
        kwargs = {
            'modelId': model_id,
            'messages': messages,
            'system': system_prompt,
            'inferenceConfig': inference_config,
        }

        if tool_config:
            kwargs['toolConfig'] = tool_config

        # リトライロジックの実装
        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                response = self.client.converse(**kwargs)
                return response  # 成功したレスポンスを即座に返す
            except ClientError as e:
                error_code = e.response['Error']['Code']
                # 一時的なエラーの場合はリトライ
                if error_code in [
                    'ThrottlingException',
                    'ServiceUnavailable',
                    'InternalServerError',
                ]:
                    if retry_count == self.max_retries:
                        raise ModelError(
                            f"Maximum retries ({self.max_retries}) exceeded. "
                            f"Last error: {str(e)}"
                        )

                    wait_time = self._exponential_backoff(retry_count)
                    self.logger.log(
                        f"Bedrock API error: {str(e)}. Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    retry_count += 1
                else:
                    # その他のエラータイプは即座に例外を発生
                    raise ModelError(f"Bedrock API error: {str(e)}")
            except Exception as e:
                # 予期しないエラー
                raise ModelError(f"Unexpected error during API call: {str(e)}")

    def process_pdf(self, pdf_content: bytes, model_id: str) -> str:
        """
        PDFファイルを処理してテキストを抽出

        PDFファイルをBedrockにアップロードし、AIモデルを使用してテキストを抽出します。

        Args:
            pdf_content: PDFファイルのバイナリコンテンツ
            model_id: 使用するモデルのID

        Returns:
            str: 抽出されたテキスト

        Raises:
            ModelError: PDFの処理中にエラーが発生した場合
        """
        try:
            # PDFファイルをアップロードしてテキストを抽出するためのプロンプト
            prompt = "あなたは優秀なリサーチャーです。PDFの内容から、コンテキストを全て維持した状態で、中の図や文字列を解釈して内容を長文で説明するようにお願いします。"
            
            # APIリクエストのパラメータを構築
            kwargs = {
                'modelId': model_id,
                'messages': [
                    {
                        'role': 'user',
                        'content': [
                            {
                                "document":{
                                    "name": "PDF Document",
                                    "format": "pdf",
                                    "source": {"bytes": pdf_content}
                                }
                            },       
                            {'text': prompt}
                        ]
                    }
                ]
            }
            
            # リトライロジックの実装
            retry_count = 0
            while retry_count <= self.max_retries:
                try:
                    # PDFファイルをアップロードしてテキストを抽出
                    response = self.client.converse(**kwargs)
                    self.logger.log(f"PDF / response: {response}")
                    # レスポンスからテキストを抽出
                    if 'output' in response and 'message' in response['output'] and 'content' in response['output']['message']:
                        for content in response['output']['message']['content']:
                            if 'text' in content:
                                return content['text']
                    
                    # テキストが見つからない場合は空文字列を返す
                    return ""
                    
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    self.logger.log(f"PDF / Bedrock error_code: {error_code}")

                    # 一時的なエラーの場合はリトライ
                    if error_code in [
                        'ThrottlingException',
                        'ServiceUnavailable',
                        'InternalServerError',
                    ]:
                        if retry_count == self.max_retries:
                            raise ModelError(
                                f"Maximum retries ({self.max_retries}) exceeded. "
                                f"Last error: {str(e)}"
                            )

                        wait_time = self._exponential_backoff(retry_count)
                        time.sleep(wait_time)
                        retry_count += 1
                    else:
                        # その他のエラータイプは即座に例外を発生
                        raise ModelError(f"Bedrock API error during PDF processing: {str(e)}")
                except Exception as e:
                    # 予期しないエラー
                    raise ModelError(f"Unexpected error during PDF processing: {str(e)}")
                    
        except Exception as e:
            raise ModelError(f"Error processing PDF: {str(e)}")
