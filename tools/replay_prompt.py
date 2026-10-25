"""ログに残った問い合わせを、今のモデルサーバーに送り直して、返事を見比べる。

モデルを替えたときに、前にうまくいかなかった問い合わせ（相談の宛先がずれた、など）で、
新しいモデルがどう答えるかを確かめるための道具。サブPC（モデルサーバーと同じPC）で動かす。

    python tools/replay_prompt.py logs/{セッションID}/0088_165644_相談_shirai_yui.txt --times 5

- ログのファイル（logs/{セッションID}/{通し番号}_{時分秒}_{段階}.txt）から「生成の設定」と「送った内容」を取り出し、
  モデルサーバーの /generate に、そのまま送る。--times の回数だけ送り、返事を順に表示する。
- 結果は logs/_replay/ に、元のログの名前と、読み込み中のモデルの名前を付けて保存する。
  モデルを替えて同じログで流せば、ファイルを並べて見比べられる。
- 元のログに残っている返事（そのときのモデルの答え）も、最初に表示する。
- --temperature を付けると、温度だけ変えて送れる（それ以外の設定はログのとおり）。
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = ROOT / "files" / "settings" / "system_settings.yaml"
REPLAY_DIR = ROOT / "logs" / "_replay"

SETTINGS_MARK = "===== 生成の設定 =====\n"
PROMPT_MARK = "\n\n===== 送った内容 =====\n"
REPLY_MARK = "\n===== 返事 =====\n"
RAW_REPLY_MARK = "\n\n===== 返事（後始末の前。モデルの返事そのまま） =====\n"


def read_log(path: Path):
    """ログのファイルから (生成の設定, 送った内容, そのときの返事) を取り出す"""
    text = path.read_text(encoding="utf-8")
    if not text.startswith(SETTINGS_MARK) or PROMPT_MARK not in text:
        raise SystemExit(f"問い合わせのログの形ではありません: {path}")

    settings_text, rest = text[len(SETTINGS_MARK):].split(PROMPT_MARK, 1)
    params = json.loads(settings_text)

    # 送った内容のあとに改行1つを書き、返事があればその後ろに「===== 返事 =====」が続く
    if REPLY_MARK in rest:
        prompt, reply = rest.split(REPLY_MARK, 1)
        reply = reply.split(RAW_REPLY_MARK, 1)[0].rstrip("\n")
    else:
        prompt, reply = rest, None
    if prompt.endswith("\n"):
        prompt = prompt[:-1]
    return params, prompt, reply


def server_url(args) -> str:
    if args.url:
        return args.url.rstrip("/")
    settings = (yaml.safe_load(SETTINGS_FILE.read_text(encoding="utf-8")) or {}) if SETTINGS_FILE.exists() else {}
    port = settings.get("local_model_server_port") or 5001
    return f"http://127.0.0.1:{port}"


def model_name(base_url: str) -> str:
    try:
        data = requests.get(f"{base_url}/health", timeout=(2, 5)).json()
    except Exception as e:
        raise SystemExit(f"モデルサーバーに接続できません（{base_url}）: {e}")
    if not data.get("model_loaded"):
        raise SystemExit("モデルサーバーに、モデルが読み込まれていません")
    return data.get("model_name") or "unknown"


def safe_name(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("log", help="送り直す問い合わせのログ（logs/{セッションID}/....txt）")
    parser.add_argument("--times", type=int, default=3, help="送る回数（既定: 3）")
    parser.add_argument("--temperature", type=float, help="温度だけ変えて送る")
    parser.add_argument("--url", help="モデルサーバーの場所（既定: 設定の local_model_server_port の 127.0.0.1）")
    args = parser.parse_args()

    log_path = Path(args.log)
    params, prompt, old_reply = read_log(log_path)
    if args.temperature is not None:
        params["temperature"] = args.temperature

    base_url = server_url(args)
    model = model_name(base_url)

    lines = [
        f"元のログ: {log_path}",
        f"モデル: {model}",
        f"生成の設定: {json.dumps(params, ensure_ascii=False)}",
        "",
        "----- 元のログの返事（そのときのモデル） -----",
        old_reply if old_reply is not None else "（返事なし）",
    ]
    print("\n".join(lines), flush=True)

    for no in range(1, args.times + 1):
        started = time.perf_counter()
        try:
            response = requests.post(f"{base_url}/generate", json={"prompt": prompt, **params}, timeout=(10, 600))
            response.raise_for_status()
            reply = (response.json().get("choices") or [{}])[0].get("text") or ""
        except Exception as e:
            reply = f"（失敗: {type(e).__name__}: {e}）"
        block = [f"", f"----- {no}回目（{time.perf_counter() - started:.1f}秒） -----", reply.strip()]
        print("\n".join(block), flush=True)
        lines += block

    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    out = REPLAY_DIR / f"{log_path.stem}__{safe_name(model)}__{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n保存しました: {out}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
