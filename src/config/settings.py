"""
Configuration settings for Deep Research Modoki
"""

import os
import yaml
from typing import Dict, Any

# デフォルト設定値
# Bedrock モデルの設定
# モデル名とそのAWS Bedrock IDのマッピング
MODEL_CONFIG: Dict[str, str] = {
    "claude-3.5-sonnet": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "claude-3.7-sonnet": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    "claude-3.5-haiku": "us.anthropic.claude-3-haiku-20240307-v1:0",
    "nova-pro": "us.amazon.nova-pro-v1:0",
    "deepseek.r1":"deepseek.r1-v1:0",
    "mistral-large": "mistral.mistral-large-2407-v1:0",
    "llama-3.3": "us.meta.llama3-3-70b-instruct-v1:0",
}

# 使用するモデルの設定
PRIMARY_MODEL = "claude-3.7-sonnet"  # 主要な対話に使用するモデル
SECONDARY_MODEL = "deepseek.r1"  # 二次的な対話に使用するモデル

# 会話の最大ターン数
MAX_CONVERSATION_TURNS = 5
SUMMARY_CONVERSATION_TURNS = 3  # サマリーモードでの会話の最大ターン数

# 調査の最大回数
MAX_PRE_RESEARCH_SEARCHES = 40  # 標準モードでの事前調査の最大検索回数
SUMMARY_PRE_RESEARCH_SEARCHES = 3  # サマリーモードでの事前調査の最大検索回数

MAX_RESEARCH_SEARCHES = 40  # 標準モードでの調査の最大検索回数
SUMMARY_RESEARCH_SEARCHES = 10  # サマリーモードでの調査の最大検索回数

# LLM接続設定
LLM_CONNECTION = {
    "timeout": 1200,  # APIリクエストのタイムアウト（秒）
    "max_retries": 8,  # 最大リトライ回数
    "base_delay": 20,  # 初期バックオフ遅延（秒）
    "max_delay": 300,  # 最大バックオフ遅延（秒）
    "profiles": [  # 使用するAWSプロファイル名のリスト
        "default"
    ]
}


# ツール設定
TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "search",
                "description": "検索する文章、キーワードを受け取って Web 検索する",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "検索する文章またはキーワード。半角スペースで区切ることで複数のキーワードを受け付ける。",
                            }
                        },
                        "required": ["query"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_content",
                "description": "URL にアクセスして html のコンテンツを取得",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "情報を取得したい URL",
                            }
                        },
                        "required": ["url"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "image_search",
                "description": "画像を検索、取得して保存する",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "検索する画像のキーワード。半角スペースで区切ることで複数のキーワードを受け付ける。",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "取得する最大画像数（デフォルト: 5）",
                            },
                        },
                        "required": ["query"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "generate_graph",
                "description": "データからグラフを生成する",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "graph_type": {
                                "type": "string",
                                "description": "グラフの種類（line: 折れ線グラフ, bar: 棒グラフ, pie: 円グラフ, scatter: 散布図）",
                                "enum": [
                                    "line",
                                    "bar",
                                    "pie",
                                    "scatter",
                                    "horizontal_bar",
                                ],
                            },
                            "title": {
                                "type": "string",
                                "description": "グラフのタイトル",
                            },
                            "x_label": {
                                "type": "string",
                                "description": "X軸のラベル（折れ線グラフ、棒グラフ、散布図の場合）",
                            },
                            "y_label": {
                                "type": "string",
                                "description": "Y軸のラベル（折れ線グラフ、棒グラフ、散布図の場合）",
                            },
                            "labels": {
                                "type": "array",
                                "description": "データのラベル（X軸の値や凡例）",
                                "items": {"type": "string"},
                            },
                            "data": {
                                "type": "array",
                                "description": "グラフ化するデータ値",
                                "items": {"type": "number"},
                            },
                            "series_labels": {
                                "type": "array",
                                "description": "複数系列がある場合の系列ラベル（オプション）",
                                "items": {"type": "string"},
                            },
                            "multi_data": {
                                "type": "array",
                                "description": "複数系列のデータ（オプション）。各系列のデータ配列を含む2次元配列。",
                                "items": {"type": "array", "items": {"type": "number"}},
                            },
                            "colors": {
                                "type": "array",
                                "description": "グラフの色（オプション）",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["graph_type", "title"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "render_mermaid",
                "description": "Mermaid形式のコードからダイアグラムや図表を生成する",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "mermaid_code": {
                                "type": "string",
                                "description": "Mermaid形式のテキストを渡すと、Mermaid形式の文字列を渡すと図を作成する。Mermaid形式には全て対応しており、Flowchat,Sequence Diagram,Class Diagram, State Diagram, Gantt, Pie chart, Quadrant Chart, Git diagram, Mindmaps, ZenUML, Sankky, XY Chart, Block Diagram, Packet, Kanban, Architecture等が作成できます。",
                            },
                            "title": {
                                "type": "string",
                                "description": "図表のタイトル（オプション）",
                            },
                        },
                        "required": ["mermaid_code"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "is_finished",
                "description": "ツールの利用が完了し、次のステップに進む関数",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    }
                },
            }
        },
    ]
}

# 出力ディレクトリ設定
OUTPUT_DIR = {
    "logs": "logs",
    "reports": "reports",
}

# プロンプト設定
PROMPT_CONFIG = {
    "max_tokens": 8192,  # 最大トークン数
    "temperature": {
        "default": 0.8,  # デフォルトの温度設定
        "strategy": 0,  # 戦略生成時の温度設定
    },
}

# 引用形式設定
CITATION_FORMAT = {
    "prefix": "[※",
    "suffix": "]",
    "reference_title": "参考文献",
}

# レポート設定
REPORT_CONFIG = {
    "max_attempts": 10,  # レポート生成の最大試行回数
    "completion_markers": [  # レポート完了を示すマーカー
        "レポートの終了",
        "レポートは終了",
        "レポートを終了",
        "レポートは完了",
        "レポートの完了",
        "レポートを完了",
    ],
    "output_mode": {
        "standard": "chapter",  # 標準モードでは章ごとに出力
        "summary": "full",  # サマリーモードではレポート全体を一度に出力
    },
}

# 画像設定
IMAGE_CONFIG = {
    "max_images": 10,  # 1回の検索で取得する最大画像数
    "max_size": 5 * 1024 * 1024,  # 画像の最大サイズ（5MB）
    "allowed_formats": ["jpg", "jpeg", "png", "gif", "webp"],  # 許可する画像形式
}

# PDF設定
PDF_CONFIG = {
    "max_size": 50 * 1024 * 1024,  # PDFの最大サイズ（50MB）
    "bedrock_max_size": 4.3
    * 1024
    * 1024,  # Bedrock APIの最大サイズ（up to 4.5MB in rawdata）
}

# グラフ設定
GRAPH_CONFIG = {
    "default_figsize": (10, 6),  # デフォルトのグラフサイズ（インチ）
    "dpi": 100,  # 解像度（dots per inch）
    "default_colors": [  # デフォルトの色パレット
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ],
}

class Config:
    # 設定ファイルからの読み込み関数
    def load_config(config_path: str = None) -> None:
        """
        設定ファイルから設定を読み込み、グローバル変数を更新する

        Args:
            config_path: 設定ファイルのパス。Noneの場合はデフォルト値を使用
        """
        global MODEL_CONFIG, PRIMARY_MODEL, SECONDARY_MODEL
        global MAX_CONVERSATION_TURNS, SUMMARY_CONVERSATION_TURNS
        global MAX_PRE_RESEARCH_SEARCHES, SUMMARY_PRE_RESEARCH_SEARCHES
        global MAX_RESEARCH_SEARCHES, SUMMARY_RESEARCH_SEARCHES
        global LLM_CONNECTION
        
        if not config_path or not os.path.exists(config_path):
            if config_path:
                print(f"警告: 設定ファイル {config_path} が見つかりません。デフォルト値を使用します。")
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
            
            if not config:
                print("警告: 設定ファイルが空か無効です。デフォルト値を使用します。")
                return
                
            # モデル設定の更新
            if 'models' in config:
                MODEL_CONFIG.update(config['models'])
            
            # 主要モデル設定の更新
            if 'primary_model' in config:
                PRIMARY_MODEL = config['primary_model']
            
            # 二次モデル設定の更新
            if 'secondary_model' in config:
                SECONDARY_MODEL = config['secondary_model']
            
            # 会話設定の更新
            if 'conversation' in config:
                conv_config = config['conversation']
                if 'max_turns' in conv_config:
                    MAX_CONVERSATION_TURNS = conv_config['max_turns']
                if 'summary_turns' in conv_config:
                    SUMMARY_CONVERSATION_TURNS = conv_config['summary_turns']
            
            # 調査設定の更新
            if 'research' in config:
                research_config = config['research']
                if 'max_pre_searches' in research_config:
                    MAX_PRE_RESEARCH_SEARCHES = research_config['max_pre_searches']
                if 'summary_pre_searches' in research_config:
                    SUMMARY_PRE_RESEARCH_SEARCHES = research_config['summary_pre_searches']
                if 'max_searches' in research_config:
                    MAX_RESEARCH_SEARCHES = research_config['max_searches']
                if 'summary_searches' in research_config:
                    SUMMARY_RESEARCH_SEARCHES = research_config['summary_searches']
            
            # LLM接続設定の更新
            if 'connection' in config:
                conn_config = config['connection']
                for key, value in conn_config.items():
                    if key in LLM_CONNECTION:
                        LLM_CONNECTION[key] = value
            
            print("設定ファイルから設定を読み込みました。")
            
        except Exception as e:
            print(f"設定ファイルの読み込み中にエラーが発生しました: {str(e)}")
            print("デフォルト設定を使用します。")

    # 現在の設定を表示する関数
    def display_config() -> None:
        """現在の設定値を表示する"""
        print("\n=== Deep Research Modoki 設定 ===")
        
        print("\n--- モデル設定 ---")
        for model_name, model_id in MODEL_CONFIG.items():
            print(f"  {model_name}: {model_id}")
        
        print(f"\n主要モデル: {PRIMARY_MODEL}")
        print(f"二次モデル: {SECONDARY_MODEL}")
        
        print("\n--- 会話設定 ---")
        print(f"  最大ターン数: {MAX_CONVERSATION_TURNS}")
        print(f"  サマリーモードのターン数: {SUMMARY_CONVERSATION_TURNS}")
        
        print("\n--- 調査設定 ---")
        print(f"  標準モードの事前調査検索回数: {MAX_PRE_RESEARCH_SEARCHES}")
        print(f"  サマリーモードの事前調査検索回数: {SUMMARY_PRE_RESEARCH_SEARCHES}")
        print(f"  標準モードの調査検索回数: {MAX_RESEARCH_SEARCHES}")
        print(f"  サマリーモードの調査検索回数: {SUMMARY_RESEARCH_SEARCHES}")
        
        print("\n--- 接続設定 ---")
        print(f"  タイムアウト: {LLM_CONNECTION['timeout']} 秒")
        print(f"  最大リトライ回数: {LLM_CONNECTION['max_retries']}")
        print(f"  初期遅延: {LLM_CONNECTION['base_delay']} 秒")
        print(f"  最大遅延: {LLM_CONNECTION['max_delay']} 秒")
        print(f"  プロファイル: {', '.join(LLM_CONNECTION['profiles'])}")
        print("\n=======================================")
