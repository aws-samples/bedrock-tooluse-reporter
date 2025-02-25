"""
カスタム例外クラスの定義

このモジュールは、アプリケーション全体で使用される
カスタム例外クラスを定義します。
"""

class ResearchError(Exception):
    """
    リサーチ処理に関する基本例外クラス
    
    アプリケーション内のすべての例外の基底クラスとして機能します。
    """
    pass


class ModelError(ResearchError):
    """
    モデル関連のエラー
    
    AIモデルとの対話中に発生するエラー（API呼び出しの失敗、
    レスポンスの解析エラーなど）を表します。
    """
    pass


class DataCollectionError(ResearchError):
    """
    データ収集に関するエラー
    
    Web検索やコンテンツ取得など、データ収集プロセス中に
    発生するエラーを表します。
    """
    pass


class ReportGenerationError(ResearchError):
    """
    レポート生成に関するエラー
    
    最終レポートの生成や保存中に発生するエラーを表します。
    """
    pass


class ConfigurationError(ResearchError):
    """
    設定関連のエラー
    
    設定の読み込みや検証中に発生するエラーを表します。
    """
    pass


class ToolError(ResearchError):
    """
    ツール関連のエラー
    
    外部ツール（Web検索、コンテンツ取得など）の使用中に
    発生するエラーを表します。
    """
    pass
