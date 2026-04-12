# src/config.py
"""
すべての設定を system_settings.yaml から読み込む
helpers.file_utils を使って統一
"""

from pathlib import Path

from helpers.file_utils import load_yaml_file

# プロジェクトルート
ROOT_DIR = Path(__file__).resolve().parent.parent

# ディレクトリ定義
FILES_DIR = ROOT_DIR / "files"
SESSIONS_DIR = FILES_DIR / "sessions"
PROMPTS_DIR = FILES_DIR / "prompts"
SETTINGS_DIR = FILES_DIR / "settings"


class Config:
    def __init__(self):
        # ディレクトリ設定
        self.SESSIONS_DIR = SESSIONS_DIR
        self.PROMPTS_DIR = PROMPTS_DIR
        self.SETTINGS_DIR = SETTINGS_DIR

        # 設定ファイルをヘルパーを使って読み込み
        self.settings = self._load_system_settings()

        # 基本設定
        self.PORT = self.settings.get("port", 5000)
        self.DEFAULT_MODEL = self.settings.get("default_model", "grok-4")
        self.TEMPERATURE = self.settings.get("temperature", 0.85)
        self.MAX_TOKENS = self.settings.get("max_tokens", 2048)

        # OpenRouter関連
        self.OPENROUTER_API_KEY = self.settings.get("openrouter_api_key")
        self.OPENROUTER_SITE_URL = self.settings.get("openrouter_site_url", "http://localhost:5000")
        self.OPENROUTER_SITE_NAME = self.settings.get("openrouter_site_name", "Grok-like RP Backend")
        self.CHARACTERS_DIR = self.settings.get("characters_dir", "no set directory")
        if not self.OPENROUTER_API_KEY or str(self.OPENROUTER_API_KEY).strip() in ["", "dummy"]:
            print("[WARN] openrouter_api_key が設定されていません。files/settings/system_settings.yaml を確認してください。")

    def _load_system_settings(self) -> dict:
        """system_settings.yaml をヘルパー関数を使って読み込む"""
        settings_file = self.SETTINGS_DIR / "system_settings.yaml"
        return load_yaml_file(settings_file)

    def reload(self):
        """設定を再読み込み"""
        self.settings = self._load_system_settings()


# グローバルインスタンス
config = Config()