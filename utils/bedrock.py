"""
Bedrock モデルの設定と操作を担当するクラス
"""

import boto3
from botocore.config import Config as BotoConfig
from .config import Config
import time
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError


class BedrockModel:
    """
    AWS Bedrock APIを使用してLLMモデルとの対話を処理するクラス

    このクラスは、AWS Bedrockサービスへのリクエストを管理し、
    エラー処理と再試行ロジックを提供します。
    """

    def __init__(self, logger, mode="short"):
        """
        Bedrock クライアントの初期化

        設定されたタイムアウト値でBedrock Runtimeクライアントをセットアップし、
        LLM接続設定を適用します。

        Args:
            logger: ロガーインスタンス
            mode: 動作モード（デフォルト: "short"）
        """
        # Bedrockクライアントを作成
        self.client = boto3.client(
            "bedrock-runtime",
            config=BotoConfig(
                connect_timeout=1200,  # 接続タイムアウト: 20分
                read_timeout=1200,  # 読み取りタイムアウト: 20分
            ),
        )
        self.config = Config(mode)
        self.max_retries = self.config.BEDROCK.MAX_RETRIES
        self.base_delay = self.config.BEDROCK.BASE_DELAY
        self.max_delay = self.config.BEDROCK.MAX_DELAY
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

    def _execute_with_retry(self, **kwargs) -> Dict:
        """
        Bedrock APIリクエストを実行し、必要に応じてリトライする共通メソッド

        一時的なエラーが発生した場合は指数バックオフでリトライします。

        Args:
            **kwargs: Bedrock APIに渡すパラメータ

        Returns:
            Dict: APIからのレスポンス

        Raises:
            Exception: 最大リトライ回数を超えた場合やその他のエラー
        """
        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                response = self.client.converse(**kwargs)
                return response  # 成功したレスポンスを即座に返す
            except ClientError as e:
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
                        f"Bedrock API error: {str(e)}. Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    retry_count += 1
                else:
                    self.logger.error(f"Non-retryable error: {e}")
                    raise Exception(e)
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                raise Exception

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

        Args:
            model_id: 使用するモデルのID
            messages: 会話履歴
            system_prompt: システムプロンプト
            inference_config: 推論設定（temperature、max_tokensなど）
            tool_config: ツール設定（オプション）

        Returns:
            Dict: モデルからのレスポンス
        """
        # APIリクエストのパラメータを構築
        kwargs = {
            "modelId": model_id,
            "messages": messages,
            "system": system_prompt,
            "inferenceConfig": inference_config,
        }

        if tool_config:
            kwargs["toolConfig"] = tool_config

        # 共通のリトライロジックを使用
        return self._execute_with_retry(**kwargs)

    def describe_document(
        self,
        document_content: bytes,
        document_name: str,
        document_type: str,
        model_id: str,
    ) -> str:
        """
        ドキュメント（PDF・画像など）を処理してテキストを抽出

        ドキュメントをBedrockにアップロードし、AIモデルを使用してテキストを抽出します。
        エラー時は指数バックオフでリトライします。

        Args:
            document_content: ドキュメントのバイナリコンテンツ
            document_name: ドキュメント名
            document_type: ドキュメントの種類（'pdf', 'jpeg', 'png'など）
            model_id: 使用するモデルのID

        Returns:
            str: 抽出されたテキスト
        """
        # ドキュメントタイプに応じたシステムプロンプトを設定
        document_type = document_type.lower()
        if document_type in self.config.IMAGE_CONFIG.ALLOWED_FORMATS:
            system_prompt = """あなたは優秀な視覚障害者向けの画像解説者です。
明確で詳細な説明を提供し、視覚情報をアクセシブルにします。
与えた画像の内容を詳細に分析し、視覚的な要素、テキスト、図表などを含む全ての情報を詳しく説明してください。画像に含まれる全ての重要な情報を見落とさないようにしてください。
説明文以外の出力は不要です。説明だけを出力してください。"""
            kwargs = {
                "modelId": model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": {
                                    "format": document_type,
                                    "source": {"bytes": document_content},
                                }
                            },
                            {"text": document_name},
                        ],
                    }
                ],
                "system": [{"text": system_prompt}],
            }
        elif (
            document_type in self.config.DOCUMENT_CONFIG.ALLOWED_FORMATS
        ):  # pdf やその他のドキュメント
            user_prompt = """あなたは優秀なコンテンツ抽出者です。
ヘッダーやフッターなどの、記事とは関係ない文字列などを除去した上で、一言一句漏らさず全ての情報を抽出してください。
情報の取捨選択はこの後に行うため決して要約をしてはいけません。語調や些末な情報も重要だからです。全て抜きだしてください。"""
            kwargs = {
                "modelId": model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "document": {
                                    "format": document_type,
                                    "name": document_name,
                                    "source": {"bytes": document_content},
                                }
                            },
                            {"text": user_prompt},
                        ],
                    }
                ],
            }

        # 共通のリトライロジックを使用
        response = self._execute_with_retry(**kwargs)

        # レスポンスからテキストを抽出
        if (
            "output" in response
            and "message" in response["output"]
            and "content" in response["output"]["message"]
        ):
            for content in response["output"]["message"]["content"]:
                if "text" in content:
                    return content["text"]

        # テキストが見つからない場合は空文字列を返す
        return "Error: 説明の取得に失敗しました"

    def describe_html(
        self,
        content: str,
        model_id: str,
    ):
        """
        HTMLコンテンツから本質的な情報を抽出

        HTMLから抽出したテキストを処理し、重要な情報だけを抽出します。

        Args:
            content: HTMLから抽出したテキスト
            model_id: 使用するモデルのID

        Returns:
            str: 抽出された本質的な情報
        """
        system_prompt = """あなたは与えたテキストから本質的な情報を抜き取るプロフェッショナルです。
与えたテキストは html から抽出したテキストです。このテキストから広告などを抜いた、このページで言いたかった本質的な情報だけを全てもれなく抜き取ってください。"""
        kwargs = {
            "modelId": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"text": content},
                    ],
                }
            ],
            "system": [{"text": system_prompt}],
        }
        # 共通のリトライロジックを使用
        response = self._execute_with_retry(**kwargs)

        # レスポンスからテキストを抽出
        if (
            "output" in response
            and "message" in response["output"]
            and "content" in response["output"]["message"]
        ):
            for content in response["output"]["message"]["content"]:
                if "text" in content:
                    return content["text"]
