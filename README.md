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

## config file

`--config` オプションを利用するとyamlで設定ファイルを読み込んで動作します。

```
# config.yaml - Deep Research Modoki Configuration

# Bedrock モデルの設定
#    モデルIDを追加してストアしておきエイリアス名を設定します
models:
  claude-3.5-sonnet: "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
  claude-3.7-sonnet: "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
  nova-pro: "us.amazon.nova-pro-v1:0"
  deepseek.r1": "deepseek.r1-v1:0"
  mistral-large: "mistral.mistral-large-2407-v1:0"
  llama-3.3: "us.meta.llama3-3-70b-instruct-v1:0"

# 使用するモデルの設定
#   上記エイリアスを指定します
#   primary_modelはconversion apiでPPTを受け取れるモデルである必要があります
primary_model: "claude-3.7-sonnet"
secondary_model: "nova-pro"

# 会話の最大ターン数
#   max_turns: 標準モードのLLM同士の議論回数
#   summary_turns: サマリーモードのLLM同士の議論回数
conversation:
  max_turns: 5
  summary_turns: 3

# 調査の最大回数
#   max_pre_searches: 事前調査の最大回数
#   summary_pre_searches: サマリーモードの事前調査の最大回数
#   max_searched: 議論後の調査の調査最大回数
#   summary_searches: サマリーモード時の議論後の調査最大回数
research:
  max_pre_searches: 40
  summary_pre_searches: 3
  max_searches: 40
  summary_searches: 10

# LLM接続設定
#    profilesには複数のプロファイルを設定できます
#    Throttling が厳しいときは複数アカウント払い出して各アカウントに振り分ける事で回答を得る事ができます
#    必ず各Profileの該当RegionでBedrockモデルを利用許諾して設定してからご利用ください
#    例）profiles:
#         - "default"
#         - "profile_two"
#         - "profiel_three"
connection:
  timeout: 1200
  max_retries: 8
  base_delay: 20
  max_delay: 300
  profiles:
    - "default"
```


## 開発時
pip-compile を使っているので、requirements.txt を変更したい場合は以下のようにしてください。


```shell
# 事前に requirements.in に変更したいパッケージを記載したあとに
pip-compile requirements.in
# インストール
pip install -r requirements.txt
```
