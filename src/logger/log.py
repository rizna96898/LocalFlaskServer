import json
import sys
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


def debug_dump_all(prompt, params):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    ts = int(time.time() * 1000)

    with open(
        log_dir / f"{ts}_prompt.txt",
        "w",
        encoding="utf-8",
    ) as f:
        f.write(repr(prompt))

    with open(
        log_dir / f"{ts}_params.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            params,
            f,
            ensure_ascii=False,
            indent=2,
        )


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
