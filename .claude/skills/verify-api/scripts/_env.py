"""検証用の共通処理（verify-api / verify-ui の両方に同じファイルを置いている）。

- 検証用フォルダ（サンドボックス）と、その中の専用 venv を用意する
- 呼び出したスクリプトを venv の Python で実行し直す

リポジトリ内の venv/ はサブPC用（E:\\python を指している）で、メインPCでは動かない。
そのため検証は、一時フォルダに作る専用 venv で行う。
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PACKAGES = ["flask", "flask-cors", "pyyaml", "requests", "pillow", "esprima"]

# このファイルは <repo>/.claude/skills/<skill>/scripts/_env.py にある
SERVER_REPO = Path(__file__).resolve().parents[4]
WEB_REPO = SERVER_REPO.parent / "LLM_CHAT_CONSOLE"


def utf8_stdout():
    """Windows のコンソール(cp932)でも日本語を落とさずに出す。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def default_sandbox() -> Path:
    return Path(os.environ.get("LLMCHAT_VERIFY_DIR") or Path(tempfile.gettempdir()) / "llmchat-verify")


def venv_python(sandbox: Path) -> Path:
    sub = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return sandbox / "venv" / sub


def ensure_venv(sandbox: Path) -> Path:
    """専用 venv が無ければ作る。2回目以降は何もしないので速い。"""
    python = venv_python(sandbox)
    marker = sandbox / "venv" / ".packages"
    wanted = " ".join(PACKAGES)

    if python.exists() and marker.exists() and marker.read_text(encoding="utf-8") == wanted:
        return python

    sandbox.mkdir(parents=True, exist_ok=True)
    print(f"[env] 検証用の venv を準備します: {sandbox / 'venv'}", flush=True)

    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(sandbox / "venv")], check=True)

    subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *PACKAGES],
        check=True,
    )
    marker.write_text(wanted, encoding="utf-8")
    return python


def run_in_venv(sandbox: Path):
    """今のスクリプトを専用 venv の Python で実行し直す。既に venv 内なら何もしない。"""
    python = ensure_venv(sandbox)

    if Path(sys.executable).resolve() == python.resolve():
        return

    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    result = subprocess.run([str(python), *sys.argv], env=env)
    sys.exit(result.returncode)
