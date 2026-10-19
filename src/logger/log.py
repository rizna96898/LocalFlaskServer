import json
import sys
import threading
import time

from datetime import datetime
from pathlib import Path


def _console_safe(*values, sep=" ") -> str:
    encoding = sys.stdout.encoding or "cp932"
    text = sep.join(str(value) for value in values)

    return text.encode(
        encoding,
        errors="replace",
    ).decode(
        encoding,
        errors="replace",
    )


def _print_safe(*values, sep=" ", end="\n"):
    print(
        _console_safe(*values, sep=sep),
        end=end,
        flush=True,
    )


# ---------------------------------------------------------------- モデルへの問い合わせの記録
# logs/{セッションID}/{通し番号}_{時分秒}_{段階}.txt に、1回の問い合わせを1つのファイルで書く。
# 中身は「生成の設定」「送った内容」「返事」の順。セッションに属さないものは logs/_セッション外/ に書く。
# セッションIDと段階は、送る前に set_session / set_step で決めておく（スレッドごとに持つ）。
_log_context = threading.local()
_log_lock = threading.Lock()


def set_session(session_id):
    """これから送る問い合わせが、どのセッションのものか（None ならセッション外）"""
    _log_context.session_id = session_id


def set_step(label):
    """これから送る問い合わせの段階（判定、返事、世界の記憶、服装 など。ファイル名に入る）"""
    _log_context.step = label


def _safe_name(text) -> str:
    # ファイル名に使えない文字を _ にする
    return "".join("_" if c in '\\/:*?"<>|' or ord(c) < 32 else c for c in str(text)).strip() or "_"


def debug_dump_all(prompt, params):
    """送る内容を書き、書いたファイルの場所を返す（返事は debug_dump_response で同じファイルに足す）"""
    session_id = getattr(_log_context, "session_id", None) or "_セッション外"
    step = getattr(_log_context, "step", None) or "問い合わせ"

    log_dir = Path("logs") / _safe_name(session_id)
    with _log_lock:
        log_dir.mkdir(parents=True, exist_ok=True)
        seq = len(list(log_dir.glob("*.txt"))) + 1
        path = log_dir / f"{seq:04d}_{datetime.now().strftime('%H%M%S')}_{_safe_name(step)}.txt"

        with open(path, "w", encoding="utf-8") as f:
            f.write("===== 生成の設定 =====\n")
            f.write(json.dumps(params, ensure_ascii=False, indent=2))
            f.write("\n\n===== 送った内容 =====\n")
            f.write(str(prompt))
            f.write("\n")

    return path


def debug_dump_response(path, text, raw_text=None):
    """返事を、debug_dump_all が書いたファイルの最後に足す。後始末の前と後で違えば、両方書く"""
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n===== 返事 =====\n")
            f.write(text or "")
            if raw_text is not None and raw_text != text:
                f.write("\n\n===== 返事（後始末の前。モデルの返事そのまま） =====\n")
                f.write(raw_text)
            f.write("\n")
    except Exception as e:
        info(f"[LOG] 返事のログを書けませんでした: {e}")


def info(*args):
    _print_safe(
        datetime.now().strftime("%H:%M:%S"),
        *args,
    )


def performance(
    model_name,
    elapsed,
    prompt_tokens,
    completion_tokens,
    total_tokens,
    text_length,
):
    _print_safe("=" * 60)
    _print_safe(f"モデル          : {model_name}")
    _print_safe(f"処理時間        : {elapsed:.2f} 秒")
    _print_safe(f"生成文字数      : {text_length}")
    _print_safe(f"生成Token数     : {completion_tokens}")
    _print_safe(f"Prompt Token    : {prompt_tokens}")
    _print_safe(f"Total Token     : {total_tokens}")

    if elapsed > 0 and completion_tokens:
        _print_safe(
            f"平均生成速度    : "
            f"{completion_tokens / elapsed:.2f} token/s"
        )

    _print_safe("=" * 60)
