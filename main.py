"""
メインエントリーポイント
"""
import argparse
import os
from logger import DualLogger
from src.core.research_manager import ResearchManager
from src.utils.exceptions import ResearchError


def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(description='AI Research Assistant')
    parser.add_argument('--prompt', required=True, help='Research prompt/question')
    args = parser.parse_args()

    # ロガーの初期化
    logger = DualLogger()

    try:
        # 研究マネージャーの初期化と実行
        research_manager = ResearchManager(logger)
        html_path, md_path = research_manager.execute_research(args.prompt)

        logger.log(f"研究が完了しました。")
        logger.log(f"HTMLレポート: {html_path}")
        logger.log(f"Markdownレポート: {md_path}")

    except ResearchError as e:
        logger.log(f"エラーが発生しました: {str(e)}")
        return 1
    except Exception as e:
        logger.log(f"予期せぬエラーが発生しました: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
