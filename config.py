import os
from typing import Dict

# Bedrock モデルの設定
MODEL_CONFIG: Dict[str, str] = {
    'claude-3.5-sonnet': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
    'nova-pro': 'us.amazon.nova-pro-v1:0',
    'mistral-large': 'mistral.mistral-large-2407-v1:0',
    'llama-3.3': 'us.meta.llama3-3-70b-instruct-v1:0',
}

# 使用するモデルの設定
PRIMARY_MODEL = 'claude-3.5-sonnet'
SECONDARY_MODEL = 'llama-3.3'

# 会話の最大ターン数
MAX_CONVERSATION_TURNS = 5

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
