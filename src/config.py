# src/config.py
from pathlib import Path
import yaml   # ← これに変える
from logger import log

# プロジェクトルート
ROOT_DIR = Path(__file__).resolve().parent.parent

# ディレクトリ定義
FILES_DIR = ROOT_DIR / "files"
SYSTEM_DIR = FILES_DIR / "systems"
SESSIONS_DIR = FILES_DIR / "sessions"
PROMPTS_DIR = FILES_DIR / "prompts"
SETTINGS_DIR = FILES_DIR / "settings"
TEMPLATES_DIR = FILES_DIR / "templates"
TEMP_DIR = ROOT_DIR / "temp"   # 記憶生成の途中結果


class Config:
    def __init__(self):

        self.SYSTEM_DIR = SYSTEM_DIR
        self.SESSIONS_DIR = SESSIONS_DIR
        self.PROMPTS_DIR  = PROMPTS_DIR
        self.BOOTSTRAP    = PROMPTS_DIR / "bootstrap"
        self.PREPROCESS   = PROMPTS_DIR / "chat" / "01_preprocess"
        self.MAIN         = PROMPTS_DIR / "chat" / "02_main"
        self.POSTPROCESS  = PROMPTS_DIR / "chat" / "03_postprocess"
        self.SETTINGS_DIR = SETTINGS_DIR

        self.TEMPLATES_DIR  = TEMPLATES_DIR
        self.TEMP_DIR       = TEMP_DIR

        self.settings = self._load_system_settings()

        # 秘密の値（APIキーなど）は、Git で管理しない secrets.yaml に分けて書く
        self.secrets = self._load_yaml_file(self.SETTINGS_DIR / "secrets.yaml", required=False)

        self._apply_settings()

    # 設定ファイルの中身から、各値（config.PORT など）を決める。起動時と、読み直し（reload）のときに呼ぶ。
    # ポート（PORT、LOCALMODEL_SERVER_PORT / URL）は、読み直しても待ち受け中のサーバーには効かない（再起動が要る）
    def _apply_settings(self):
        self.PORT = self.settings.get("port", 5000)
        self.DEFAULT_MODEL = self.settings.get("default_model", "grok-4")
        self.TEMPERATURE = self.settings.get("temperature", 0.85)
        self.MAX_TOKENS = self.settings.get("max_tokens", 2048)

        self.OPENROUTER_API_KEY = self._read_secret("openrouter_api_key")
        self.OPENROUTER_USE_FLAG = self.settings.get("open_router_use_flag")
        self.OPENROUTER_SITE_URL = self.settings.get("openrouter_site_url", "http://localhost:5000")
        self.OPENROUTER_SITE_NAME = self.settings.get("openrouter_site_name", "Grok-like RP Backend")
        self.OPENROUTER_MAX_TOKENS = self.settings.get("openrouter_max_tokens")
        
        self.CHARACTERS_DIR = self.settings.get("characters_dir", "no set directory")

        # 鍵が要るのは OpenRouter を使うときだけ
        if self.OPENROUTER_USE_FLAG and (not self.OPENROUTER_API_KEY or str(self.OPENROUTER_API_KEY).strip() in ["", "dummy"]):
            log.info("[WARN] openrouter_api_key が設定されていません。files/settings/secrets.yaml を確認してください。")

        self.LOCALMODEL_USE_FLAG = self.settings.get("local_model_use_flag")
        self.LOCALMODEL_PATH = self.settings.get("local_model_path")
        # 設定項目名は local_model_name。古い名前 local_mode_name（綴り違い）も、しばらくは読む
        self.LOCALMODEL_NAME = self.settings.get("local_model_name") or self.settings.get("local_mode_name")
        self.LOCALMODEL_MAX_TOKENS = self.settings.get("local_mode_max_tokens")

        # モデルサーバー(src/server.py)。APサーバーと同じPCで動かす前提
        self.LOCALMODEL_SERVER_PORT = self.settings.get("local_model_server_port", 5001)
        self.LOCALMODEL_SERVER_URL = f"http://127.0.0.1:{self.LOCALMODEL_SERVER_PORT}/generate"

        # ローカルモデルへ送る会話の形式。モデルが学習した形式に合わせる。
        #   chatml : <|im_start|>role ... <|im_end|> で区切る形。Qwen 系など
        #   alpaca : ### Instruction: / ### Response: の形。mythomax など
        # 形式がモデルと合っていないと、返事が空になったり、延々と思考を書き続けたりする。
        self.LOCALMODEL_PROMPT_FORMAT = str(self.settings.get("local_model_prompt_format", "chatml")).lower()

        # true なら、返事の出だしに空の思考ブロックを置き、モデルに思考を書かせない（chatml のときだけ効く）。
        # <think> を logit_bias で禁止する方法は使わない。禁止すると、モデルが第一手を失って空の返事を返す。
        self.LOCALMODEL_NO_THINK = bool(self.settings.get("local_model_no_think", True))

    def _load_system_settings(self) -> dict:
        return self._load_yaml_file(self.SETTINGS_DIR / "system_settings.yaml", required=True)

    def _load_yaml_file(self, path: Path, required: bool) -> dict:
        if not path.exists():
            if required:
                log.info(f"[WARN] settings file not found: {path}")
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data if isinstance(data, dict) else {}
        except Exception as e:
            log.info(f"[ERROR] settings load failed: {path.name}: {e}")
            return {}

    # 秘密の値を読む。置き場所は secrets.yaml。
    # system_settings.yaml は Git で管理する（公開される）ので、そちらに書いてあったら移すように促す。
    # 値そのものは、ログにも画面にも出さない。
    def _read_secret(self, name: str):
        value = self.secrets.get(name)

        if name in self.settings:
            log.info(
                f"[WARN] {name} が system_settings.yaml に書かれています。"
                "このファイルは Git で管理されるので、files/settings/secrets.yaml に移してください。"
            )
            if not value:
                value = self.settings.get(name)

        return value

    def reload(self):
        self.settings = self._load_system_settings()
        self.secrets = self._load_yaml_file(self.SETTINGS_DIR / "secrets.yaml", required=False)
        # 読み直した中身で、各値も決め直す（以前は settings だけ読み直し、値は起動時のままだった）
        self._apply_settings()


config = Config()