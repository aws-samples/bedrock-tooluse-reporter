# logger.py
import sys
import logging
from datetime import datetime
import os


class DualLogger:
    def __init__(self, output_dir: str = 'logs'):
        """
        コンソールとファイルの両方に出力するロガーの初期化

        Args:
            output_dir: ログファイルを保存するディレクトリ
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # ログファイル名に現在時刻を含める
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = os.path.join(output_dir, f'research_log_{timestamp}.txt')

        # ロガーの設定
        self.logger = logging.getLogger('research_logger')
        self.logger.setLevel(logging.INFO)

        # ファイルハンドラの設定
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # コンソールハンドラの設定
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # フォーマッターの設定
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # ハンドラの追加
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log(self, message: str, with_separator: bool = False):
        """
        メッセージをログに出力

        Args:
            message: 出力するメッセージ
            with_separator: 区切り線を追加するかどうか
        """
        if with_separator:
            self.logger.info("\n" + "=" * 50 + "\n")
        self.logger.info(message)

    def section(self, title: str):
        """
        セクションタイトルを出力

        Args:
            title: セクションのタイトル
        """
        self.logger.info(f"\n=== {title} ===\n")

    def subsection(self, title: str):
        """
        サブセクションタイトルを出力

        Args:
            title: サブセクションのタイトル
        """
        self.logger.info(f"\n--- {title} ---\n")

    def get_log_file_path(self) -> str:
        """ログファイルのパスを取得"""
        return self.log_file
