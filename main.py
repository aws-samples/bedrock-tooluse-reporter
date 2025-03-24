from utils import DualLogger, parse_arguments, Conversation
from research import ContextChecker, PerspectiveExplorer, DataSurveyor, ReportWriter
import traceback
from utils import Config, md2html, html2pdf


def main():
    """
    メイン関数 - レポート生成プロセスを制御します
    
    コマンドライン引数を解析し、レポート生成の各ステップを順番に実行します。
    1. コンテキストチェック: ユーザープロンプトの理解と初期情報収集
    2. 視点探索: 複数の視点からトピックを検討
    3. データ調査: レポートに必要なデータの収集
    4. レポート作成: 収集した情報に基づくレポートの執筆
    """
    # コマンドライン引数を解析
    args = parse_arguments()
    conversation = Conversation(args.resume_file)
    timestamp_str = conversation.timestamp_str
    logger = DualLogger(timestamp_str=timestamp_str, log_level=args.log_level)
    logger.info(f"会話履歴ファイルは {conversation.conversation_file} です。")
    config = Config(args.mode)
    logger.debug(args)
    try:
        # ステップ1: コンテキストチェック - トピックの理解と初期情報収集
        context_checker = ContextChecker(
            timestamp_str=timestamp_str,
            logger=logger,
            conversation=conversation,
            user_prompt=args.prompt,
            requested_tools=config.CONTEXT_CHECK_REQUESTED_TOOLS,
            mode=args.mode,
            max_iterate_count=config.MAX_CONTEXT_CHECK_COUNT,
        )
        context_checker_result = context_checker.run()

        # ステップ2: 視点探索 - 複数の視点からトピックを検討
        perspective_explorer_prompt = f"""
<topic>
{args.prompt}
</topic>
<pre-research>
{context_checker_result}
</pre-research>"""
        perspective_explorer = PerspectiveExplorer(
            timestamp_str=timestamp_str,
            logger=logger,
            conversation=conversation,
            user_prompt=perspective_explorer_prompt,
            mode=args.mode,
        )
        report_framework = perspective_explorer.run()

        # ステップ3: データ調査 - レポートに必要なデータの収集
        data_surveyor_prompt = (
            f"<title>{args.prompt}</title><framework>{report_framework}</framework>"
        )
        data_surveyor = DataSurveyor(
            timestamp_str=timestamp_str,
            logger=logger,
            conversation=conversation,
            user_prompt=data_surveyor_prompt,
            requested_tools=config.DATA_SURVEYOR_REQUESTED_TOOLS,
            mode=args.mode,
            max_iterate_count=config.MAX_DATA_SURVEYOR_COUNT,
        )
        survey = data_surveyor.run()

        # ステップ4: レポート作成 - 収集した情報に基づくレポートの執筆
        report_writer_prompt = f"""<title>{args.prompt}</title>
<framework>{report_framework}</framework>
<survey>{survey['survey_result']}</<survey>
<report>{survey['report_path']}</report>"""
        report_generator = ReportWriter(
            timestamp_str=timestamp_str,
            logger=logger,
            conversation=conversation,
            user_prompt=report_writer_prompt,
            requested_tools=config.REPORT_WRITER_REQUESTED_TOOLS,
            mode=args.mode,
            max_iterate_count=99,
        )
        report_markdown_path = report_generator.run()

        # マークダウンからHTMLへ変換
        report_html_path = md2html(report_markdown_path, logger)
        # HTMLからPDFへ変換
        logger.info(html2pdf(report_html_path, logger))

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        print(f"予期しないエラーが発生しました: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
