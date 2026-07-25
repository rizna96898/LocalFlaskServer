from pathlib import Path
import json, time
from datetime import datetime

def debug_dump_all(prompt, params):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    ts = int(time.time() * 1000)

    with open(log_dir / f"{ts}_prompt.txt", "w", encoding="utf-8") as f:
        f.write(repr(prompt))

    with open(log_dir / f"{ts}_params.json", "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

def info(*args):
    print(datetime.now().strftime("%H:%M:%S"), *args, flush=True)

def section(title):
    print("=" * 60, flush=True)
    print(title, flush=True)
    print("=" * 60, flush=True)

def performance(
    model_name,
    elapsed,
    prompt_tokens,
    completion_tokens,
    total_tokens,
    text_length,
):
    print("=" * 60, flush=True)
    print(f"モデル          : {model_name}", flush=True)
    print(f"処理時間        : {elapsed:.2f} 秒", flush=True)
    print(f"生成文字数      : {text_length}", flush=True)
    print(f"生成Token数     : {completion_tokens}", flush=True)
    print(f"Prompt Token    : {prompt_tokens}", flush=True)
    print(f"Total Token     : {total_tokens}", flush=True)

    if elapsed > 0 and completion_tokens:
        print(
            f"平均生成速度    : {completion_tokens / elapsed:.2f} token/s",
            flush=True,
        )

    print("=" * 60, flush=True)