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
5. Source references at the end of each chapter
"""

from datetime import datetime
import os
from typing import Dict, List, Tuple
import markdown2
import cssutils
import logging
from ..utils.exceptions import ReportGenerationError
from ..models.source_reference import SourceReferenceManager
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
        self,
        research_text: str,
        strategy_text: str,
        user_prompt: str,
        source_manager: SourceReferenceManager,
    ) -> str:
        """
        最終レポートを生成

        Args:
            research_text: 収集した研究データ
            strategy_text: 調査戦略テキスト
            user_prompt: ユーザーのプロンプト
            source_manager: ソース参照マネージャー

        Returns:
            str: 生成されたレポートテキスト

        Raises:
            ReportGenerationError: レポート生成時のエラー
        """
        try:
            self.logger.section("最終レポート生成")
            final_messages = self._create_final_messages(research_text, source_manager)
            report_prompt = self._create_report_prompt(user_prompt, strategy_text)

            final_report_text = self._get_complete_response(
                final_messages,
                report_prompt,
                source_manager,
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
        self,
        messages: List[Dict],
        report_prompt: str,
        source_manager: SourceReferenceManager,
        max_attempts: int = 10,
    ) -> str:
        """完全なレスポンスを取得"""
        complete_response = ""
        last_markers = [
            "レポートの終了",
            "レポートは終了",
            "レポートを終了",
            "レポートは完了",
            "レポートの完了",
            "レポートを完了",
        ]
        attempt = 0
        prompt_text = report_prompt
        chapter_references = set()

        while attempt < max_attempts:
            if attempt != 0:
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": "調査戦略に基づいて、今の章内の続きを執筆するか、次の章を執筆してください。全ての調査フレームを終え、続きがない場合は、「レポートの終了」と呟いてください。「次の章へ進むか？」は聞かないでください。"
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

            self.logger.log("レポートの一部引用:")
            summary = (
                current_text[:500] + "..." if len(current_text) > 500 else current_text
            )
            self.logger.log(summary)

            chapter_references.clear()

            complete_response += current_text + "\n\n"
            prompt_text += "\n\n" + current_text

            if any(marker in current_text[-50:] for marker in last_markers):
                break

            attempt += 1

        # Process the text to ensure proper citation format and collect references
        for ref in source_manager.get_all_references():
            citation_mark = f"[※{ref.reference_number}]"
            self.logger.log(f"{citation_mark} : {ref.url} / {ref.title}")
            chapter_references.add(ref)

        #           if citation_mark in complete_response or ref.url in complete_response:
        #               chapter_references.add(ref)
        #               # Replace plain URLs with hyperlinked citations
        #               current_text = complete_response.replace(ref.url, f"[{citation_mark}]({ref.url})")
        #               # Ensure citation marks are properly formatted
        #               current_text = complete_response.replace(
        #                   f"[{ref.reference_number}]",
        #                   citation_mark
        #               )
        #
        # Add chapter references if any were used
        if chapter_references:
            complete_response += "\n\n### 参考文献\n"
            for ref in sorted(
                chapter_references, key=lambda x: x.reference_number or 0
            ):
                complete_response += (
                    f"※{ref.reference_number}. [{ref.title}]({ref.url})\n\n"
                )

        return complete_response

    def _create_final_messages(
        self, research_text: str, source_manager: SourceReferenceManager
    ) -> List[Dict]:
        """最終メッセージの作成"""
        # Create reference information for the prompt
        reference_info = "\n\n利用可能な情報源:\n"
        for ref in source_manager.get_all_references():
            reference_info += f"- [{ref.title}]({ref.url}) [※{ref.reference_number}]\n"

        return [
            {
                "role": "user",
                "content": [
                    {
                        "text": f'''
{research_text}

{reference_info}

これでレポートを書いてください。

ここから繰り返し質問します。
以下の*Rule*に従って出力を続けてください。

#Rule
0: Respond directly without asking questions or seeking clarification. 
1: Do not include statements about waiting for responses or confirmations or questions.
2: Do not include statements about next chapter
3: 章ごとに出力する。続きが繰り返し問い合わせされる。
4: 調査戦略にまとめた"章ごと"に詳細なコンテキストを全て維持する
5: 箇条書きではなく長文、または、表を出力する
6: レポート分は客観的なデータポイントについて詳細に解説し、それを論拠として、考察と推論について述べる順番でロジックを展開する
7: 専門的な説明や具体的な内容、データや数値など詳細なコンテキストは全て維持する
8: 文体はレポート文体で長文とする。
9: 章をまたいで、Report全体の文脈の流れを維持する。
10: 最終的にすべての章立ての情報を出力し終わった場合は、ひとこと「レポートの終了」と呟く。
'''
                        # 11: インターネットの検索からの情報を引用している場合にのみ、該当するURLとハイパーリンクを作ってください。架空の参考文献を作り出さないでください。
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
* レポート分は客観的なデータポイントについて詳細に解説し、それを論拠として、考察と推論について述べる順番でロジックを展開する
* 複数の視点からの考察を行う。ただし視点の主体は明らかにする
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
        h3 {
            color: #34495e;
            border-bottom: 1px solid #3498db;
            padding-bottom: 5px;
            margin-top: 20px;
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
        a {
            color: #3498db;
            text-decoration: none;
            transition: color 0.3s ease;
        }
        a:hover {
            color: #2980b9;
            text-decoration: underline;
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
        # Use markdown2 with extras, but without link-patterns
        html_content = markdown2.markdown(
            markdown_text, extras=['tables', 'fenced-code-blocks']
        )
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
