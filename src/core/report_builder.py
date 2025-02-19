"""
Report Builder Module

This module contains the ReportBuilder class which is responsible for generating
final research reports in both HTML and Markdown formats. It processes collected
research data and creates well-structured, comprehensive reports with proper
formatting and styling.

Features:
1. Markdown to HTML conversion
2. Custom CSS styling
3. Multiple output formats (HTML and Markdown)
4. Structured report generation with proper sections
"""

from datetime import datetime
import os
from typing import Dict, List, Tuple
import markdown2
import cssutils
import logging
from ..utils.exceptions import ReportGenerationError
from ..config.settings import MODEL_CONFIG, PRIMARY_MODEL, PROMPT_CONFIG

# Suppress CSS parser logs
cssutils.log.setLevel(logging.CRITICAL)


class ReportBuilder:
    def __init__(self, model, logger):
        """
        レポートビルダーの初期化

        Args:
            model: BedrockModelインスタンス
            logger: ロガーインスタンス
        """
        self.model = model
        self.logger = logger
        self.css = self._get_default_css()

    def generate_final_report(
        self, research_text: str, strategy_text: str, user_prompt: str
    ) -> str:
        """
        最終レポートを生成

        Args:
            research_text: 収集した研究データ
            strategy_text: 調査戦略テキスト
            user_prompt: ユーザーのプロンプト

        Returns:
            str: 生成されたレポートテキスト

        Raises:
            ReportGenerationError: レポート生成時のエラー
        """
        try:
            self.logger.section("最終レポート生成")
            final_messages = self._create_final_messages(research_text)
            report_prompt = self._create_report_prompt(user_prompt, strategy_text)

            final_report_text = self._get_complete_response(
                final_messages,
                report_prompt,
            )

            self.logger.section("最終レポート")
            self.logger.log(final_report_text)

            return final_report_text

        except Exception as e:
            raise ReportGenerationError(f"Error generating final report: {str(e)}")

    def save_report(self, report_text: str, title: str) -> Tuple[str, str]:
        """
        レポートをファイルに保存

        Args:
            report_text: レポートのテキスト
            title: レポートのタイトル

        Returns:
            Tuple[str, str]: 生成されたHTMLとMarkdownファイルのパス

        Raises:
            ReportGenerationError: レポート保存時のエラー
        """
        try:
            self.logger.section("レポートの保存")

            # 出力ディレクトリの作成
            output_dir = 'reports'
            os.makedirs(output_dir, exist_ok=True)

            # ファイル名の生成
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_filename = os.path.join(output_dir, f"report_{timestamp}")

            # レポートの保存
            html_path = self._save_html(report_text, f"{base_filename}.html", title)
            md_path = self._save_markdown(report_text, f"{base_filename}.md", title)

            self.logger.log(f"HTMLレポートを生成しました: {html_path}")
            self.logger.log(f"Markdownレポートを生成しました: {md_path}")

            return html_path, md_path

        except Exception as e:
            raise ReportGenerationError(f"Error saving report: {str(e)}")

    def _get_complete_response(
        self, messages: List[Dict], report_prompt: str, max_attempts: int = 10
    ) -> str:
        """完全なレスポンスを取得"""
        complete_response = ""
        last_markers = ["レポートの終了", "レポートは終了", "レポートを終了"]
        attempt = 0
        prompt_text = report_prompt

        while attempt < max_attempts:
            if attempt != 0:
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": '調査戦略に基づいて、次の章をお願いします。調査戦略に基づいた場合、次の章立てが無い場合は、「レポートの終了」と呟いてください。'
                            }
                        ],
                    }
                ]

            response = self.model.generate_response(
                MODEL_CONFIG[PRIMARY_MODEL],
                messages,
                [{"text": prompt_text}],
                {
                    'temperature': PROMPT_CONFIG['temperature']['default'],
                    'maxTokens': PROMPT_CONFIG['max_tokens'],
                },
            )

            current_text = response['output']['message']['content'][0]['text']
            complete_response += current_text
            prompt_text += "\n\n" + current_text

            if any(marker in current_text[-20:] for marker in last_markers):
                break

            attempt += 1

        return complete_response

    def _create_final_messages(self, research_text: str) -> List[Dict]:
        """最終メッセージの作成"""
        return [
            {
                "role": "user",
                "content": [
                    {
                        "text": f'{research_text}\n\nこれでレポートを書いてください。各章における説明は箇条書きではなくすべて文章とした上で、詳細なコンテキストを落とす事無く詳細なレポートとしてまとめてください。ここから繰り返し質問します。調査戦略にまとめた章ごとに詳細に長文を応答してください。章ごとに、続きは私から訪ねます。最終的にすべての章立ての情報を出力し終わった場合は、ひとこと「レポートの終了」と呟いてください。'
                    }
                ],
            }
        ]

    def _create_report_prompt(self, user_prompt: str, strategy_text: str) -> str:
        """レポート生成プロンプトの作成"""
        return f'''あなたは優秀なリサーチャーです。
あなたは「{user_prompt}」 という調査依頼を受けとっています。
そして、調査の仕方については「{strategy_text}」で定義されています。
必要な情報はユーザーが提供します。
マークダウン形式のレポートを作成してください。
以下の点に注意してレポートを作成してください：

* ナレーティブに文章を書く。安易に箇条書きを用いない
* 客観的なデータ、特に数字を用いた分析に基づいた論述を用いる
* 複数の視点からの考察。ただし視点の主体は明らかにする
* 明確な構造と論理的な展開を心がけてください。突飛な話は読者が戸惑います
* 具体例や事例の適切な活用をしてください。具体例は説得力が増します
* 結論の妥当性と説得力を意識して書いてください
* 箇条書きを使う場合は**必ずその下に詳細な説明を入れて**レポートの主張を明瞭にしてください
'''

    def _get_default_css(self) -> str:
        """デフォルトのCSSスタイルを取得"""
        return """
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

    def _save_markdown(self, markdown_text: str, output_path: str, title: str) -> str:
        """Markdownファイルの保存"""
        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')
        markdown_content = f"""# {title}

作成日時: {current_time}

{markdown_text}
"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        return output_path

    def _save_html(self, markdown_text: str, output_path: str, title: str) -> str:
        """HTMLファイルの保存"""
        html_content = markdown2.markdown(markdown_text)
        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

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

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_document)
        return output_path
