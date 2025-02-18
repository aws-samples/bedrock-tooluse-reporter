"""
Deep Research Modoki - AI-powered Research Assistant

This module serves as the main entry point for the research assistant application.
It initializes the research process, handles command-line arguments, and manages
the overall execution flow of the research task.

The application takes a research prompt from the user and generates comprehensive
research reports by leveraging AI models and web-based data collection.
"""

import argparse
from logger import DualLogger
from src.core.research_manager import ResearchManager
from src.utils.exceptions import ResearchError


def main():
    """
    Main execution function for the research assistant.

    This function:
    1. Parses command-line arguments to get the research prompt
    2. Initializes the logging system
    3. Creates and executes a research manager instance
    4. Handles any errors that occur during the research process

    Returns:
        int: 0 for successful execution, 1 for errors
    """
    parser = argparse.ArgumentParser(description='AI Research Assistant')
    parser.add_argument('--prompt', required=True, help='Research prompt/question')
    args = parser.parse_args()

    # Initialize logger
    logger = DualLogger()

    try:
        # Initialize and execute research manager
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
