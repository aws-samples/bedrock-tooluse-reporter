# logger.py
import sys
import logging
from datetime import datetime
import os
from typing import Optional


class DualLogger:
    """
    コンソールとファイルの両方に出力するロガークラス
    
    このクラスは、研究プロセス中のメッセージをコンソールとログファイルの
    両方に出力するためのインターフェースを提供します。
    """
    
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
        
        # 既存のハンドラをクリア（複数回の初期化を防止）
        if self.logger.handlers:
            self.logger.handlers.clear()

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
        
        大きなセクションの開始を示すタイトルを出力します。

        Args:
            title: セクションのタイトル
        """
        self.logger.info(f"\n=== {title} ===\n")

    def subsection(self, title: str):
        """
        サブセクションタイトルを出力
        
        セクション内のサブセクションの開始を示すタイトルを出力します。

        Args:
            title: サブセクションのタイトル
        """
        self.logger.info(f"\n--- {title} ---\n")

    def get_log_file_path(self) -> str:
        """
        ログファイルのパスを取得
        
        Returns:
            str: 現在のログファイルの絶対パス
        """
        return self.log_file
        
    def truncate_text(self, text: str, max_length: int = 500) -> str:
        """
        テキストを指定された長さに切り詰める
        
        長いテキストをログに出力する前に適切な長さに切り詰めます。
        
        Args:
            text: 切り詰めるテキスト
            max_length: 最大長（デフォルト: 500文字）
            
        Returns:
            str: 切り詰められたテキスト（必要な場合は「...」が追加される）
        """
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
        
    def log_summary(self, text: str, max_length: int = 500):
        """
        テキストの要約をログに出力
        
        長いテキストの要約（先頭部分）をログに出力します。
        
        Args:
            text: 要約するテキスト
            max_length: 最大長（デフォルト: 500文字）
        """
        summary = self.truncate_text(text, max_length)
        self.log(summary)
