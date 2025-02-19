"""
ツール関連の処理を担当するクラス
"""
from typing import Dict, Optional
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from ..utils.exceptions import ToolError


class ToolHandler:
    def __init__(self):
        """ツールハンドラの初期化"""
        self.api_key = self._load_api_key()
        self.search_url = "https://api.search.brave.com/res/v1/web/search"
        self.headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }

    def _load_api_key(self) -> str:
        """
        Brave API キーの読み込み

        Returns:
            str: API キー

        Raises:
            ToolError: API キーファイルが見つからない場合
        """
        try:
            return Path('.brave').read_text().strip()
        except FileNotFoundError:
            raise ToolError("Brave API key file (.brave) not found")

    def search(self, query: str) -> str:
        """
        Web検索を実行

        Args:
            query: 検索クエリ

        Returns:
            str: 検索結果のJSON文字列

        Raises:
            ToolError: 検索実行時のエラー
        """
        query = query.replace('　', ' ')
        results = []

        try:
            params = {"q": query, "offset": 0, "count": 10}
            response = requests.get(
                self.search_url, headers=self.headers, params=params
            )
            response.raise_for_status()
            data = response.json()

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

        except Exception as e:
            raise ToolError(f"Search error: {str(e)}")

    def get_content(self, url: str) -> str:
        """
        指定URLのコンテンツを取得
    
        Args:
            url: コンテンツを取得するURL
    
        Returns:
            str: 取得したコンテンツ。エラー時は空文字列
        """
        try:
            # タイムアウトを設定（接続は5秒、読み込みは10秒）
            response = requests.get(url, timeout=(5, 10))
            
            # HTTPステータスコードのチェック
            if response.status_code >= 300:  # 300番台以上は全てエラーとして扱う
                return ""
    
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for tag in soup(['script', 'style', 'header', 'footer', 'nav']):
                tag.decompose()
    
            lines = [
                line.strip() for line in soup.get_text().splitlines() if line.strip()
            ]
            return '\n'.join(lines)
    
        except requests.Timeout:
            # タイムアウトエラー
            return ""
        except requests.ConnectionError:
            # 接続エラー（DNSエラー、接続拒否など）
            return ""
        except Exception:
            # その他のエラー
            return ""
    
    def search(self, query: str) -> str:
        """
        Web検索を実行
    
        Args:
            query: 検索クエリ
    
        Returns:
            str: 検索結果のJSON文字列。エラー時は空文字列
        """
        query = query.replace('　', ' ')
        results = []
    
        try:
            params = {"q": query, "offset": 0, "count": 10}
            # タイムアウトを設定（接続は5秒、読み込みは10秒）
            response = requests.get(
                self.search_url, 
                headers=self.headers, 
                params=params,
                timeout=(5, 10)
            )
            
            # HTTPステータスコードのチェック
            if response.status_code >= 300:  # 300番台以上は全てエラーとして扱う
                return ""
    
            data = response.json()
    
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
        except Exception:
            # その他のエラー
            return ""
    
    def process_tool_response(self, model_response: Dict) -> Optional[Dict]:
        """
        モデルのツール使用レスポンスを処理
    
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
        except (AttributeError, TypeError):
            pass
        return None
    