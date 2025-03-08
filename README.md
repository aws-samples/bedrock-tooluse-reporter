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
3. `playwright install chromium` を実行
4. python main.py --prompt "きのこの山とたけのこの里、どちらが至高のお菓子かの結論"  
  (prompt は自由に変える)
5. `./reports/` ディレクトリに `report_YYYYMMDD_HH24MISS.md` および `html` 形式でレポートが出来上がります。
6. enjoy!

## 開発時
pip-compile を使っているので、requirements.txt を変更したい場合は以下のようにしてください。


```shell
# 事前に requirements.in に変更したいパッケージを記載したあとに
pip-compile requirements.in
# インストール
pip install -r requirements.txt
```
