import yaml
import time
import os
from typing import Dict


class Conversation:
    """
    会話履歴管理クラス
    
    AIとの会話履歴を管理し、YAMLファイルとして保存・読み込みを行います。
    会話の再開（レジューム）機能もサポートしています。
    """
    def __init__(self, resume_file):
        """
        会話履歴管理の初期化
        
        Args:
            resume_file: 再開する会話履歴ファイルのパス（Noneの場合は新規作成）
        """
        self.resume_file = resume_file
        self.timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        self.conversation_file = self._set_conversation_file()
        self.conversation = self._load_conversation()
        self.resume = False

    def _set_conversation_file(self):
        """
        会話履歴ファイルのパスを設定
        
        新規作成の場合はタイムスタンプに基づいて新しいファイル名を生成します。
        
        Returns:
            str: 会話履歴ファイルのパス
            
        Raises:
            FileNotFoundError: 指定されたレジュームファイルが存在しない場合
        """
        if self.resume_file is None:
            # 新規作成の場合、会話ディレクトリを確認・作成
            if not os.path.exists("conversation"):
                os.makedirs("conversation")
        else:
            # レジュームファイルが存在するか確認
            if not os.path.exists(self.resume_file):
                raise FileNotFoundError(
                    f"指定されたファイルが見つかりません: {self.resume_file}"
                )
        # 新しい会話ファイルのパスを生成
        conversation_file = "conversation/" + self.timestamp_str + ".yaml"
        return conversation_file

    class OrderedDumper(yaml.Dumper):
        """
        順序付きYAMLダンパー
        
        YAMLファイル出力時に特定のキーを優先的に出力するためのカスタムダンパー
        """
        pass

    @staticmethod
    def _dict_representer(dumper, data):
        """
        辞書のカスタム表現関数
        
        YAMLファイル出力時に'role'と'content'キーを先頭に配置します。
        
        Args:
            dumper: YAMLダンパー
            data: 出力する辞書データ
            
        Returns:
            yaml.nodes.MappingNode: 順序付きマッピングノード
        """
        ordered_keys = []
        if "role" in data:
            ordered_keys.append("role")
        if "content" in data:
            ordered_keys.append("content")

        # 残りのキーを追加（role と content 以外）
        for key in data:
            if key not in ["role", "content"]:
                ordered_keys.append(key)

        # 順序付きマッピングノードを返す
        return dumper.represent_mapping(
            "tag:yaml.org,2002:map", [(key, data[key]) for key in ordered_keys]
        )

    def _load_conversation(self):
        """
        会話履歴を読み込み
        
        レジュームファイルが指定されている場合はそこから読み込み、
        そうでない場合は空の辞書を返します。
        
        Returns:
            dict: 読み込んだ会話履歴
        """
        if self.resume_file:
            with open(self.resume_file, "r") as f:
                conversation = yaml.safe_load(f)
        else:
            conversation = {}
        return conversation

    def save_conversation(self, name: str, messages: Dict):
        """
        会話履歴を保存
        
        指定された名前で会話履歴を保存します。
        
        Args:
            name: 会話コンポーネントの名前
            messages: 保存するメッセージ
        """
        self.conversation[name] = messages
        yaml.add_representer(dict, self._dict_representer, Dumper=self.OrderedDumper)
        with open(self.conversation_file, "wt") as f:
            yaml.dump(
                self.conversation,
                f,
                allow_unicode=True,
                default_flow_style=False,
                Dumper=self.OrderedDumper,
            )
