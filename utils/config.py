class Config:
    """
    アプリケーション設定クラス

    動作モードに応じた各種設定値を管理します。
    短時間モード(short)と長時間モード(long)の2種類があり、
    実行回数や処理量が異なります。
    """

    class DotDict(dict):
        """
        ドット記法でアクセスできるディクショナリクラス
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # ネストされた辞書もDotDictに変換
            for key, value in self.items():
                if isinstance(value, dict):
                    self[key] = Config.DotDict(value)

        def __getattr__(self, key):
            try:
                return self[key]
            except KeyError:
                raise AttributeError(
                    f"'{self.__class__.__name__}' object has no attribute '{key}'"
                )

    def __init__(self, mode="short"):
        """
        設定の初期化

        Args:
            mode: 動作モード（'short'または'long'）
        """
        # Amazon Bedrock の設定
        self.BEDROCK = self.DotDict(
            {
                "PRIMARY_MODEL_ID": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "SECONDARY_MODEL_ID": "us.deepseek.r1-v1:0",
                "MAX_RETRIES": 8,
                "BASE_DELAY": 20,
                "MAX_DELAY": 300,
                "REPORTER": {
                    "MAX_TOKENS": 8192,
                    "TEMPERATURE": 0.5,
                    "TOP_P": 0.9,
                },
                "PERSPECTIVE_EXPLORER": {
                    "MAX_TOKENS": 8192,
                    "TEMPERATURE": 1.0,
                    "TOP_P": 0.9,
                },
                "CACHE_SUPPORTED_MODELS": [
                    "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                    "anthropic.claude-3-7-sonnet-20250219-v1:0",
                ],
                "MAX_CACHE_BLOCKS": 4,
            }
        )
        self.PRIMARY_MODEL_ID: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        self.SECONDARY_MODEL_ID: str = "us.deepseek.r1-v1:0"

        # 各プロセスの最大実行回数（モードによって変化）
        self.MAX_CONTEXT_CHECK_COUNT: int = 5 if mode == "short" else 10
        self.MAX_PERSPECTIVE_EXPLORER_COUNT: int = 3 if mode == "short" else 5
        self.MAX_DATA_SURVEYOR_COUNT: int = 20 if mode == "short" else 40

        # 各種ディレクトリパス
        self.REPORT_DIR: str = "./report"
        self.CONVERSATION_DIR: str = "./conversation"
        self.LOG_DIR: str = "./log"

        # 各プロセスで使用するツール
        self.CONTEXT_CHECK_REQUESTED_TOOLS = ["search", "get_content", "is_finished"]
        self.DATA_SURVEYOR_REQUESTED_TOOLS = [
            "search",
            "get_content",
            "image_search",
            "generate_graph",
            "is_finished",
        ]
        self.REPORT_WRITER_REQUESTED_TOOLS = [
            "write",
            "is_finished",
        ]

        # 画像関連の設定
        self.IMAGE_CONFIG = self.DotDict(
            {
                "MAX_IMAGES": 10,  # 1回の検索で取得する最大画像数
                "MAX_SIZE": 5 * 1024 * 1024,  # 画像の最大サイズ（5MB）
                "ALLOWED_FORMATS": (
                    "jpeg",
                    "png",
                    "gif",
                    "webp",
                ),
            }
        )

        # ドキュメント関連の設定
        self.DOCUMENT_CONFIG = self.DotDict(
            {
                "BEDROCK_MAX_SIZE": 4.5
                * 1024
                * 1024,  # Bedrock APIの最大サイズ（up to 4.5MB in rawdata）
                "ALLOWED_FORMATS": (
                    "pdf",
                    "csv ",
                    "doc",
                    "docx",
                    "xls",
                    "xlsx",
                    "html",
                    "txt",
                    "md",
                ),
            }
        )

    def __getitem__(self, key):
        """
        ディクショナリのようにアクセスできるようにする

        Args:
            key: アクセスしたい属性名

        Returns:
            属性の値

        Raises:
            KeyError: 指定されたキーが存在しない場合
        """
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(f"設定項目 '{key}' は存在しません")

    def __getattr__(self, name):
        """
        存在しない属性にアクセスした場合のエラーハンドリング

        Args:
            name: アクセスしようとした属性名

        Raises:
            AttributeError: 指定された属性が存在しない場合
        """
        raise AttributeError(f"設定項目 '{name}' は存在しません")
