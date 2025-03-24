import argparse
import markdown
import re
import os
import time
import base64
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options


def parse_arguments():
    """
    コマンドライン引数を解析する

    レポート生成に必要なコマンドライン引数を設定し、解析します。

    Returns:
        argparse.Namespace: 解析された引数
    """
    parser = argparse.ArgumentParser(description="Generate Report")

    parser.add_argument(
        "--prompt", "-p", type=str, required=True, help="レポートタイトル(必須)"
    )

    parser.add_argument(
        "--resume-file",
        "-r",
        type=str,
        required=False,
        help="レジュームする際に convesation/YYYYMMDD_HHMISS.yaml のファイルパスを入力する",
    )

    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        required=False,
        default="short",
        choices=["short", "long"],
        help="short or long",
    )

    parser.add_argument(
        "--log-level",
        "-l",
        type=str,
        default="INFO",
        choices=[
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
            "debug",
            "info",
            "warning",
            "error",
            "critical",
        ],
        help="ログレベルを指定します (デフォルト: INFO)",
    )

    return parser.parse_args()


def md2html(report_markdown_path, logger):
    """
    マークダウンをHTMLに変換
    
    マークダウンファイルを読み込み、HTMLに変換します。
    Mermaid図を適切に処理し、スタイリングを適用します。
    
    Args:
        report_markdown_path: マークダウンファイルのパス
        logger: ロガーインスタンス
        
    Returns:
        str: 生成されたHTMLファイルのパス
    """
    logger.info("markdown から html を生成します")
    with open(report_markdown_path, "rt") as f:
        markdown_text = f.read()
    mermaid_blocks = []
    placeholder_template = "MERMAID_PLACEHOLDER_{}"

    def extract_mermaid(match):
        """
        Mermaid図を抽出してプレースホルダーに置き換える
        
        Args:
            match: 正規表現マッチオブジェクト
            
        Returns:
            str: プレースホルダー文字列
        """
        content = match.group(1).strip()
        mermaid_blocks.append(content)
        placeholder = placeholder_template.format(len(mermaid_blocks) - 1)
        return f"\n\n{placeholder}\n\n"

    # Mermaid図を抽出してプレースホルダーに置き換え
    processed_markdown = re.sub(
        r"```mermaid\n(.*?)\n```", extract_mermaid, markdown_text, flags=re.DOTALL
    )

    # ハッシュタグとヘッダーの区別
    lines = processed_markdown.split("\n")
    for i in range(len(lines)):
        # 見出しのパターン: 行頭の#（複数可）の後にスペースがある場合
        if re.match(r"^#+\s", lines[i]):
            # 見出しはそのまま（何もしない）
            pass
        # ハッシュタグのパターン: 行頭の単一の#の後にスペースがない場合
        elif re.match(r"^#[^\s#]", lines[i]):
            # #の前にバックスラッシュを追加してエスケープ
            lines[i] = "\\" + lines[i]

    processed_markdown = "\n".join(lines)

    # マークダウンをHTMLに変換
    html = markdown.markdown(processed_markdown, extensions=["fenced_code", "tables"])

    # 目次の階層構造を手動で修正し、同時に見出しのIDも修正する
    def fix_html_structure(html):
        """
        HTMLの構造を修正
        
        目次の階層構造を修正し、見出しにIDを追加します。
        
        Args:
            html: 修正前のHTML
            
        Returns:
            str: 修正後のHTML
        """
        # 目次部分を検出
        toc_match = re.search(r'<h2>目次</h2>\s*<ul>(.*?)</ul>', html, re.DOTALL)
        if not toc_match:
            return html

        toc_content = toc_match.group(1)
        items = re.findall(r'<li>(.*?)</li>', toc_content, re.DOTALL)

        # 新しい階層構造のHTMLを構築
        new_toc = '<h2 id="目次">目次</h2>\n<div class="toc-container">\n<ul class="toc-list">\n'

        # メインレベルの項目（1., 2., など）
        main_items = []
        sub_items = {}

        # リンクとIDのマッピング
        id_mapping = {}

        for item in items:
            match = re.search(r'<a href="#(.*?)">(.*?)</a>', item)
            if match:
                href = match.group(1)
                text = match.group(2)

                # 項目のレベルを判断
                if re.match(r'\d+\.\s', text):
                    # メインレベル項目
                    main_items.append((href, text))
                    current_main = href
                elif re.match(r'\d+\.\d+\s', text):
                    # サブレベル項目
                    if current_main not in sub_items:
                        sub_items[current_main] = []
                    sub_items[current_main].append((href, text))

                # IDマッピングを作成
                id_mapping[text] = href

        # 階層構造を構築
        for main_href, main_text in main_items:
            new_toc += f'  <li><a href="#{main_href}" class="toc-main">{main_text}</a>'

            if main_href in sub_items:
                new_toc += '\n    <ul class="toc-sub">\n'
                for sub_href, sub_text in sub_items[main_href]:
                    new_toc += f'      <li><a href="#{sub_href}" class="toc-sub-item">{sub_text}</a></li>\n'
                new_toc += '    </ul>\n'

            new_toc += '</li>\n'

        new_toc += '</ul>\n</div>'

        # 目次を置き換え
        html = html.replace(toc_match.group(0), new_toc)

        # 見出しのIDを修正
        for text, id_value in id_mapping.items():
            # 見出しのパターンを検索
            heading_pattern = f'<h\\d>({re.escape(text)})</h\\d>'
            html = re.sub(
                heading_pattern,
                f'<h2 id="{id_value}" class="section-heading">\\1</h2>',
                html,
            )

        return html

    # HTMLの構造を修正
    html = fix_html_structure(html)

    # Mermaid図のプレースホルダーを実際のdivに置き換え
    for i, content in enumerate(mermaid_blocks):
        placeholder = placeholder_template.format(i)
        mermaid_div = f'<div class="mermaid">{content}</div>'
        html = html.replace(f"<p>{placeholder}</p>", mermaid_div)

    # ファイル名からドキュメントタイトルを取得（拡張子なし）
    document_title = os.path.basename(report_markdown_path).replace('.md', '')

    # HTMLテンプレート（スタイルとスクリプトを含む）
    html_template = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{document_title}</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&family=Noto+Serif+JP:wght@400;700&display=swap">
    <style>
        :root {{
            --primary-color: #2c3e50;
            --secondary-color: #3498db;
            --accent-color: #e74c3c;
            --background-color: #f9f9f9;
            --text-color: #333;
            --border-color: #ddd;
            --heading-color: #2c3e50;
            --link-color: #3498db;
            --link-hover-color: #2980b9;
            --code-background: #f8f8f8;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        html {{
            scroll-behavior: smooth;
        }}
        
        body {{
            font-family: 'Noto Sans JP', sans-serif;
            line-height: 1.7;
            color: var(--text-color);
            background-color: var(--background-color);
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        /* ヘッダー */
        header {{
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }}
        
        /* 見出し */
        h1, h2, h3, h4, h5, h6 {{
            font-family: 'Noto Serif JP', serif;
            color: var(--heading-color);
            margin: 2rem 0 1rem;
            line-height: 1.3;
        }}
        
        h1 {{
            font-size: 2.5rem;
            margin-top: 0;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--secondary-color);
        }}
        
        h2 {{
            font-size: 2rem;
            padding-bottom: 0.3rem;
            border-bottom: 1px solid var(--border-color);
        }}
        
        h3 {{
            font-size: 1.5rem;
            color: var(--secondary-color);
        }}
        
        h4 {{
            font-size: 1.3rem;
        }}
        
        /* 段落 */
        p {{
            margin-bottom: 1.5rem;
            text-align: justify;
        }}
        
        /* リンク */
        a {{
            color: var(--link-color);
            text-decoration: none;
            transition: color 0.2s;
        }}
        
        a:hover {{
            color: var(--link-hover-color);
            text-decoration: underline;
        }}
        
        /* リスト */
        ul, ol {{
            margin: 1rem 0 1.5rem 1.5rem;
        }}
        
        li {{
            margin-bottom: 0.5rem;
        }}
        
        /* 目次 */
        .toc-container {{
            background-color: rgba(236, 240, 241, 0.7);
            border-radius: 8px;
            padding: 1.5rem;
            margin: 2rem 0;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
        }}
        
        .toc-list {{
            list-style-type: none;
            margin-left: 0;
        }}
        
        .toc-list li {{
            margin-bottom: 0.7rem;
        }}
        
        .toc-main {{
            font-weight: 500;
            color: var(--primary-color);
        }}
        
        .toc-sub {{
            margin-top: 0.5rem;
            margin-left: 1.5rem !important;
            list-style-type: none;
        }}
        
        .toc-sub-item {{
            font-size: 0.95rem;
            color: var(--secondary-color);
        }}
        
        /* コード */
        pre, code {{
            font-family: 'Courier New', monospace;
            background-color: var(--code-background);
            border-radius: 4px;
            padding: 0.2rem 0.4rem;
            font-size: 0.9rem;
        }}
        
        pre {{
            padding: 1rem;
            overflow-x: auto;
            margin-bottom: 1.5rem;
            border-left: 4px solid var(--secondary-color);
        }}
        
        pre code {{
            padding: 0;
            background-color: transparent;
        }}
        
        /* 表 */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.5rem 0;
        }}
        
        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        
        th {{
            background-color: rgba(52, 152, 219, 0.1);
            font-weight: 500;
        }}
        
        tr:hover {{
            background-color: rgba(52, 152, 219, 0.05);
        }}
        
        /* 引用 */
        blockquote {{
            border-left: 4px solid var(--secondary-color);
            padding-left: 1rem;
            margin: 1.5rem 0;
            color: #555;
            font-style: italic;
        }}
        
        /* セクション見出し */
        .section-heading {{
            margin-top: 3rem;
            padding-top: 1rem;
        }}
        
        /* Mermaid図 */
        .mermaid {{
            margin: 2rem 0;
            text-align: center;
            background-color: white;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
        }}
        
        /* mermaidのテキストを読みやすく */
        .mermaid text {{
            font-family: 'Noto Sans JP', sans-serif !important;
            font-size: 14px !important;
        }}
        
        /* mermaidの線を少し太く */
        .mermaid .flowchart-link {{
            stroke-width: 2px !important;
        }}
        
        /* レスポンシブ対応 */
        @media (max-width: 768px) {{
            body {{
                padding: 1rem;
            }}
            
            h1 {{
                font-size: 2rem;
            }}
            
            h2 {{
                font-size: 1.7rem;
            }}
            
            h3 {{
                font-size: 1.4rem;
            }}
        }}
    </style>
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            mermaid.initialize({{ 
                startOnLoad: true,
                theme: 'default',
                flowchart: {{ curve: 'basis' }},
                securityLevel: 'loose'
            }});
            
            // ページ内リンクのスムーススクロール
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
                anchor.addEventListener('click', function (e) {{
                    e.preventDefault();
                    
                    const targetId = this.getAttribute('href');
                    const targetElement = document.querySelector(targetId);
                    
                    if (targetElement) {{
                        window.scrollTo({{
                            top: targetElement.offsetTop - 20,
                            behavior: 'smooth'
                        }});
                        
                        // URLにハッシュを追加
                        history.pushState(null, null, targetId);
                    }}
                }});
            }});
        }});
    </script>
</head>
<body>
{html}
<footer>
    <p style="text-align: center; margin-top: 3rem; color: #777; font-size: 0.9rem; border-top: 1px solid var(--border-color); padding-top: 1rem;">
        © {datetime.datetime.now().year} | 自動生成されたドキュメント
    </p>
</footer>
</body>
</html>"""

    # HTMLファイルを保存
    report_html_path = report_markdown_path.replace(".md", ".html")
    with open(report_html_path, "wt") as f:
        f.write(html_template)
    logger.info("markdown から html を生成しました")
    return report_html_path


def html2pdf(report_html_path, logger):
    """
    HTMLをPDFに変換

    HTMLファイルを読み込み、PDFに変換します。
    Seleniumを使用してMermaid図を正しくレンダリングします。

    Args:
        report_html_path: HTMLファイルのパス
        logger: ロガーインスタンス

    Returns:
        str: 生成されたPDFファイルのパス
    """
    logger.info("html から pdf を生成します")
    report_pdf_path = report_html_path.replace(".html", ".pdf")

    # Chromeのオプション設定
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # ヘッドレスモード
    chrome_options.add_argument("--disable-gpu")  # GPUを使用しない
    chrome_options.add_argument("--no-sandbox")  # サンドボックスを無効化
    chrome_options.add_argument("--disable-dev-shm-usage")  # /dev/shmパーティションの使用を無効化
    chrome_options.add_argument("--window-size=1920,1080")  # 十分な大きさに設定

    # Chromeドライバーを初期化
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=chrome_options
    )

    # HTMLファイルを読み込み
    absolute_path = os.path.abspath(report_html_path)
    driver.get(f"file:///{absolute_path}")

    print("Waiting for Mermaid diagrams to render...")
    # Mermaidの描画を待つ
    time.sleep(5)

    # 印刷設定
    print_options = {
        "landscape": False,
        "displayHeaderFooter": False,
        "printBackground": True,
        "preferCSSPageSize": True,
        "pageSize": "A4",
    }

    print("Generating PDF...")
    # PDFとして印刷
    pdf_data = driver.execute_cdp_cmd("Page.printToPDF", print_options)

    # バイナリデータをファイルに保存
    with open(report_pdf_path, "wb") as f:
        # Base64でデコードする
        pdf_bytes = base64.b64decode(pdf_data["data"])
        f.write(pdf_bytes)

    print(f"PDF successfully created at: {report_pdf_path}")

    logger.info("html から pdf を生成しました")
    return report_pdf_path
