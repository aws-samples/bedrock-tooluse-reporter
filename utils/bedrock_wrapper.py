"""
このコードはプラグインです。コードの公開予定はありません。
"""

import boto3
from botocore.config import Config
import time
from typing import Dict
from botocore.exceptions import ClientError
import threading

# 基本クラスをインポート
from .bedrock import BedrockModel as BaseBedrockModel


class BedrockModel(BaseBedrockModel):
    """
    AWS Bedrock APIを使用してLLMモデルとの対話を処理するクラス

    このクラスは、AWS Bedrockサービスへのリクエストを管理し、
    エラー処理と再試行ロジックを提供します。
    複数のプロファイル（e.g. default, sub1, sub2）をラウンドロビン方式で使用します。
    """

    def __init__(self, logger):
        """
        Bedrock クライアントの初期化

        設定されたタイムアウト値でBedrock Runtimeクライアントをセットアップし、
        LLM接続設定を適用します。複数のプロファイルを初期化します。

        Args:
            logger: ロガーインスタンス
        """
        # 親クラスの__init__は呼び出さず、必要な属性だけ設定
        base_model = BaseBedrockModel(logger)
        self.max_retries = base_model.max_retries
        self.base_delay = base_model.base_delay
        self.max_delay = base_model.max_delay
        self.cache_supported_models = base_model.cache_supported_models
        self.max_cache_blocks = base_model.max_cache_blocks
        self.logger = logger

        # 利用可能なプロファイル名のリスト
        self.profiles = ["default"]

        # 各プロファイル用のクライアントを作成
        self.clients = {}
        for profile in self.profiles:
            self.clients[profile] = boto3.Session(profile_name=profile).client(
                "bedrock-runtime",
                config=Config(
                    connect_timeout=1200,
                    read_timeout=1200,
                ),
            )

        # 現在のプロファイルインデックスとロック（スレッドセーフにするため）
        self.current_profile_index = 0
        self.profile_lock = threading.Lock()

    def _get_next_client(self):
        """
        ラウンドロビン方式で次のクライアントを取得します。

        Returns:
            tuple: (クライアント, プロファイル名)
        """
        with self.profile_lock:
            profile = self.profiles[self.current_profile_index]
            client = self.clients[profile]

            # 次のプロファイルインデックスに更新
            self.current_profile_index = (self.current_profile_index + 1) % len(
                self.profiles
            )

            return client, profile

    def _execute_with_retry(self, **kwargs) -> Dict:
        """
        Bedrock APIリクエストを実行し、必要に応じてリトライする共通メソッド
        ラウンドロビン方式でプロファイルを切り替えます。

        Args:
            **kwargs: Bedrock APIに渡すパラメータ

        Returns:
            Dict: APIからのレスポンス

        Raises:
            Exception: 最大リトライ回数を超えた場合やその他のエラー
        """
        retry_count = 0
        while retry_count <= self.max_retries:
            # ラウンドロビンで次のクライアントを取得
            client, profile = self._get_next_client()

            try:
                self.logger.info(f"Using profile: {profile}")
                response = client.converse(**kwargs)
                return response  # 成功したレスポンスを即座に返す
            except ClientError as e:
                self.logger.info(f"Error with profile {profile}: {e}")
                error_code = e.response["Error"]["Code"]
                # 一時的なエラーの場合はリトライ
                if error_code in [
                    "ThrottlingException",
                    "ServiceUnavailable",
                    "InternalServerError",
                ]:
                    if retry_count == self.max_retries:
                        self.logger.error(
                            f"最大リトライ回数に到達しました。最後のエラーは {str(e)} です。"
                        )
                        raise Exception()

                    wait_time = self._exponential_backoff(retry_count)
                    self.logger.warning(
                        f"Bedrock API error with profile {profile}: {str(e)}. Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    retry_count += 1
                else:
                    self.logger.error(
                        f"Non-retryable error with profile {profile}: {e}"
                    )
                    raise Exception(e)
            except Exception as e:
                self.logger.error(f"Unexpected error with profile {profile}: {e}")
                raise Exception
