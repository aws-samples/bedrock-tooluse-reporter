import argparse
import os
from datetime import datetime
from typing import Dict, List

from models import BedrockModel
from conversation_handler import ConversationHandler
from logger import DualLogger
from report_generator import ReportGenerator
from prompts import (
    create_qualification_prompt,
    create_survey_strategy_prompt,
    create_report_generation_prompt,
    create_research_execution_prompt,
)
from config import MODEL_CONFIG, PRIMARY_MODEL, TOOL_CONFIG, MAX_CONVERSATION_TURNS
from search_client import SearchClient


def process_tool_response(model_response):
    """ツールの応答を処理し、必要な情報を抽出する"""
    tool_use = None
    try:
        content_list = (
            model_response.get('output', {}).get('message', {}).get('content', [])
        )
        for content_item in content_list:
            if isinstance(content_item, dict) and 'toolUse' in content_item:
                tool_use = content_item['toolUse']
                break
    except (AttributeError, TypeError):
        return None
    return tool_use


def collect_research_data(
    model: BedrockModel,
    search_client: SearchClient,
    conversation: Dict,
    strategy_text: str,
    user_prompt: str,
    logger: DualLogger,
) -> List[str]:
    """
    情報収集を実行し、結果を返す

    Args:
        model: BedrockModelインスタンス
        search_client: SearchClientインスタンス
        conversation: 会話履歴
        strategy_text: 調査戦略テキスト
        user_prompt: ユーザーのプロンプト
        logger: DualLoggerインスタンス

    Returns:
        List[str]: 収集したデータのリスト
    """
    logger.section("情報収集フェーズ開始")

    research_prompt = create_research_execution_prompt(user_prompt)
    conversation['F'] = []
    conversation['F'].append({"role": "user", "content": [{"text": strategy_text}]})

    collected_data = []
    for i in range(100):  # 最大100回の情報収集試行
        logger.subsection(f"情報収集ステップ {i+1}")

        response = model.generate_response(
            MODEL_CONFIG[PRIMARY_MODEL],
            conversation['F'],
            research_prompt,
            {'temperature': 0},
            TOOL_CONFIG,
        )

        # AIの思考プロセスを出力
        logger.log("AI の思考:")
        for content in response['output']['message']['content']:
            if 'text' in content:
                logger.log(content['text'])
        logger.log("")

        conversation['F'].append(
            {'role': 'assistant', 'content': response['output']['message']['content']}
        )

        tool_use = process_tool_response(response)
        if not tool_use:
            logger.log("情報収集完了（ツール使用なし）")
            break

        if tool_use['name'] == 'is_finished':
            logger.log("情報収集完了（明示的終了）")
            conversation['F'].append(
                {
                    'role': 'user',
                    'content': [
                        {
                            'toolResult': {
                                'toolUseId': tool_use['toolUseId'],
                                'content': [{'text': 'finished'}],
                            }
                        }
                    ],
                }
            )
            break

        # ツールの実行と結果の出力
        logger.log(f"使用ツール: {tool_use['name']}")
        logger.log(f"入力パラメータ: {tool_use['input']}")

        result = None
        if tool_use['name'] == 'search':
            result = search_client.search(**tool_use['input'])
            logger.log("\n検索結果:")
        elif tool_use['name'] == 'get_content':
            result = search_client.get_content(**tool_use['input'])
            logger.log("\nコンテンツ取得結果:")

        if result:
            # 長い結果は省略して表示
            display_result = result[:500] + "..." if len(result) > 500 else result
            logger.log(display_result)

            conversation['F'].append(
                {
                    'role': 'user',
                    'content': [
                        {
                            'toolResult': {
                                'toolUseId': tool_use['toolUseId'],
                                'content': [{'text': result}],
                            }
                        }
                    ],
                }
            )
            collected_data.append(result)

    logger.section("情報収集フェーズ完了")
    return collected_data


def process_tool_response(model_response):
    """ツールの応答を処理し、必要な情報を抽出する"""
    tool_use = None
    try:
        content_list = (
            model_response.get('output', {}).get('message', {}).get('content', [])
        )
        for content_item in content_list:
            if isinstance(content_item, dict) and 'toolUse' in content_item:
                tool_use = content_item['toolUse']
                break
    except (AttributeError, TypeError):
        return None
    return tool_use


def extract_conversation_text(conversation):
    """会話履歴からテキストを抽出"""
    extracted_text = ""
    for c in conversation['F']:
        if 'content' in c:
            for item in c['content']:
                if 'text' in item:
                    extracted_text += item['text'] + "\n\n"
                elif 'toolResult' in item and 'content' in item['toolResult']:
                    for content_item in item['toolResult']['content']:
                        if 'text' in content_item:
                            extracted_text += content_item['text'] + "\n\n"
    return extracted_text


def main():
    parser = argparse.ArgumentParser(description='AI Research Assistant')
    parser.add_argument('--prompt', required=True, help='Research prompt/question')
    args = parser.parse_args()

    # ロガーの初期化
    logger = DualLogger()

    logger.section(f"リサーチ開始: {args.prompt}")

    # 初期化
    model = BedrockModel()
    conversation_handler = ConversationHandler(model, logger)  # ロガーを渡す
    search_client = SearchClient()

    # 会話の実行
    logger.section("初期討議フェーズ")
    logger.log("目的: 調査方針の検討と決定")

    conversation_handler.initialize_conversation(args.prompt)
    qualification_prompt = create_qualification_prompt(
        args.prompt, MAX_CONVERSATION_TURNS
    )
    conversation = conversation_handler.conduct_conversation(qualification_prompt)

    # 調査戦略の生成
    logger.section("調査戦略の生成")
    strategy_prompt = create_survey_strategy_prompt(args.prompt)
    strategy_response = model.generate_response(
        MODEL_CONFIG[PRIMARY_MODEL],
        conversation['A'],
        strategy_prompt,
        {'temperature': 0},
    )
    strategy_text = strategy_response['output']['message']['content'][0]['text']
    logger.log("調査戦略:")
    logger.log(strategy_text)

    # 情報収集の実行
    collected_data = collect_research_data(
        model=model,
        search_client=search_client,
        conversation=conversation,
        strategy_text=strategy_text,
        user_prompt=args.prompt,
        logger=logger,
    )

    # 収集したデータの整理
    logger.section("収集データの整理")
    research_text = extract_conversation_text(conversation)
    logger.log("収集データのサマリー:")
    logger.log(
        research_text[:500] + "..." if len(research_text) > 500 else research_text
    )

    # 最終レポートの生成
    logger.section("最終レポート生成")
    final_messages = [
        {
            "role": "user",
            "content": [
                {"text": f'{research_text}\n\nこれでレポートを書いてください。'}
            ],
        }
    ]

    report_prompt = create_report_generation_prompt(args.prompt, strategy_text)
    final_report = model.generate_response(
        MODEL_CONFIG[PRIMARY_MODEL],
        final_messages,
        [{"text": report_prompt}],
        {'temperature': 1},
    )

    # 最終レポートの出力
    logger.section("最終レポート")
    final_report_text = final_report['output']['message']['content'][0]['text']
    logger.log(final_report_text)

    # レポートの生成
    logger.section("レポートの生成")

    # 出力ディレクトリの作成
    output_dir = 'reports'
    os.makedirs(output_dir, exist_ok=True)

    # ファイル名の生成（日時を含む）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_filename = os.path.join(output_dir, f"report_{timestamp}")

    # レポートの生成（HTML と Markdown）
    try:
        report_generator = ReportGenerator()
        html_path, md_path = report_generator.generate_report(
            final_report_text, base_filename, f"調査レポート: {args.prompt}"
        )
        logger.log(f"HTMLレポートを生成しました: {html_path}")
        logger.log(f"Markdownレポートを生成しました: {md_path}")
    except Exception as e:
        logger.log(f"レポートの生成中にエラーが発生しました: {e}")


if __name__ == "__main__":
    main()
