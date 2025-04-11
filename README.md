# Bedrock Tooluse Reporter

AIを活用した自動レポート生成システム

## 概要

Bedrock Tooluse Reporterは、与えられたトピックに関する詳細なレポートを自動的に生成するAIシステムです。複数のAIモデルを活用して、情報収集、視点の多角化、データ調査、レポート執筆を行います。

## 特徴

- **コンテキスト理解**: ユーザーの意図を理解し、トピックに関連する基本情報を収集
- **多角的視点**: 2つの異なるAIモデル間の対話を通じて多様な視点を獲得
- **データ収集**: Web検索、コンテンツ取得、画像検索などを活用した情報収集
- **レポート生成**: 収集した情報に基づく構造化されたマークダウンレポートの作成
- **視覚化**: Mermaid図やWeb画像を活用した視覚的なレポート
- **複数形式**: マークダウン、HTML、PDFの3形式でレポートを出力

## システム構成

システムは以下の4つの主要コンポーネントで構成されています：

1. **ContextChecker**: ユーザーの意図を理解し、トピックに関連する基本情報を収集
2. **PerspectiveExplorer**: 2つの異なるAIモデル間の対話を通じて多角的な視点を獲得
3. **DataSurveyor**: レポートフレームワークに基づいて必要なデータを収集
4. **ReportWriter**: 収集したデータとフレームワークに基づいてレポートを執筆

### 前提条件
- AWS環境
  - リージョン: `us-west-2`
  - AWS CLIで設定済み（`aws configure`）
  - Bedrock APIの呼び出し権限
  - 対応モデル: claude-3.7-sonnet-v1, claude-3.5-sonnet-v2
- Python 3.10
- Brave Search API キー

## インストール方法

1. リポジトリをクローン
   ```shell
   git clone https://github.com/aws-samples/bedrock-tooluse-reporter
   cd bedrock-tooluse-reporter
2. `.brave` ファイルをリポジトリのルートディレクトリに作成し、Brave Search APIキーを保存
3. 仮想環境を作成し、依存パッケージをインストール
    ```shell
    python -m venv .venv
    source .venv/bin/activate  # Windowsの場合: .venv\Scripts\activate
    pip install -r requirements.txt
    ```
## 使用方法

```bash
# 基本的な使用方法
python main.py --prompt "調査したいトピック"
```

例: 
```shell
python main.py --prompt "タワマン文学とマウンティングについてのレポート"
```

### オプション
`--prompt`, `-p`: 調査するトピック（必須）
`--mode`, `-m`: 処理モード（short/long）を指定。shortは処理回数を減らして高速に、longは詳細な調査を行います
`--log-level`, `-l`: ログレベルを指定（DEBUG/INFO/WARNING/ERROR/CRITICAL）
`--resume-file`, `-r`: 以前の会話履歴から再開する場合に指定
例: 
```shell
python main.py --prompt "AIと著作権の未来" --mode long --log-level DEBUG
```

### 出力
- レポートは `./report/[タイムスタンプ]/` に生成されます
- 各レポートディレクトリには以下のファイルが含まれます:
    - `report.md`: マークダウン形式のレポート
    - `report.html`: スタイル適用済みのHTML形式レポート
    - `report.pdf`: 印刷可能なPDF形式レポート
    - `images/`: レポートで使用される画像ファイル

## 開発者向け情報
### 依存パッケージの管理
このプロジェクトでは pip-compile を使用して依存関係を管理しています。

```shell
# requirements.in を編集後、requirements.txt を更新
pip-compile requirements.in

# 依存パッケージのインストール
pip install -r requirements.txt
```

### プロジェクト構造
```text
bedrock-tooluse-reporter/
├── main.py                # メインエントリーポイント
├── requirements.txt       # 依存パッケージ
├── research/              # 研究関連モジュール
│   ├── __init__.py
│   ├── perspective_explorer.py
│   ├── reporter.py
│   └── mermaid.md
├── utils/                 # ユーティリティモジュール
│   ├── __init__.py
│   ├── bedrock.py
│   ├── bedrock_wrapper.py
│   ├── config.py
│   ├── conversation.py
│   ├── logger.py
│   ├── tools.py
│   └── utils.py
├── report/                # 生成されたレポート
├── conversation/          # 会話履歴
└── log/                   # ログファイル
```

## 設定

設定は `utils/config.py` で管理されています。主な設定項目：

- AIモデルID
- 各プロセスの最大実行回数
- ディレクトリパス
- 使用するツール
- 画像関連の設定
- ドキュメント関連の設定

### トラブルシューティング
- **APIキーエラー**: `.brave` ファイルが正しく配置されているか確認
- **AWS認証エラー**: `aws configure` で認証情報が正しく設定されているか確認
- **モデルアクセスエラー**: 指定されたBedrockモデルへのアクセス権があるか確認
- **メモリエラー**: 大量の画像や長いテキストを処理する場合、十分なメモリを確保

## 裏メニュー
アカウントラウンドロビンする場合は `utils/bedrock_rapper.py` の `self.profiles` をいじる