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
MODELS_DIR = ROOT_DIR / "models"   # ローカルモデル(.gguf)の置き場所。画面のモデルの一覧は、この下を探す

# PCごとの設定。Git で管理しない。system_settings.yaml の上に重ねて読む（書いてある項目だけ上書き）。
# 画面でモデルを切り替えると、ここに local_model_path / local_model_name を書く
LOCAL_SETTINGS_FILE = SETTINGS_DIR / "local_settings.yaml"


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
        self.MODELS_DIR     = MODELS_DIR
        self.LOCAL_SETTINGS_FILE = LOCAL_SETTINGS_FILE

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
        # 一度に扱える文章の長さ（送る内容と返事の合計）。モデルを読み込むときに使う
        self.LOCALMODEL_N_CTX = int(self.settings.get("local_model_n_ctx") or 4096)
        # 作業用領域（KV キャッシュ。n_ctx の分の会話を覚えておく所）の形式。f16（既定）/ q8_0（大きさが半分。質はほとんど落ちない）/ q4_0。
        # f16 以外は flash attention が要るので、モデルサーバーが flash attention も有効にする
        self.LOCALMODEL_KV_CACHE_TYPE = str(self.settings.get("local_model_kv_cache_type") or "f16").lower()
        # flash attention を使うか。計算用の領域も小さくなる（llama-cpp-python の既定は使わない）
        self.LOCALMODEL_FLASH_ATTN = bool(self.settings.get("local_model_flash_attn", False))
        # 窓の分だけ覚える層（SWA。Gemma など）にも、n_ctx の分の作業用領域を取るか。
        # llama.cpp の既定は取る（true）だが、取ると Gemma 4 31B は 8192 で VRAM に載らない。
        # モデルサーバーは返事のたびに作業用領域を空にする（llm.reset()）ので、取らなくても困らない
        self.LOCALMODEL_SWA_FULL = bool(self.settings.get("local_model_swa_full", False))

        # モデルサーバー(src/server.py)。APサーバーと同じPCで動かす前提
        self.LOCALMODEL_SERVER_PORT = self.settings.get("local_model_server_port", 5001)
        self.LOCALMODEL_SERVER_URL = f"http://127.0.0.1:{self.LOCALMODEL_SERVER_PORT}/generate"

        # ローカルモデルへ送る会話の形式。モデルが学習した形式に合わせる。
        #   auto   : 読み込んだモデルに入っている形式（chat_template）から、モデルサーバーが決める（既定）
        #   chatml : <|im_start|>role ... <|im_end|> で区切る形。Qwen 系など
        #   gemma4 : <|turn>role ... <turn|> で区切る形。Gemma 4
        #   alpaca : ### Instruction: / ### Response: の形。mythomax など
        # 形式がモデルと合っていないと、返事が空になったり、延々と思考を書き続けたりする。
        self.LOCALMODEL_PROMPT_FORMAT = str(self.settings.get("local_model_prompt_format") or "auto").lower()

        # true なら、返事の出だしに空の思考ブロックを置き、モデルに思考を書かせない（chatml・gemma4 のときだけ効く）。
        # <think> を logit_bias で禁止する方法は使わない。禁止すると、モデルが第一手を失って空の返事を返す。
        self.LOCALMODEL_NO_THINK = bool(self.settings.get("local_model_no_think", True))

    # system_settings.yaml に、PCごとの設定（local_settings.yaml）を重ねたもの
    def _load_system_settings(self) -> dict:
        settings = self._load_yaml_file(self.SETTINGS_DIR / "system_settings.yaml", required=True)
        local = self._load_yaml_file(self.LOCAL_SETTINGS_FILE, required=False)
        if settings and local:
            settings.update(local)
        return settings

    # PCごとの設定（local_settings.yaml）に values を書き足し、設定を読み直す
    def save_local_settings(self, values: dict):
        local = self._load_yaml_file(self.LOCAL_SETTINGS_FILE, required=False)
        local.update(values)
        with open(self.LOCAL_SETTINGS_FILE, "w", encoding="utf-8") as f:
            f.write("# PCごとの設定。Git で管理しない。system_settings.yaml の同じ項目より優先する。\n")
            f.write("# 画面でモデルを切り替えると書き換わる。\n")
            yaml.safe_dump(local, f, allow_unicode=True, sort_keys=False)
        self.reload()

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