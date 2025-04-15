from utils import BedrockModel, Tools, Config
from datetime import date
import shutil
import os
import json


class BaseReporter:
    """
    レポーター基底クラス

    各種レポート生成クラスの共通機能を提供する基底クラスです。
    AIモデルとの対話、ツールの使用、会話履歴の管理などの基本機能を実装しています。
    """

    def __init__(
        self,
        timestamp_str,
        logger,
        conversation,
        user_prompt,
        requested_tools,
        mode,
        max_iterate_count,
    ):
        """
        BaseReporterの初期化

        Args:
            timestamp_str: タイムスタンプ文字列
            logger: ロガーインスタンス
            conversation: 会話履歴管理インスタンス
            user_prompt: ユーザーからのプロンプト
            requested_tools: 使用するツールのリスト
            mode: 動作モード（short/long）
            max_iterate_count: 最大反復回数
        """
        self.timestamp_str = timestamp_str
        self.conversation_count = 0
        self.config = Config(mode)
        self.requested_tools = requested_tools
        self.logger = logger
        self.conversation = conversation
        self.report_dir = self._set_report_dir()
        self.tools = Tools(
            timestamp_str, logger, requested_tools, mode, self.report_dir
        )
        self.bedrock_runtime = BedrockModel(logger)
        self.iterate_count = 0
        self.messages = self._initialize_messages(user_prompt)
        self.system_prompt = self._define_system_prompt()
        self.max_iterate_count = max_iterate_count
        self.is_finished = False

    def _set_report_dir(self):
        """
        レポートディレクトリを設定

        レポート保存用のディレクトリを作成し、必要に応じて前回のレポートをコピーします。

        Returns:
            str: レポートディレクトリのパス
        """
        if self.conversation.resume_file:
            previous_timestamp_str = self.conversation.resume_file.split("/")[
                1
            ].replace(".yaml", "")
            previous_report_dir = os.path.join(
                self.config.REPORT_DIR, previous_timestamp_str
            )
            self.logger.info(previous_report_dir)

        report_dir = os.path.join(self.config.REPORT_DIR, self.timestamp_str)

        if not os.path.exists(report_dir):
            os.makedirs(report_dir)

        if self.conversation.resume_file:
            if os.path.exists(previous_report_dir):
                shutil.copytree(previous_report_dir, report_dir, dirs_exist_ok=True)

        return report_dir

    def _define_system_prompt(self):
        """
        システムプロンプトを定義

        サブクラスでオーバーライドされることを想定しています。

        Returns:
            str: システムプロンプト
        """
        prompt = f""""""
        return prompt

    def _initialize_messages(self, user_prompt):
        """
        メッセージ履歴を初期化

        既存の会話履歴がある場合はそれを読み込み、なければ新しく作成します。

        Args:
            user_prompt: ユーザーからのプロンプト

        Returns:
            list: 初期化されたメッセージ履歴
        """
        try:
            messages = self.conversation.conversation[self.__class__.__name__]
            for item in messages:
                if item["role"] == "assistant":
                    self.iterate_count += 1

            self.logger.info("Conversation Loaded")
            return messages
        except Exception as e:
            self.logger.error(e)
            self.logger.info(
                f"会話履歴を読み込みませんでした。{self.__class__.__name__} を最初から始めます。"
            )
            messages = [
                {
                    "role": "user",
                    "content": [{"text": user_prompt}],
                }
            ]
            return messages

    def _set_tool_result_message(self, tool_result, tool_use_id):
        """
        ツール実行結果をメッセージ形式に変換

        Args:
            tool_result: ツールの実行結果
            tool_use_id: ツール使用ID

        Returns:
            dict: ツール結果メッセージ
        """
        tool_result_message = {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"text": tool_result}],
                    }
                },
            ],
        }

        if tool_result[0:6] == "Error:":
            tool_result_message["content"][0]["toolResult"]["status"] = "error"
        return tool_result_message

    def _set_messages(self, assistant_message, tool_result_message):
        """
        メッセージ履歴を更新

        Args:
            assistant_message: アシスタントからのメッセージ
            tool_result_message: ツール実行結果のメッセージ

        Returns:
            list: 更新されたメッセージ履歴
        """
        messages = self.messages
        messages.append(assistant_message)
        messages.append(tool_result_message)
        return self.messages

    def generate_response(self, model_id):
        """
        AIモデルからレスポンスを生成

        Args:
            model_id: 使用するAIモデルのID

        Returns:
            dict: AIモデルからのレスポンス
        """
        self.logger.info(self.messages)
        response = self.bedrock_runtime.generate_response(
            model_id=model_id,
            messages=self.messages,
            system_prompt=[{"text": self.system_prompt}],
            inference_config={
                "maxTokens": self.config.BEDROCK.REPORTER.MAX_TOKENS,
                "temperature": self.config.BEDROCK.REPORTER.TEMPERATURE,
                "topP": self.config.BEDROCK.REPORTER.TOP_P,
            },
            tool_config=self.tools.get_tool_config(),
        )
        return response["output"]

    def run(self):
        """
        レポート生成プロセスを実行

        AIモデルとの対話を通じて情報収集や分析を行います。

        Returns:
            任意: サブクラスによって異なる戻り値
        """
        self.logger.info(f"{self.__class__.__name__} Start")
        loop = max(self.max_iterate_count - self.iterate_count, 0)
        for i in range(loop):
            self.logger.info(f"{str(i+1)} /{loop} 回目のループです。")
            assistant_message = self.generate_response(
                self.config.BEDROCK.PRIMARY_MODEL_ID
            ).get("message")
            content_list = assistant_message.get("content")
            # tool 実行 ロジック開始
            for content in content_list:
                if isinstance(content, dict):
                    if "text" in content:
                        self.logger.info(f'AI の思考: {content["text"]}')
                    elif "toolUse" in content:
                        self.logger.info(content["toolUse"])
                        tool_use_id = content["toolUse"]["toolUseId"]
                        tool_name = content["toolUse"]["name"]
                        if tool_name == "is_finished":
                            self.is_finished = True
                            return True
                        else:
                            method = getattr(self.tools, tool_name)
                            # tool 実行と message 作成
                            tool_result = method(**content["toolUse"]["input"])
                            self.logger.info(f"{tool_name} の結果: \n {tool_result}")
                            tool_result_message = self._set_tool_result_message(
                                tool_result, tool_use_id
                            )
                            self.messages = self._set_messages(
                                assistant_message, tool_result_message
                            )
                            self.conversation.save_conversation(
                                self.__class__.__name__, self.messages
                            )
        self.logger.info(f"{self.__class__.__name__} の最大回数に到達しました。")
        return None


class ContextChecker(BaseReporter):
    """
    コンテキストチェッカークラス

    ユーザーの意図を理解し、トピックに関連する基本的な情報を収集します。
    Web検索などのツールを使用して、トピックの背景や関連情報を調査します。
    """

    def __init__(
        self,
        timestamp_str,
        logger,
        conversation,
        user_prompt,
        requested_tools,
        mode,
        max_iterate_count,
    ):
        """
        ContextCheckerの初期化

        Args:
            timestamp_str: タイムスタンプ文字列
            logger: ロガーインスタンス
            conversation: 会話履歴管理インスタンス
            user_prompt: ユーザーからのプロンプト
            requested_tools: 使用するツールのリスト
            mode: 動作モード（short/long）
            max_iterate_count: 最大反復回数
        """
        super().__init__(
            timestamp_str,
            logger,
            conversation,
            user_prompt,
            requested_tools,
            mode,
            max_iterate_count,
        )

    def _define_system_prompt(self):
        """
        コンテキストチェッカー用のシステムプロンプトを定義

        Returns:
            str: システムプロンプト
        """
        prompt = f"""あなたはユーザーの意図を読み取ることに長けた AI です。
ユーザーは <title> タグでトピックを提供します。詳細なレポート作成を後段で行うので、ユーザーの与えるトピックを Web 検索を通じて理解してください。

与えられたトピックについて、<point-of-view> タグで与えた点を明らかにするための情報を収集します。
また、<tools> で与えたツールのみを使用して粛々と情報収集します。
<rules> で与えた制約事項は大切なので遵守してください。
<point-of-view>
* 主要な概念や用語の定義
* 最新のニュースや動向、傾向、話題、研究
* 関連する用語や関連するコンテキスト
* データポイント
* 関連する事例
* 比較対象となりえるもの
</point-of-view>
<tools>
{",".join(self.config.CONTEXT_CHECK_REQUESTED_TOOLS)}
</tools>
<rules>
- あなたが賢いのは知っていますが、一旦すべてのバイアスを除去と最新情報を得るために、例え知っているトピックだったとしてもすべての知識を忘れ、与えられたトピックについて貪欲に学んでください。
- コンテキストがわからない用語も含めてキーワードに分割して調査すること
</rules>

ただしあなたがツールを使える回数は {self.config.MAX_CONTEXT_CHECK_COUNT} 回と限られています。
ユーザーがトピックを与えたら、あなたは必ず最初に、ツールを使うのが何回目か、なぜそのツールを使おうとし、どんな結果を期待しているのかを出力してから <tools> を使って調査を開始してください。"""
        return prompt

    def _organize_data(self, data):
        """
        収集したデータを整理

        ツール使用結果を整理して構造化されたデータに変換します。

        Args:
            data: 収集した生データ

        Returns:
            str: 整理されたデータのJSON文字列
        """
        # 結果を格納する配列
        organized_data = []

        # toolUseIdをキーとする一時的な辞書（処理中のデータ追跡用）
        temp_dict = {}

        # データを走査して、toolUseIdごとにツール使用と結果をまとめる
        for item in data:
            if item["role"] == "assistant" and "content" in item:
                for content_item in item["content"]:
                    if "toolUse" in content_item:
                        tool_use_id = content_item["toolUse"]["toolUseId"]
                        tool_name = content_item["toolUse"]["name"]
                        tool_input = content_item["toolUse"]["input"]

                        # 新しいtoolUseIdの場合、一時辞書に追加
                        if tool_use_id not in temp_dict:
                            temp_dict[tool_use_id] = {
                                "tool": tool_name,
                                "input": tool_input,
                                "result": None,
                            }

            elif item["role"] == "user" and "content" in item:
                for content_item in item["content"]:
                    if "toolResult" in content_item:
                        tool_use_id = content_item["toolResult"]["toolUseId"]

                        # エラーチェック
                        if (
                            "status" in content_item["toolResult"]
                            and content_item["toolResult"]["status"] == "error"
                        ):
                            # エラーの場合は一時辞書から削除
                            if tool_use_id in temp_dict:
                                del temp_dict[tool_use_id]
                        else:
                            # 成功した場合は結果を追加
                            if tool_use_id in temp_dict:
                                temp_dict[tool_use_id]["result"] = content_item[
                                    "toolResult"
                                ]["content"]
                                self.logger.info(
                                    temp_dict[tool_use_id]["result"])
                                # 完成したエントリを配列に追加
                                organized_data.append(temp_dict[tool_use_id])

        return json.dumps(organized_data, ensure_ascii=False)

    def run(self):
        """
        コンテキストチェックプロセスを実行

        トピックに関する基本情報を収集し、整理します。

        Returns:
            str: 整理された情報のJSON文字列
        """
        super().run()
        return self._organize_data(self.conversation.conversation["ContextChecker"])


class DataSurveyor(BaseReporter):
    """
    データ調査員クラス

    レポートフレームワークに基づいて必要なデータを収集します。
    Web検索、コンテンツ取得、画像検索などのツールを使用して、
    レポート作成に必要な情報を網羅的に収集します。
    """

    def __init__(
        self,
        timestamp_str,
        logger,
        conversation,
        user_prompt,
        requested_tools,
        mode,
        max_iterate_count,
    ):
        """
        DataSurveyorの初期化

        Args:
            timestamp_str: タイムスタンプ文字列
            logger: ロガーインスタンス
            conversation: 会話履歴管理インスタンス
            user_prompt: ユーザーからのプロンプト
            requested_tools: 使用するツールのリスト
            mode: 動作モード（short/long）
            max_iterate_count: 最大反復回数
        """
        super().__init__(
            timestamp_str,
            logger,
            conversation,
            user_prompt,
            requested_tools,
            mode,
            max_iterate_count,
        )

    def _define_system_prompt(self):
        """
        データ調査員用のシステムプロンプトを定義

        Returns:
            str: システムプロンプト
        """
        prompt = f"""あなたはデータ調査員です。
ユーザーは <title> タグでトピックを提供します。また、<framework> タグでレポートのフレームワークについて議論した結果を与えます。
詳細なレポート作成は後段で行うので、まず <framework> に沿ったレポートを作成するのに必要十分なデータを徹底的にかき集めてください。
与えられたトピックについて、<point-of-view> タグで与えた点を明らかにするための情報を収集します。
また、<tools> で与えたツールのみを使用して粛々と情報収集します。
<rules> で与えた制約事項は大切なので遵守してください。
<point-of-view>
* 主要な概念や用語の定義
* 最新(ただし現在の日付は{date.today().strftime("%Y/%m/%d")})のニュースや画像
* 関連する用語や関連するコンテキスト
* 関連する最新(ただし現在の日付は{date.today().strftime("%Y/%m/%d")})の動向や傾向や話題
* 関連する最新の研究
* データポイント
* 関連する事例
</point-of-view>
<tools>
<tools>
{",".join(self.config.DATA_SURVEYOR_REQUESTED_TOOLS)}
</tools>
</tools>
<rules>
- あなたが賢いのは知っていますが、一旦すべてのバイアスを除去と最新情報を得るために、例え知っているトピックだったとしてもすべての知識を忘れ、与えられたトピックについて貪欲に調べてください。
- is_finished する前に一度はすべての tools を使うこと
- 後ほど mermaid で可視化するために必要な数値データを見つけること
- レポートに使えそうな画像を image_search で探すこと。視覚情報はレポートの説得力が増すため、is_finished を使う前にかならず image_search を使用する必要があります
</rules>

ただしあなたがツールを使える回数は {self.config.MAX_DATA_SURVEYOR_COUNT} 回と限られています。
ユーザーが情報を与えたら、あなたは必ず最初に、ツールを使うのが何回目か、なぜそのツールを使おうとし、どんな結果を期待しているのかを出力してから <tools> を使って調査を開始してください。"""
        return prompt

    def _organize_data(self, data):
        """
        収集したデータを整理

        ツール使用結果を整理して構造化されたデータに変換します。

        Args:
            data: 収集した生データ

        Returns:
            str: 整理されたデータのJSON文字列
        """
        # 結果を格納する配列
        organized_data = []

        # toolUseIdをキーとする一時的な辞書（処理中のデータ追跡用）
        temp_dict = {}

        # データを走査して、toolUseIdごとにツール使用と結果をまとめる
        for item in data:
            if item["role"] == "assistant" and "content" in item:
                for content_item in item["content"]:
                    if "toolUse" in content_item:
                        tool_use_id = content_item["toolUse"]["toolUseId"]
                        tool_name = content_item["toolUse"]["name"]
                        tool_input = content_item["toolUse"]["input"]

                        # 新しいtoolUseIdの場合、一時辞書に追加
                        if tool_use_id not in temp_dict:
                            temp_dict[tool_use_id] = {
                                "tool": tool_name,
                                "input": tool_input,
                                "result": None,
                            }

            elif item["role"] == "user" and "content" in item:
                for content_item in item["content"]:
                    if "toolResult" in content_item:
                        tool_use_id = content_item["toolResult"]["toolUseId"]

                        # エラーチェック
                        if (
                            "status" in content_item["toolResult"]
                            and content_item["toolResult"]["status"] == "error"
                        ):
                            # エラーの場合は一時辞書から削除
                            if tool_use_id in temp_dict:
                                del temp_dict[tool_use_id]
                        else:
                            # 成功した場合は結果を追加
                            if tool_use_id in temp_dict:
                                temp_dict[tool_use_id]["result"] = content_item[
                                    "toolResult"
                                ]["content"]
                                self.logger.info(
                                    temp_dict[tool_use_id]["result"])
                                # 完成したエントリを配列に追加
                                organized_data.append(temp_dict[tool_use_id])

        return json.dumps(organized_data, ensure_ascii=False)

    def run(self):
        """
        データ調査プロセスを実行

        レポートフレームワークに基づいて必要なデータを収集し、整理します。

        Returns:
            dict: 調査結果とレポートパスを含む辞書
        """
        super().run()
        return {
            "survey_result": self._organize_data(
                self.conversation.conversation["DataSurveyor"]
            ),
            "report_path": os.path.join(self.report_dir, "report.md"),
        }


class ReportWriter(BaseReporter):
    """
    レポート執筆者クラス

    収集したデータとレポートフレームワークに基づいて、
    マークダウン形式のレポートを執筆します。
    """

    def __init__(
        self,
        timestamp_str,
        logger,
        conversation,
        user_prompt,
        requested_tools,
        mode,
        max_iterate_count,
    ):
        """
        ReportWriterの初期化

        Args:
            timestamp_str: タイムスタンプ文字列
            logger: ロガーインスタンス
            conversation: 会話履歴管理インスタンス
            user_prompt: ユーザーからのプロンプト
            requested_tools: 使用するツールのリスト
            mode: 動作モード（short/long）
            max_iterate_count: 最大反復回数
        """
        self.mermaid_description = self._set_mermaid_description()
        super().__init__(
            timestamp_str,
            logger,
            conversation,
            user_prompt,
            requested_tools,
            mode,
            max_iterate_count,
        )

    def _set_mermaid_description(self):
        """
        Mermaid図の説明を読み込み

        Returns:
            str: Mermaid図の説明テキスト
        """
        file_path = os.path.abspath(__file__)
        directory = os.path.dirname(file_path)
        with open(os.path.join(directory, "mermaid.md"), "rt") as f:
            mermaid_description = f.read()
        return mermaid_description

    def _define_system_prompt(self):
        """
        レポート執筆者用のシステムプロンプトを定義

        Returns:
            str: システムプロンプト
        """
        prompt = f"""あなたはレポート執筆者です。
ユーザーは <title> タグでトピックを、<framework> タグでレポートのフレームワークについて議論した結果を、<survey>タグで事前調査結果を、<report>でレポートのファイルパスを与えます。
あなたは <framework> に沿って、各章ごとにマークダウン形式でレポートを執筆してください。
ただし、執筆する際は<rules>で与えた制約を遵守してください。
<rules> で与えた制約事項は大切なので遵守してください。
<rules>
- 最初にこのレポートの目次をアンカーリンク形式で記入してください
    + 目次は大事です。このあとのレポートの全容が決まります
- 目次を作成したあと、「これから X 章を書きます、 X 章には検討の結果 XX な構成で詳細をナレーティブに書きます。」と行った発言をしたあと、write ツールを使ってその章だけを書いてください
    + ただし、目次にない項目は整合性がなくなるため書いてはいけません。必ず書く前に目次に記載があるかどうかをチェックしてください
- 各章・節・項はなるべくナレーティブに詳細を書いてください。どうしても箇条書きを使ったほうがわかりやすい場合は <bullet-detail-example> のように箇条書きの下に必ず詳細な説明文を追加してください。レポートは読み物であり読み手に解釈の幅を持たせてはいけません。解釈が一意になるように詳細を書いてください
- あなたの意見は不要です。<survey> をそのまま、あるいは論理的に導けることだけを書き、<survey> を引用する形で内容を記載してください
    + 引用する際は、マークダウンのリンクを利用し、[引用したテキスト](URL) という形式で書いてください。意味的に引用した箇所は全てリンクにしてください
- 視覚的な情報を積極的に活用してください
    + 取得済の画像の説明文を見ながら適切な場所に画像を差し込んでください
    + マークダウン形式なので ![代替テキスト](画像のパス "画像タイトル") の形式で書いてください
    + markdown は mermaid 記法に対応しています。図示は効果的です。<framework> 内で描かれた mermaid の図や、必ず <survey> から論理的に可視化できる内容やデータを見つけて mermaid で図示してください。使用できる mermaid 記法は <mermaid> で与えます
- マークダウンファイルは <report> タグで与えたファイルパスに追記していってください
- すべての章を書き終えたら is_finished ツールを使って終えてください
</rules>
<bullet-detail-example>
- りんご  
    [リンゴ（林檎、学名: Malus domestica）は、バラ科リンゴ属の落葉高木の一種、またはその果実のことである。植物学上の和名では、セイヨウリンゴともよばれる。中央アジア原産であると考えられているが、紀元前から栽培されるようになり、他種との交雑を経てヨーロッパで確立し、現在では世界中の主に温帯域で栽培されている（→#起源と歴史）。2022年時点での世界におけるリンゴ生産量は約9,600万トンであり、国別では中国が約半分を占めている（→#生産）。日本では遅くとも鎌倉時代以降に中国原産の同属別種であるワリンゴ（Malus asiatica）が栽培され、「リンゴ」とよばれていたが、明治時代にセイヨウリンゴが導入され、一般化するに伴ってセイヨウリンゴが「リンゴ」とよばれるようになった（→#名称）。2023年時点では、日本でのリンゴ生産量は約60万トンであり、青森県が約62%を占めている。](https://ja.wikipedia.org/wiki/%E3%83%AA%E3%83%B3%E3%82%B4)
- オレンジ  
    [オレンジ（甜橙、orange）は、柑橘類に属するミカン科ミカン属の常緑小高木やその果実。特に日本では、原産地インドからヨーロッパを経由して明治時代に日本に導入されたものを「オレンジ」と呼んでいる。オレンジは、ザボン（ブンタン）とマンダリンの交雑種である。葉緑体のゲノムすなわち母系はザボンのものである。スイートオレンジは全ゲノム配列解析済みである。オレンジは、中国南部・インド北東部・ミャンマーを含む地域が発祥で、同果物に関する最初期の言及が紀元前314年の中国文学に見られた。](https://ja.wikipedia.org/wiki/%E3%82%AA%E3%83%AC%E3%83%B3%E3%82%B8)
</bullet-detail-example>
<mermaid>
{self.mermaid_description}
</mermaid>
"""
        return prompt

    def run(self):
        """
        レポート執筆プロセスを実行

        収集したデータとレポートフレームワークに基づいてレポートを執筆します。

        Returns:
            str: 作成したレポートのファイルパス
        """
        super().run()
        return os.path.join(self.report_dir, "report.md")
