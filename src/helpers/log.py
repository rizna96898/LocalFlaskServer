from pathlib import Path
import json, time

def debug_dump_all(prompt, params):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    ts = int(time.time() * 1000)

    with open(log_dir / f"{ts}_prompt.txt", "w", encoding="utf-8") as f:
        f.write(repr(prompt))

    with open(log_dir / f"{ts}_params.json", "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)