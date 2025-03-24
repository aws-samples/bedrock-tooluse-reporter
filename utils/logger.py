import logging
import os
from datetime import datetime


class DualLogger:
    """
    コマンドラインとログファイルの両方に出力するロガークラス
    
    標準出力とファイルの両方にログを出力する機能を提供します。
    ログレベルの動的変更にも対応しています。
    """

    # 有効なログレベル名とそれに対応する logging モジュールの定数のマッピング
    VALID_LOG_LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,  # WARNING の別名
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.CRITICAL,  # CRITICAL の別名
    }

    def __init__(self, timestamp_str: str, log_level="INFO"):
        """
        ロガーを初期化します
        
        指定されたログレベルでロガーを設定し、タイムスタンプに基づいたログファイルを作成します。

        Args:
            timestamp_str: タイムスタンプ文字列（ログファイル名に使用）
            log_level: ロギングレベル（文字列: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'）
                       デフォルト: 'INFO'

        Raises:
            ValueError: 無効なログレベルが指定された場合
        """
        # ログレベル文字列を大文字に変換して正規化
        log_level_upper = log_level.upper()

        # 有効なログレベルかチェック
        if log_level_upper not in self.VALID_LOG_LEVELS:
            valid_levels = ", ".join(self.VALID_LOG_LEVELS.keys())
            raise ValueError(
                f"無効なログレベル: '{log_level}' - 有効なレベルは {valid_levels} です"
            )

        # 文字列からログレベル定数に変換
        numeric_level = self.VALID_LOG_LEVELS[log_level_upper]

        # 現在の日時を取得してフォーマット
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        # ログディレクトリの作成
        log_dir = "log"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # ログファイルのパス
        log_file = os.path.join(log_dir, f"{timestamp}.log")

        # ロガーの設定
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(numeric_level)

        # 既存のハンドラをクリア
        if self.logger.handlers:
            self.logger.handlers.clear()

        # コンソールハンドラの設定
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(console_format)

        # ファイルハンドラの設定
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_format)

        # ハンドラをロガーに追加
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

        self.logger.info(f"ログファイルを作成しました: {log_file}")
        self.logger.info(f"ログレベルを {log_level_upper} に設定しました")

    def set_level(self, log_level):
        """
        ロガーとすべてのハンドラのログレベルを変更する
        
        実行中にログの詳細度を動的に変更するために使用します。

        Args:
            log_level: 新しいロギングレベル（文字列: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'）

        Raises:
            ValueError: 無効なログレベルが指定された場合
        """
        # ログレベル文字列を大文字に変換して正規化
        log_level_upper = log_level.upper()

        # 有効なログレベルかチェック
        if log_level_upper not in self.VALID_LOG_LEVELS:
            valid_levels = ", ".join(self.VALID_LOG_LEVELS.keys())
            raise ValueError(
                f"無効なログレベル: '{log_level}' - 有効なレベルは {valid_levels} です"
            )

        # 文字列からログレベル定数に変換
        numeric_level = self.VALID_LOG_LEVELS[log_level_upper]

        # ロガーとすべてのハンドラのレベルを設定
        self.logger.setLevel(numeric_level)
        for handler in self.logger.handlers:
            handler.setLevel(numeric_level)

        self.logger.info(f"ログレベルを {log_level_upper} に変更しました")

    def debug(self, message):
        """
        デバッグレベルのログを出力
        
        Args:
            message: ログメッセージ
        """
        self.logger.debug(message)

    def info(self, message):
        """
        情報レベルのログを出力
        
        Args:
            message: ログメッセージ
        """
        self.logger.info(message)

    def warning(self, message):
        """
        警告レベルのログを出力
        
        Args:
            message: ログメッセージ
        """
        self.logger.warning(message)

    def error(self, message):
        """
        エラーレベルのログを出力
        
        Args:
            message: ログメッセージ
        """
        self.logger.error(message)

    def critical(self, message):
        """
        重大エラーレベルのログを出力
        
        Args:
            message: ログメッセージ
        """
        self.logger.critical(message)
