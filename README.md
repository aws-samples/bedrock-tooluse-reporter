# deep-research-modoki

## 前提
* リージョンは `us-west-2`
* aws configure してあること
* Bedrock Invoke できること
* claude-3.7-sonnet-v1, claude-3.5-sonnet-v2 が使えること

## Getting started

1. `.brave` ファイルをリポジトリのルートディレクトリに配置し、そこに brave サーチの API キーを保存する。  
  API キーの取得は[こちら](https://brave.com/search/api/)から
2. `pip install -r requirements.txt` を実行
3. python main.py --prompt "きのこの山とたけのこの里、どちらが至高のお菓子かの結論"  
  (prompt は自由に変える)
4. `./reports/` ディレクトリに `report_YYYYMMDD_HH24MISS.md` および `html` 形式でレポートが出来上がります。
5. enjoy!