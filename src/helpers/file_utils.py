# src/helpers/file_utils.py
"""
ファイル・ディレクトリ操作に関するユーティリティ
"""

from __future__ import annotations
import yaml
from typing import Dict, Any
import json
from pathlib import Path
from typing import Dict
from PIL import Image
from helpers import string_utils
import base64
import time
from logger import log

def literal_str_representer(dumper, data):
    return dumper.represent_scalar(
        "tag:yaml.org,2002:str",
        data,
        style="|"
    )

yaml.SafeDumper.add_representer(
    string_utils.LiteralString,
    literal_str_representer
)


def str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)

def save_yaml_file(file_path: Path, data: Dict[str, Any]) -> bool:
    """YAMLファイルを保存"""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(
                data,
                f,
                Dumper=BlockStyleDumper,
                allow_unicode=True,
                sort_keys=False,
                width=1000,
                default_flow_style=False,
            )
        return True
    except Exception as e:
        log.info(f"[ERROR] Failed to save YAML {file_path}: {e}")
        return False

def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """YAMLファイルを読み込む"""
    try:
        if not file_path.exists():
            return {}
        with open(file_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        log.info(f"[ERROR] Failed to load YAML {file_path}: {e}")
        return {}


#ファイルから会話履歴を読み込み
def load_history(directory_full_path: str) -> list:
    path = create_file(directory_full_path, "history.json")
    if path.exists() and path.stat().st_size > 0:
        with path.open("r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = []

    #不要なt（タイムスタンプ）を落とす
    # llm_history = [
    #     {"role": m["role"], "message": m["message"]}
    #     for m in history
    # ]
    return history

        #log.info(f"[DYNAMIC PARAM] applied → {memory_file.name}")

#会話履歴を保存
def save_history(dir_full_path: str, history: list) -> None:
    p = create_file(dir_full_path, "history.json")
    p.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

def create_file(dir_path: str, file_name:str) -> Path:
    SESS_DIR = Path(dir_path)  # 好きな場所に
    # ファイル名に使えるよう最低限サニタイズ
    safe = "".join(c for c in file_name if c.isalnum() or c in ("_", "-", "."))

    file_path = SESS_DIR / f"{safe}"
    file_path.touch(exist_ok=True)
    return file_path


class BlockStyleDumper(yaml.SafeDumper):
    pass
BlockStyleDumper.add_representer(str, str_presenter)
