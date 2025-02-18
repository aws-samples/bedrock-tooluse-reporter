"""
カスタム例外クラスの定義
"""

class ResearchError(Exception):
    """リサーチ処理に関する基本例外クラス"""
    pass

class ModelError(ResearchError):
    """モデル関連のエラー"""
    pass

class DataCollectionError(ResearchError):
    """データ収集に関するエラー"""
    pass

class ReportGenerationError(ResearchError):
    """レポート生成に関するエラー"""
    pass

class ConfigurationError(ResearchError):
    """設定関連のエラー"""
    pass

class ToolError(ResearchError):
    """ツール関連のエラー"""
    pass
