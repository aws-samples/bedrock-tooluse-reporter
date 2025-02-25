"""
ツール関連の処理を担当するクラス
"""

from typing import Dict, Optional, Tuple
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from ..utils.exceptions import ToolError


class ToolHandler:
    """
    外部ツールの操作を管理するクラス

    このクラスは、Web検索やコンテンツ取得などの外部ツールの操作を処理し、
    AIモデルからのツール使用リクエストを解釈します。
    """

    def __init__(self):
        """
        ツールハンドラの初期化

        Brave Search APIキーを読み込み、APIエンドポイントとヘッダーを設定します。
        """
        self.api_key = self._load_api_key()
        self.search_url = "https://api.search.brave.com/res/v1/web/search"
        self.headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        # タイムアウト設定（接続は5秒、読み込みは10秒）
        self.timeout = (5, 10)

    def _load_api_key(self) -> str:
        """
        Brave API キーの読み込み

        .braveファイルからAPIキーを読み込みます。

        Returns:
            str: API キー

        Raises:
            ToolError: API キーファイルが見つからない場合
        """
        try:
            return Path('.brave').read_text().strip()
        except FileNotFoundError:
            raise ToolError("Brave API key file (.brave) not found")
        except Exception as e:
            raise ToolError(f"Error loading API key: {str(e)}")

    def get_content(self, url: str) -> Tuple[str, str]:
        """
        指定URLのコンテンツを取得

        指定されたURLからコンテンツを取得し、HTMLを処理して整形されたテキストを返します。
        また、ページのタイトルも取得します。

        Args:
            url: コンテンツを取得するURL

        Returns:
            Tuple[str, str]: 取得したコンテンツとページタイトル。エラー時は空文字列のタプル
        """
        try:
            # タイムアウト設定でリクエスト実行
            response = requests.get(url, timeout=self.timeout)

            # HTTPステータスコードのチェック
            if response.status_code >= 300:  # 300番台以上は全てエラーとして扱う
                return "", ""

            # コンテンツタイプのチェック
            content_type = response.headers.get('Content-Type', '').lower()

            # バイナリコンテンツの場合は処理をスキップ
            if (
                'pdf' in content_type
                or 'application/' in content_type
                or 'image/' in content_type
            ):
                return (
                    f"[このコンテンツは{content_type}ファイルであり、直接処理できません。"
                    f"ファイルを手動でダウンロードして確認してください。]",
                    "バイナリコンテンツ",
                )

            # エンコーディングを設定
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')

            # タイトルの取得と整形
            title = soup.title.string if soup.title else ""
            title = " ".join(title.split())

            # 不要なHTML要素を削除
            for tag in soup(['script', 'style', 'header', 'footer', 'nav']):
                tag.decompose()

            # テキストを行ごとに抽出して結合
            lines = [
                line.strip() for line in soup.get_text().splitlines() if line.strip()
            ]
            return '\n'.join(lines), title

        except requests.Timeout:
            # タイムアウトエラー
            return "", ""
        except requests.ConnectionError:
            # 接続エラー（DNSエラー、接続拒否など）
            return "", ""
        except Exception as e:
            # その他のエラー
            return "", ""

    def search(self, query: str) -> str:
        """
        Web検索を実行

        Brave Search APIを使用してWeb検索を実行し、結果をJSON形式で返します。

        Args:
            query: 検索クエリ

        Returns:
            str: 検索結果のJSON文字列。エラー時は空文字列
        """
        # 全角スペースを半角に変換
        query = query.replace('　', ' ')
        results = []

        try:
            params = {"q": query, "offset": 0, "count": 10}
            # タイムアウト設定でリクエスト実行
            response = requests.get(
                self.search_url,
                headers=self.headers,
                params=params,
                timeout=self.timeout,
            )

            # HTTPステータスコードのチェック
            if response.status_code >= 300:  # 300番台以上は全てエラーとして扱う
                return ""

            data = response.json()

            # 検索結果の処理
            if 'web' in data and 'results' in data['web']:
                for result in data['web']['results']:
                    result_dict = {
                        "title": result.get('title', ''),
                        "url": result.get('url', ''),
                        "description": result.get('description', ''),
                    }
                    if result_dict["title"] and result_dict["url"]:
                        results.append(result_dict)

            return json.dumps(results, ensure_ascii=False)

        except requests.Timeout:
            # タイムアウトエラー
            return ""
        except requests.ConnectionError:
            # 接続エラー（DNSエラー、接続拒否など）
            return ""
        except Exception as e:
            # その他のエラー
            return ""

    def process_tool_response(self, model_response: Dict) -> Optional[Dict]:
        """
        モデルのツール使用レスポンスを処理

        AIモデルのレスポンスからツール使用情報を抽出します。

        Args:
            model_response: モデルからのレスポンス

        Returns:
            Optional[Dict]: ツール使用情報、ツール使用がない場合はNone
        """
        try:
            content_list = (
                model_response.get('output', {}).get('message', {}).get('content', [])
            )
            for content_item in content_list:
                if isinstance(content_item, dict) and 'toolUse' in content_item:
                    return content_item['toolUse']
        except (AttributeError, TypeError) as e:
            # エラーが発生した場合はNoneを返す
            pass
        return None
