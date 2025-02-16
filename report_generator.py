from datetime import datetime
import markdown2
import cssutils
import logging
from typing import Tuple

# CSSパーサーのログを抑制
cssutils.log.setLevel(logging.CRITICAL)


class ReportGenerator:
    def __init__(self):
        """レポート生成器の初期化"""
        self.css = """
        body {
            font-family: 'Helvetica Neue', Arial, 'Hiragino Kaku Gothic ProN', 'Hiragino Sans', Meiryo, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
            margin-top: 30px;
        }
        h2 {
            color: #34495e;
            border-left: 4px solid #3498db;
            padding-left: 10px;
            margin-top: 25px;
        }
        p {
            margin: 15px 0;
            text-align: justify;
        }
        .metadata {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 30px;
        }
        .content {
            background-color: #fff;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        """

    def generate_report(
        self, markdown_text: str, base_path: str, title: str
    ) -> Tuple[str, str]:
        """
        マークダウンテキストからレポートを生成（HTML と Markdown）

        Args:
            markdown_text: 元のマークダウンテキスト
            base_path: 出力ファイルのベースパス（拡張子なし）
            title: レポートのタイトル

        Returns:
            Tuple[str, str]: 生成されたHTMLとMarkdownファイルのパス
        """
        # ファイルパスの設定
        html_path = f"{base_path}.html"
        md_path = f"{base_path}.md"

        # Markdownファイルの生成
        self._save_markdown(markdown_text, md_path, title)

        # HTMLファイルの生成
        self._save_html(markdown_text, html_path, title)

        return html_path, md_path

    def _save_markdown(self, markdown_text: str, output_path: str, title: str) -> None:
        """
        マークダウンファイルを保存
        """
        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

        markdown_content = f"""# {title}

作成日時: {current_time}

{markdown_text}
"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

    def _save_html(self, markdown_text: str, output_path: str, title: str) -> None:
        """
        HTMLファイルを保存
        """
        # マークダウンをHTMLに変換
        html_content = markdown2.markdown(markdown_text)

        # 現在時刻
        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

        # HTML文書の構造
        html_document = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
            {self.css}
            </style>
        </head>
        <body>
            <div class="content">
                <h1>{title}</h1>
                <div class="metadata">
                    作成日時: {current_time}
                </div>
                {html_content}
            </div>
        </body>
        </html>
        """

        # HTMLファイルとして保存
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_document)
