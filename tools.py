import requests
import json
from pathlib import Path
import requests
from bs4 import BeautifulSoup


def search(query: str) -> list[dict]:
    """
    Brave検索を実行し、検索結果をJSON形式で返す

    Args:
        query (str): 検索キーワード（全角/半角スペース区切り）

    Returns:
        list[dict]: 検索結果のリスト。各結果は以下のキーを持つ辞書:
            - title: 検索結果のタイトル
            - url: 検索結果のURL
            - description: 検索結果の説明文
    """
    # APIキーの読み込み
    try:
        api_key = Path('.brave').read_text().strip()
    except FileNotFoundError:
        raise Exception("Brave API key file (.brave) not found")

    # 全角スペースを半角に変換
    query = query.replace('　', ' ')

    # API エンドポイントとヘッダー
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept": "application/json", "X-Subscription-Token": api_key}

    results = []

    # 3ページ分の結果を取得
    for offset in range(1):
        params = {"q": query, "offset": offset * 10, "count": 10}  # 各ページ10件ずつ

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()

            # 検索結果の抽出
            if 'web' in data and 'results' in data['web']:
                for result in data['web']['results']:
                    result_dict = {
                        "title": result.get('title', ''),
                        "url": result.get('url', ''),
                        "description": result.get('description', ''),
                    }
                    # タイトルとURLが存在する場合のみ追加
                    if result_dict["title"] and result_dict["url"]:
                        results.append(result_dict)

        except requests.exceptions.RequestException as e:
            print(f"Error during API request: {e}")
            continue

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {e}")
            continue

    return json.dumps(results, ensure_ascii=False)


def get_content(url):
    try:
        # HTMLを取得
        response = requests.get(url)
        response.raise_for_status()
        response.encoding = response.apparent_encoding

        # BeautifulSoupでパース
        soup = BeautifulSoup(response.text, 'html.parser')

        # 不要な要素を削除
        for tag in soup(['script', 'style', 'header', 'footer', 'nav']):
            tag.decompose()

        # テキストを抽出
        text = soup.get_text()
        # 空行を削除して整形
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        content = '\n'.join(lines)

        return content

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return None


# 使用例
if __name__ == "__main__":
    # query = "Python プログラミング 入門"
    # search_results = search(query)

    # for i, (title, url, description) in enumerate(search_results, 1):
    #     print(f"\n{i}. タイトル: {title}")
    #     print(f"   URL: {url}")
    #     print(f'説明:{description}')
    print(get_content('http://www.yahoo.co.jp'))
