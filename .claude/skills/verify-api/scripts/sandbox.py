"""サーバーAPIを、本物のデータに触れずに呼ぶための土台。

使い方（検証スクリプトの先頭で）:

    import _env, sandbox
    _env.utf8_stdout()
    _env.run_in_venv(_env.default_sandbox())      # 専用 venv で実行し直す

    box = sandbox.prepare()                        # コピーを作る
    client = box.client()                          # Flask の test_client
    r = client.post("/world_start", json={...})

prepare() がやること:
- LocalFlaskServer の src/ と files/prompts/ をサンドボックスへコピー
- LLM_CHAT_CONSOLE の characters/ players/ worlds/ をコピー
- 設定ファイルはコピーせず、検証用の最小の system_settings.yaml を新しく書く
  （本物にはAPIキーが入っているため）
- sessions/ と sessions_list.yaml は空から始める
- llama_cpp を偽物に差し替える（モデルは読み込まない）

client() がやること:
- モデルサーバーへの送信(requests.post)を差し替える。既定では「接続できない」扱い。
  llm= に文字列か関数を渡すと、その内容をモデルの返事として返す。
  本物のモデルサーバーが同じPCで動いていても、検証からは絶対に呼ばない。
"""
import importlib
import os
import shutil
import sys
import threading
import time
from pathlib import Path

import _env

FAKE_LLAMA = '''class Llama:
    """検証用の偽物。モデルは読み込まない。"""
    loaded = []

    def __init__(self, model_path=None, **kwargs):
        Llama.loaded.append(model_path)

    def reset(self):
        pass

    def __call__(self, **kwargs):
        return {"choices": [{"text": "ok"}], "usage": {}}
'''

VERBOSE = "--verbose" in sys.argv or os.environ.get("LLMCHAT_VERIFY_VERBOSE") == "1"

DEFAULT_SETTINGS = """# 検証用。本物の system_settings.yaml はコピーしない
port: 5000
local_model_use_flag: true
open_router_use_flag: false
"""


class Sandbox:
    def __init__(self, root: Path):
        self.root = root
        self.server = root / "server"          # LocalFlaskServer のコピー
        self.web = root / "web"                # LLM_CHAT_CONSOLE のコピー（データフォルダのみ）
        self.sessions = self.server / "files" / "sessions"
        self.settings_file = self.server / "files" / "settings" / "system_settings.yaml"
        self.llm_calls = []                    # モデルへ送られたプロンプトの記録
        self._app = None

    # 画面が送る base_chat_path に相当する値
    @property
    def base_chat_path(self) -> str:
        return str(self.web)

    def write_settings(self, text: str):
        """設定を書き換える。client() より前に呼ぶこと（config は import 時に読まれる）。"""
        self.settings_file.write_text(text, encoding="utf-8")

    def client(self, llm=None):
        """Flask の test_client を返す。

        llm: None      -> モデルサーバーに接続できない扱い（既定）
             str       -> その文字列をモデルの返事として返す
             callable  -> llm(prompt) の戻り値を返事として返す
        """
        if self._app is None:
            os.chdir(self.server)
            sys.path.insert(0, str(self.root / "fake_llama"))
            sys.path.insert(0, str(self.server / "src"))

            # サーバーのログは量が多く、検証結果が埋もれるので既定では出さない。
            # 失敗の原因を追う時は --verbose を付けるか、LLMCHAT_VERIFY_VERBOSE=1 にする。
            if not VERBOSE:
                server_log = importlib.import_module("logger.log")
                server_log._print_safe = lambda *args, **kwargs: None

            self._app = importlib.import_module("app").app

        import requests

        calls = self.llm_calls

        class _Response:
            status_code = 200

            def __init__(self, text):
                self._text = text

            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [{"text": self._text, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }

        def fake_post(url, *args, **kwargs):
            prompt = (kwargs.get("json") or {}).get("prompt", "")
            calls.append(prompt)
            if llm is None:
                raise requests.exceptions.ConnectionError("検証中のためモデルサーバーには接続しません")
            return _Response(llm(prompt) if callable(llm) else llm)

        requests.post = fake_post
        return self._app.test_client()

    def wait_background(self, timeout: float = 20.0) -> bool:
        """/new_chat が裏で始める記憶生成スレッドの終了を待つ。"""
        end = time.time() + timeout
        while time.time() < end:
            if threading.active_count() == 1:
                return True
            time.sleep(0.2)
        return False

    # ---- 検証でよく使う、リポジトリのデータの手がかり ----
    def worlds(self):
        """[(world_id, 世界YAMLの内容)]"""
        import yaml

        found = []
        for path in sorted((self.web / "worlds" / "settings").glob("*_world.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            found.append((path.name[: -len("_world.yaml")], data))
        return found

    def characters_with_images(self):
        """アイコンと立ち絵の両方を持つキャラクターIDの一覧"""
        ids = []
        for icon in sorted((self.web / "characters" / "icon").glob("*/*.png")):
            cid = icon.parent.name
            if (self.web / "characters" / "standing" / cid / f"{cid}_standing.png").exists():
                ids.append(cid)
        return ids


def _copy_tree(src: Path, dst: Path):
    if dst.exists():
        shutil.rmtree(dst)
    if src.exists():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "backups"))


def prepare(server_repo: Path = None, web_repo: Path = None, root: Path = None) -> Sandbox:
    server_repo = Path(server_repo or _env.SERVER_REPO)
    web_repo = Path(web_repo or _env.WEB_REPO)
    root = Path(root or _env.default_sandbox())

    for repo, must in ((server_repo, "src/app.py"), (web_repo, "js/constant.js")):
        if not (repo / must).exists():
            raise SystemExit(f"リポジトリが見つかりません: {repo}（{must} が無い）")

    box = Sandbox(root)

    _copy_tree(server_repo / "src", box.server / "src")
    _copy_tree(server_repo / "files" / "prompts", box.server / "files" / "prompts")
    _copy_tree(server_repo / "files" / "templates", box.server / "files" / "templates")

    # 実行時データは毎回空から
    for name in ("sessions", "systems", "settings"):
        path = box.server / "files" / name
        if path.exists():
            shutil.rmtree(path)
    box.sessions.mkdir(parents=True)
    box.settings_file.parent.mkdir(parents=True)
    box.write_settings(DEFAULT_SETTINGS)

    for name in ("characters", "players", "worlds"):
        _copy_tree(web_repo / name, box.web / name)

    fake = root / "fake_llama" / "llama_cpp"
    fake.mkdir(parents=True, exist_ok=True)
    (fake / "__init__.py").write_text(FAKE_LLAMA, encoding="utf-8")

    return box


class Checker:
    """結果を1行ずつ出して、最後に失敗数をまとめるだけの小さな道具。"""

    def __init__(self):
        self.failed = 0
        self.total = 0

    def check(self, name: str, ok: bool, detail=""):
        self.total += 1
        self.failed += not ok
        print(("ok  " if ok else "NG  ") + name + (f"  | {detail}" if detail != "" and not ok else ""), flush=True)
        return ok

    def api(self, client, name, method, path, status, ok=None, keys=(), **kwargs):
        """APIを呼び、HTTPステータス・ok の値・必要なキーを確かめる。JSON本文を返す。"""
        response = getattr(client, method)(path, **kwargs)
        body = response.get_json(silent=True) or {}
        problems = []

        if response.status_code != status:
            problems.append(f"status {response.status_code} (期待 {status})")
        if ok is not None and body.get("ok") is not ok:
            problems.append(f"ok={body.get('ok')!r} (期待 {ok})")
        if ok is False and not body.get("message"):
            problems.append("message が無い")
        for key in keys:
            if key not in body:
                problems.append(f"{key} が無い")

        self.check(name, not problems, " / ".join(problems) + f" body={str(body)[:160]}")
        return body

    def finish(self) -> int:
        print(f"\n結果: {self.total - self.failed}/{self.total} 成功" + (f"、{self.failed} 失敗" if self.failed else ""))
        return 1 if self.failed else 0
