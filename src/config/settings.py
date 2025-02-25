"""
設定ファイル
環境変数とデフォルト値の管理

このモジュールは、アプリケーション全体で使用される設定値を定義します。
"""

from typing import Dict, Any

# Bedrock モデルの設定
# モデル名とそのAWS Bedrock IDのマッピング
MODEL_CONFIG: Dict[str, str] = {
    'claude-3.5-sonnet': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
    'claude-3.7-sonnet': 'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
    'nova-pro': 'us.amazon.nova-pro-v1:0',
    'mistral-large': 'mistral.mistral-large-2407-v1:0',
    'llama-3.3': 'us.meta.llama3-3-70b-instruct-v1:0',
}

# 使用するモデルの設定
PRIMARY_MODEL = 'claude-3.7-sonnet'  # 主要な対話に使用するモデル
SECONDARY_MODEL = 'claude-3.5-sonnet'  # 二次的な対話に使用するモデル

# 会話の最大ターン数
MAX_CONVERSATION_TURNS = 5

# LLM接続設定
LLM_CONNECTION = {
    'timeout': 600,  # APIリクエストのタイムアウト（秒）
    'max_retries': 5,  # 最大リトライ回数
    'base_delay': 20,  # 初期バックオフ遅延（秒）
    'max_delay': 300,  # 最大バックオフ遅延（秒）
}

# ツール設定
TOOL_CONFIG = {
    'tools': [
        {
            'toolSpec': {
                'name': 'search',
                'description': '検索する文章、キーワードを受け取って Web 検索する',
                'inputSchema': {
                    'json': {
                        'type': 'object',
                        'properties': {
                            'query': {
                                'type': 'string',
                                'description': '検索する文章またはキーワード。半角スペースで区切ることで複数のキーワードを受け付ける。',
                            }
                        },
                        'required': ['query'],
                    }
                },
            }
        },
        {
            'toolSpec': {
                'name': 'get_content',
                'description': 'URL にアクセスして html のコンテンツを取得',
                'inputSchema': {
                    'json': {
                        'type': 'object',
                        'properties': {
                            'url': {
                                'type': 'string',
                                'description': '情報を取得したい URL',
                            }
                        },
                        'required': ['url'],
                    }
                },
            }
        },
        {
            'toolSpec': {
                'name': 'is_finished',
                'description': 'ツールの利用が完了し、次のステップに進む関数',
                'inputSchema': {
                    'json': {
                        'type': 'object',
                        'properties': {},
                        'required': [],
                    }
                },
            }
        },
    ]
}

# 出力ディレクトリ設定
OUTPUT_DIR = {
    'logs': 'logs',
    'reports': 'reports',
}

# プロンプト設定
PROMPT_CONFIG = {
    'max_tokens': 8192,  # 最大トークン数
    'temperature': {
        'default': 0.8,  # デフォルトの温度設定
        'strategy': 0,  # 戦略生成時の温度設定
    },
}

# 引用形式設定
CITATION_FORMAT = {
    'prefix': '[※',
    'suffix': ']',
    'reference_title': '参考文献',
}

# レポート設定
REPORT_CONFIG = {
    'max_attempts': 10,  # レポート生成の最大試行回数
    'completion_markers': [  # レポート完了を示すマーカー
        "レポートの終了",
        "レポートは終了",
        "レポートを終了",
        "レポートは完了",
        "レポートの完了",
        "レポートを完了",
    ],
}
