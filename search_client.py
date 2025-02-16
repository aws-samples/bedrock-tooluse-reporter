import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Dict, Optional


class SearchClient:
    def __init__(self):
        self.api_key = self._load_api_key()
        self.search_url = "https://api.search.brave.com/res/v1/web/search"
        self.headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }

    def _load_api_key(self) -> str:
        try:
            return Path('.brave').read_text().strip()
        except FileNotFoundError:
            raise Exception("Brave API key file (.brave) not found")

    def search(self, query: str) -> str:
        """Web検索を実行し結果を返す"""
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

        except Exception as e:
            print(f"Search error: {e}")

        return json.dumps(results, ensure_ascii=False)

    def get_content(self, url: str) -> Optional[str]:
        """指定URLのコンテンツを取得"""
        try:
            response = requests.get(url)
            response.raise_for_status()
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, 'html.parser')
            for tag in soup(['script', 'style', 'header', 'footer', 'nav']):
                tag.decompose()

            lines = [
                line.strip() for line in soup.get_text().splitlines() if line.strip()
            ]
            return '\n'.join(lines)

        except Exception as e:
            print(f"Content fetch error: {e}")
            return None
