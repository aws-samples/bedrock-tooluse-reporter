import requests
import json
from pathlib import Path
from .bedrock import BedrockModel
from .config import Config
from bs4 import BeautifulSoup
import os
from uuid import uuid4
from typing import Optional


class Tools:
    """
    AIが使用するツール群を提供するクラス

    Web検索、コンテンツ取得、画像検索などの外部データ収集ツールを実装しています。
    """

    def __init__(self, timestamp_str, logger, requested_tools, mode, report_dir):
        """
        ツールの初期化

        Args:
            timestamp_str: タイムスタンプ文字列
            logger: ロガーインスタンス
            requested_tools: 使用するツールのリスト
            mode: 動作モード（short/long）
            report_dir: レポート出力ディレクトリ
        """
        self.logger = logger
        self.requested_tools = requested_tools
        self.tool_config = self.get_tool_config()
        self.timestamp_str = timestamp_str
        self.api_key = self._load_api_key()
        self.search_url = "https://api.search.brave.com/res/v1/web/search"
        self.image_search_url = "https://api.search.brave.com/res/v1/images/search"
        self.headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        self.timeout = (5, 10)  # 接続タイムアウト: 5秒, 読み取りタイムアウト: 10秒
        self.config = Config(mode)
        self.report_dir = report_dir
        self.image_dir = self._set_image_dir()
        self.bedrock = BedrockModel(logger, mode)

    def _set_image_dir(self):
        """
        画像保存ディレクトリを設定

        Returns:
            str: 画像ディレクトリのパス
        """
        image_dir = os.path.join(self.report_dir, "images")
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)
        return image_dir

    def get_tool_config(self):
        """
        ツール設定を取得

        AIモデルに提供するツール設定を生成します。

        Returns:
            dict: ツール設定
        """
        tools = [
            {
                "toolSpec": {
                    "name": "search",
                    "description": """検索する文章、キーワードを受け取ってインターネット(brave)で検索する。
レスポンスは [{"title": "タイトル" ,"url": "URL","description": "説明"}] の JSON 文字列
エラーが発生した場合は Error: から始まるエラー内容が返る。""",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "検索する文章またはキーワード。半角スペースで区切ることで複数のキーワードを受け付ける。",
                                }
                            },
                            "required": ["query"],
                        }
                    },
                }
            },
            {
                "toolSpec": {
                    "name": "get_content",
                    "description": """URL にアクセスしてコンテンツを取得
レスポンスは title キーと content キーを持った JSON 文字列
エラー発生時は Error: から始まる文言が返る""",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": "情報を取得したい URL",
                                }
                            },
                            "required": ["url"],
                        }
                    },
                }
            },
            {
                "toolSpec": {
                    "name": "image_search",
                    "description": """画像をインターネット(brave)で検索、取得して保存する。
エラー発生時は Error: から始まる文言が返る""",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "検索する画像のキーワード。半角スペースで区切ることで複数のキーワードを受け付ける。",
                                },
                                "max_results": {
                                    "type": "integer",
                                    "description": "取得する最大画像数（デフォルト: 5）",
                                },
                            },
                            "required": ["query"],
                        }
                    },
                }
            },
            {
                "toolSpec": {
                    "name": "write",
                    "description": """ファイルにテキストを追記するツール。
書き込みに成功したら "Succeeded!" が返る。
エラーが発生した場合は Error: という文言から始まる言葉が返る。""",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": "ファイルに書き込みたい内容",
                                },
                                "write_file_path": {
                                    "type": "string",
                                    "description": "テキストを追記するファイルパス",
                                },
                            },
                            "required": ["content", "write_file_path"],
                        }
                    },
                }
            },
            {
                "toolSpec": {
                    "name": "is_finished",
                    "description": "やることが全て終わった時に使用する関数",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        }
                    },
                }
            },
        ]

        # 要求されたツールだけをフィルタリング
        filtered_tools = {"tools": []}
        for tool in tools:
            if tool["toolSpec"]["name"] in self.requested_tools:
                filtered_tools["tools"].append(tool)

        return filtered_tools

    def _load_api_key(self, file_path: str = ".brave") -> str:
        """
        Brave API キーの読み込み

        指定されたファイルからAPIキーを読み込みます。

        Args:
            file_path: APIキーが保存されているファイルパス（デフォルト: ".brave"）

        Returns:
            str: API キー

        Raises:
            FileNotFoundError: APIキーファイルが見つからない場合
            ValueError: APIキーが空または無効な場合
        """
        try:
            api_key = Path(file_path).read_text().strip()
            if not api_key:
                self.logger.error(f"API key is empty in file: {file_path}")
                raise ValueError("API key cannot be empty")
            return api_key
        except FileNotFoundError:
            self.logger.error(f"API key file not found: {file_path}")
            raise FileNotFoundError(
                f"API key file not found: {file_path}. Please create a file named {file_path} with your Brave API key."
            )
        except Exception as e:
            self.logger.error(f"Failed to load API key: {str(e)}")
            raise

    def _get_http_headers(self):
        """
        HTTPリクエスト用のヘッダーを取得

        Returns:
            dict: HTTPヘッダー
        """
        obj = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }
        return obj

    def _extract_info(self, data):
        """
        検索結果から情報を抽出

        Args:
            data: 検索APIからのレスポンスデータ

        Returns:
            list: 抽出された検索結果のリスト
        """
        results = []

        # web検索結果を取得
        web_results = data.get("web", {}).get("results", [])

        # 各結果からtitle, url, descriptionを抽出
        for result in web_results:
            title = result.get("title", "")
            url = result.get("url", "")
            description = result.get("description", "")

            results.append({"title": title, "url": url, "description": description})

        return results

    def search(self, query):
        """
        Web検索を実行

        Brave Search APIを使用してWeb検索を実行します。

        Args:
            query: 検索クエリ

        Returns:
            str: 検索結果のJSON文字列またはエラーメッセージ
        """
        # 全角スペースを半角に変換
        query = query.replace("　", " ")

        try:
            params = {"q": query, "offset": 0, "count": 10}
            response = requests.get(
                self.search_url,
                headers=self.headers,
                params=params,
                timeout=self.timeout,
            )
            self.logger.info(f"Web検索API: {response.url}")
            self.logger.info(f"Web検索API: {response.status_code}")

            if response.status_code >= 300:
                error_message = f"Error: ステータスコードが {response.status_code} でした。300番台以上はすべてエラーです。"
                return error_message
            data = json.dumps(self._extract_info(response.json()), ensure_ascii=False)
            self.logger.info(f"検索結果: {data}")
            return data

        except requests.Timeout:
            return f"Error: タイムアウト"
        except requests.ConnectionError:
            return f"Error: 接続エラー"
        except Exception as e:
            return f"Error: {e}"

    def _process_document(self, url: str, document_type: str):
        """
        ドキュメントを処理

        URLからドキュメントを取得し、AIモデルを使用して内容を抽出します。

        Args:
            url: ドキュメントのURL
            document_type: ドキュメントの種類

        Returns:
            str: 処理結果またはエラーメッセージ
        """
        # ファイルサイズを確認
        response = requests.head(url)
        # Content-Length ヘッダーがあればファイルサイズを取得
        if "Content-Length" in response.headers:
            file_size = int(response.headers["Content-Length"])
            if file_size > self.config.DOCUMENT_CONFIG.BEDROCK_MAX_SIZE:
                return f"Error: ファイルサイズが 4.5 MB以上で扱えません(サイズ: {file_size / (1024 * 1024):.2f}MB)"

        # ドキュメントをダウンロード
        response = requests.get(url, stream=True)
        response.raise_for_status()

        # AIモデルを使用してドキュメントを処理
        return self.bedrock.describe_document(
            response.content,
            "downloaded document",
            document_type,
            self.config.BEDROCK.PRIMARY_MODEL_ID,
        )

    def get_content(self, url: str):
        """
        指定URLのコンテンツを取得

        指定されたURLからコンテンツを取得し、HTMLを処理して整形されたテキストを返します。
        また、ページのタイトルも取得します。

        Args:
            url: コンテンツを取得するURL

        Returns:
            str: 取得したコンテンツまたはエラーメッセージ
        """
        try:
            # タイムアウト設定でリクエスト実行
            response = requests.get(
                url, timeout=self.timeout, stream=True, headers=self._get_http_headers()
            )

            # HTTPステータスコードのチェック
            if response.status_code >= 300:  # 300番台以上は全てエラーとして扱う
                error_message = f"ERROR: コンテンツ取得エラー: ステータスコード {response.status_code}"
                return error_message

            # コンテンツタイプのチェック
            content_type = (
                response.headers.get("Content-Type", "").lower().split(";")[0]
            )
            self.logger.debug(f"コンテンツタイプ: {content_type}")

            # 処理可能なコンテンツタイプの定義
            processable_types = {
                "application/pdf": "pdf",
                "text/csv": "csv",
                "application/msword": "doc",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
                "application/vnd.ms-excel": "xls",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
                "text/html": "html",
                "text/plain": "txt",
                "text/markdown": "md",
                "application/json": "json",  # JSONも処理対象に含める
            }

            # コンテンツタイプに応じた処理
            if (content_type in processable_types) and content_type != "text/html":
                # HTML以外の処理可能なドキュメント
                document_type = processable_types[content_type]
                return self._process_document(url, document_type)
            elif (content_type in processable_types) and content_type == "text/html":
                # HTMLの処理
                response.encoding = response.apparent_encoding
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.string if soup.title else ""
                title = " ".join(title.split())

                # 不要なタグを削除
                for tag in soup(["script", "style", "header", "footer", "nav"]):
                    tag.decompose()

                # テキストを抽出して整形
                lines = [
                    line.strip()
                    for line in soup.get_text().splitlines()
                    if line.strip()
                ]
                lines_text = "\n".join(lines)
                content = f"""title : {title}
{lines_text}"""

                # AIモデルを使用してHTMLコンテンツを処理
                return self.bedrock.describe_html(
                    content,
                    self.config.BEDROCK.PRIMARY_MODEL_ID,
                )
            else:
                # 処理できないコンテンツタイプ
                error_message = f"Error: このコンテンツは{content_type}ファイルであり、直接処理できません。ファイルを手動でダウンロードして確認してください。"
                return error_message
        except requests.Timeout:
            error_message = "Error: タイムアウトしました"
            return error_message
        except requests.ConnectionError:
            error_message = "Error: 接続エラーが発生しました。"
            return error_message
        except Exception as e:
            error_message = f"Error: {str(e)}"
            return error_message

    def image_search(self, query: str, max_results: int = None) -> str:
        """
        画像検索を実行し、画像を保存

        Brave Search APIを使用して画像検索を実行し、画像をダウンロードして保存します。
        保存した画像のパスとメタデータを返します。

        Args:
            query: 検索クエリ
            max_results: 取得する最大画像数（指定がない場合はIMAGE_CONFIG.MAX_IMAGESを使用）

        Returns:
            str: 保存した画像のパスとメタデータのJSON文字列またはエラーメッセージ
        """
        self.logger.debug("################## call image search ##################")
        # 全角スペースを半角に変換
        query = query.replace("　", " ")

        # 最大画像数の設定
        if max_results is None:
            max_results = self.config.IMAGE_CONFIG.MAX_IMAGES
        else:
            max_results = min(max_results, 10)  # 最大10枚に制限

        saved_images = []

        try:
            params = {
                "q": query,
                "offset": 0,
                "count": max_results * 2,
            }  # 余裕を持って多めに取得

            # タイムアウト設定でリクエスト実行
            response = requests.get(
                self.image_search_url,
                headers=self.headers,
                params=params,
                timeout=self.timeout,
            )
            # HTTPステータスコードのチェック
            if response.status_code >= 300:  # 300番台以上は全てエラーとして扱う
                return json.dumps(
                    {"error": f"API error: {response.status_code}"}, ensure_ascii=False
                )

            data = response.json()
            self.logger.debug(data)
            # 検索結果の処理
            if "results" in data:
                count = 0
                for image in data["results"]:
                    if count >= max_results:
                        break
                    try:
                        # 画像URLの取得
                        property_dict = image.get("properties", {})
                        image_url = (
                            property_dict.get("url", "") if property_dict else None
                        )
                        if not image_url:
                            continue

                        # 画像の拡張子を取得
                        ext = (
                            image_url.split("?")[0]
                            .split(".")[-1]
                            .replace("jpg", "jpeg")
                        )
                        if (not ext) or (
                            ext not in self.config.IMAGE_CONFIG.ALLOWED_FORMATS
                        ):
                            continue

                        # 画像をダウンロードして保存
                        image_path = self._download_and_save_image(image_url, ext)
                        # 画像の説明文を生成
                        with open(image_path, "rb") as f:
                            document_content = f.read()
                        description = self.bedrock.describe_document(
                            document_content,
                            image_path,
                            ext,
                            self.config.BEDROCK.PRIMARY_MODEL_ID,
                        )
                        saved_images.append(
                            {
                                "path": os.path.join(
                                    "./", os.path.relpath(image_path, self.report_dir)
                                ),  # markdown では markdown ファイルからの相対パスを参照するための処理
                                "title": image.get("title", ""),
                                "description": description,
                                "source_url": image.get("sourceUrl", ""),
                                "width": image.get("width", 0),
                                "height": image.get("height", 0),
                                "format": image.get("format", ""),
                            }
                        )
                        count += 1
                    except Exception as e:
                        self.logger.error(f"画像処理エラー: {str(e)}")
                        continue

            return json.dumps({"images": saved_images}, ensure_ascii=False)

        except requests.Timeout:
            # タイムアウトエラー
            return json.dumps({"error": "タイムアウトエラー"}, ensure_ascii=False)
        except requests.ConnectionError:
            # 接続エラー
            return json.dumps({"error": "接続エラー"}, ensure_ascii=False)
        except Exception as e:
            # その他のエラー
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def _download_and_save_image(self, url: str, ext: str) -> Optional[str]:
        """
        画像をダウンロードして保存

        Args:
            url: 画像URL
            ext: 拡張子（ドットを含まない）

        Returns:
            Optional[str]: 保存したファイルのパスまたはエラーメッセージ
        """
        try:
            # タイムアウト設定でリクエスト実行
            response = requests.get(
                url, timeout=self.timeout, stream=True, headers=self._get_http_headers()
            )

            # HTTPステータスコードのチェック
            if response.status_code >= 300:
                self.logger.warning(
                    f"画像ダウンロードエラー: HTTP {response.status_code}"
                )
                return f"Error: 画像ダウンロードエラー: HTTP {response.status_code}"

            # Content-Typeのチェック
            content_type = response.headers.get("Content-Type", "").lower()
            if not ("image/" in content_type):
                self.logger.warning(f"画像ではないコンテンツ: {content_type}")
                return f"Error: 画像ではないコンテンツ: {content_type}"

            # ファイルサイズのチェック
            content_length = int(response.headers.get("Content-Length", 0))
            if content_length > self.config.IMAGE_CONFIG.MAX_SIZE:
                self.logger.warning(f"画像サイズ制限超過: {content_length} bytes")
                return f"Error: 画像サイズ制限超過: {content_length} bytes"

            # ユニークなファイル名を生成
            filename = f"{uuid4().hex}.{ext}"
            filepath = os.path.join(self.image_dir, filename)

            # 画像を保存
            with open(filepath, "wb") as f:
                f.write(response.content)

            self.logger.info(f"画像を保存しました: {filepath}")
            return filepath

        except Exception as e:
            self.logger.warning(f"画像ダウンロードエラー: {str(e)}")
            return f"Error: 画像ダウンロードエラー: {str(e)}"

    def write(self, content, write_file_path) -> str:
        """
        ファイルにテキストを書き込み

        Args:
            content: 書き込む内容
            write_file_path: 書き込み先ファイルパス

        Returns:
            str: 成功メッセージまたはエラーメッセージ
        """
        error_messages = []
        if content == "":
            error_messages.append("content is empty")
        if write_file_path == "":
            error_messages.append("write_file_path is empty")

        if error_messages:
            return "Error: " + ", ".join(error_messages)

        try:
            with open(write_file_path, "at") as f:
                f.write(content + "\n")
            return "Succeeded!"
        except Exception as e:
            return f"Error: An unexpected error occurred: {str(e)}"
