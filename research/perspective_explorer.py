from utils import BedrockModel, Config
import json


class PerspectiveExplorer:
    """
    視点探索クラス

    トピックに対して複数の視点から検討を行い、レポートのフレームワークを構築します。
    2つの異なるAIモデル間の対話を通じて、多角的な視点を得ることを目的としています。
    """

    def __init__(
        self,
        timestamp_str,
        logger,
        conversation,
        user_prompt: str,
        mode,
    ):
        """
        PerspectiveExplorerの初期化

        Args:
            timestamp_str: タイムスタンプ文字列
            logger: ロガーインスタンス
            conversation: 会話履歴管理インスタンス
            user_prompt: ユーザーからのプロンプト
            mode: 動作モード（short/long）
        """
        self.timestamp_str = timestamp_str
        self.perspective_explorer_count = 0
        self.config = Config(mode)
        self.logger = logger
        self.conversation = conversation
        self.bedrock_runtime = BedrockModel(logger)
        self.max_perspective_explorer_count = self.config.MAX_PERSPECTIVE_EXPLORER_COUNT
        self.context_check_result = self._set_context_check_result()
        self.messages = self._initialize_messages(user_prompt)
        self.system_prompt = self._define_system_prompt()

    def _define_system_prompt(self):
        """
        システムプロンプトを定義

        Returns:
            str: システムプロンプト
        """
        prompt = f"""あなたは優秀なリサーチャー AI です。
会話相手はあなたと同じ調査内容で依頼を受けている同僚の AI さんです。
最初に <topic> タグで調査のトピックを、<pre-research> タグで事前の調査内容が与えらます。
調査内容はキーワードや意味の列挙なので、調査の粒度や観点などは仮説を持って調査をした後調査結果を作成し、調査結果のフィードバックをもらうことでしか改善できません。
AI さんはあなたの思考の枠を外して広い視野を提供してくれます。
あなたも調査内容を自由に広げて網羅性を高め、その後どんなことを調べるのかを深めていってください。
特に反対意見や出ていない意見は大事です。既出の意見はそんなに重要ではありません。
お互いの網羅性や深さの不足を指摘しながらAI さんとの会話を重ね、リサーチする内容を決めていってください。
会話はお互い {self.max_perspective_explorer_count} 回までしかできないので、それまでに議論をまとめてください。
ただし会話は <rules> を遵守してください。
<rules>
* 具体的にどんなことをするのか actionable にまとめる必要があります。
* 予算や人員については触れてはいけません。調査する内容にだけフォーカスしてください。
* 調査対象に関わるだろう人の観点を複数入れてください。例えば料理であれば、調理器具をつくる人、食材を売る人、食材を買う人、食材を運ぶ人、料理を作る人、料理を運ぶ人、食べる人、口コミを書く人、ゴミを捨てる人、などです。与えられたお題に反しない限り様々な人に思いを巡らせてください。
* 会話を始める前に、自分がどのように考えたのか、を述べてから結論を述べてください。
* さまざまな観点から内容をブラッシュアップしてください。
* 事前調査に基づき、画像取得や作成したグラフ画像などの視覚的な情報をできるだけ活用することを検討してください。
* 説明をよりわかりやすく整理するために mermaid 形式を必要に応じて利用し、sequence / class / er diagram / mindmap / pie / gantt / quadrant / gitgraph / timeline / sankey-beta / architecture-beta などを議論上の整理に用いてください。
</rules>
発言する際は最初に必ず x 回目の発言です、と言ってください。発言回数は自分の発言回数であり、相手の発言はカウントしてはいけません。
また、最後の発言は必ずレポート全体のフレームワークを詳細に説明してください。
"""
        return prompt

    def _initialize_messages(self, user_prompt):
        """
        メッセージ履歴を初期化

        既存の会話履歴がある場合はそれを読み込み、なければ新しく作成します。

        Args:
            user_prompt: ユーザーからのプロンプト

        Returns:
            dict: 初期化されたメッセージ履歴
        """
        try:
            primary = self.conversation.conversation[self.__class__.__name__]["primary"]
            secondary = self.conversation.conversation[self.__class__.__name__][
                "secondary"
            ]
            for item in secondary:
                if item["role"] == "assistant":
                    self.perspective_explorer_count += 1

            self.logger.info("Conversation Loaded")
            return {"primary": primary, "secondary": secondary}
        except Exception as e:
            self.logger.error(e)
            self.logger.info(
                f"会話履歴を読み込みませんでした。{self.__class__.__name__} を最初から始めます。"
            )
            messages = {
                "primary": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": f"""今回のトピックと事前調査結果は以下の通りです。
{user_prompt}
一緒に調査内容を検討しましょう。よろしくお願いします。まずは何かアイデアはありますか？"""
                            }
                        ],
                    }
                ],
                "secondary": [],
            }
            return messages

    def _set_context_check_result(self):
        """
        コンテキストチェック結果を設定

        Returns:
            str: コンテキストチェック結果のJSON文字列
        """
        messages = self.conversation.conversation["ContextChecker"]
        return json.dumps(messages, ensure_ascii=False)

    def generate_response(self, model_id, is_primary=True):
        """
        AIモデルからレスポンスを生成

        Args:
            model_id: 使用するAIモデルのID
            is_primary: プライマリモデルかどうか

        Returns:
            dict: AIモデルからのレスポンス
        """
        messages_to_use = (
            self.messages["primary"] if is_primary else self.messages["secondary"]
        )
        self.logger.info(messages_to_use)
        response = self.bedrock_runtime.generate_response(
            model_id=model_id,
            messages=messages_to_use,
            system_prompt=[{"text": self.system_prompt}],
            inference_config={
                "maxTokens": self.config.BEDROCK.PERSPECTIVE_EXPLORER.MAX_TOKENS,
                "temperature": self.config.BEDROCK.PERSPECTIVE_EXPLORER.TEMPERATURE,
                "topP": self.config.BEDROCK.PERSPECTIVE_EXPLORER.TOP_P,
            },
        )
        return response["output"]

    def _remove_reasoning(self, message):
        """
        AIの思考プロセス部分を抽出し、メッセージを整形

        Args:
            message: AIからのレスポンスメッセージ

        Returns:
            tuple: (アシスタントメッセージ, ユーザーメッセージ)
        """
        content = message.get("content", [])
        text = content[0].get("text", "") if content else ""

        # reasoningContent が存在するか確認
        reasoning_content = content[0].get("reasoningContent") if content else None
        reasoning_text = ""

        # reasoningContent が存在する場合のみ、その中のデータを取得
        if reasoning_content:
            reasoning_text_obj = reasoning_content.get("reasoningText")
            if reasoning_text_obj:
                reasoning_text = reasoning_text_obj.get("text", "")

        assistant_message = {
            "role": "assistant",
            "content": [{"text": reasoning_text + text}],
        }
        user_message = {
            "role": "user",
            "content": [{"text": reasoning_text + text}],
        }
        return assistant_message, user_message

    def run(self):
        """
        視点探索プロセスを実行

        2つのAIモデル間で対話を行い、多角的な視点からトピックを検討します。

        Returns:
            str: 最終的なレポートフレームワーク
        """
        self.logger.info(f"{self.__class__.__name__} Start")
        loop = max(
            self.max_perspective_explorer_count - self.perspective_explorer_count, 0
        )
        for _ in range(loop):
            self.logger.info(
                f"{self.config.BEDROCK.PRIMARY_MODEL_ID}: {self.perspective_explorer_count + 1} 回目の発言です。"
            )
            primary_message = self.generate_response(
                self.config.BEDROCK.PRIMARY_MODEL_ID, is_primary=True
            ).get("message")

            assistant_message, user_message = self._remove_reasoning(primary_message)

            self.messages["primary"].append(assistant_message)
            self.messages["secondary"].append(user_message)
            self.logger.info(
                f"{self.config.BEDROCK.SECONDARY_MODEL_ID}: {self.perspective_explorer_count + 1} 回目の発言です。"
            )
            secondary_message = self.generate_response(
                self.config.BEDROCK.SECONDARY_MODEL_ID, is_primary=False
            ).get("message")

            assistant_message, user_message = self._remove_reasoning(secondary_message)

            self.messages["secondary"].append(assistant_message)
            self.messages["primary"].append(user_message)
            self.conversation.save_conversation(self.__class__.__name__, self.messages)
        # 会話の最後にレポートのフレームワーク最終版が入るのでそれだけ返す
        return self.messages["primary"][-1]["content"][0]["text"]
