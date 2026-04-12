# src/helpers/file_utils.py
"""
ファイル・ディレクトリ操作に関するユーティリティ
"""

from pathlib import Path
import yaml
from typing import Dict, Any
import json
from pathlib import Path
from typing import Dict
from PIL import Image
from helpers import string_utils
import base64

def ensure_session_dir(sessions_dir: Path, session_id: str) -> Path:
    """セッションディレクトリを作成してPathを返す"""
    session_dir = sessions_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir

class BlockStyleDumper(yaml.SafeDumper):
    pass

def str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)

BlockStyleDumper.add_representer(str, str_presenter)

def save_yaml_file(file_path: Path, data: Dict[str, Any]) -> bool:
    """YAMLファイルを保存"""
    try:
        print("save_yaml_file start");
        file_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[DEBUG] save target = {file_path}")

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
        print(f"[ERROR] Failed to save YAML {file_path}: {e}")
        return False

def save_json_file(file_path: Path, data: Dict) -> bool:
    """
    JSONファイルを保存するヘルパー関数
    - ディレクトリがなければ自動作成
    - UTF-8で保存（日本語対応）
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[FILE] JSON保存完了: {file_path.name}")
        return True
    except Exception as e:
        print(f"[ERROR] JSON保存失敗 {file_path}: {e}")
        return False
    
def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """YAMLファイルを読み込む"""
    try:
        if not file_path.exists():
            return {}
        with open(file_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[ERROR] Failed to load YAML {file_path}: {e}")
        return {}

def _load_character_data(file_path):
    try:
        suffix = file_path.suffix.lower()

        if suffix == ".json":
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)

        elif suffix == ".png":
            with open(file_path, "rb") as f:
                data = f.read()

            pos = 0
            while True:
                pos = data.find(b"tEXt", pos)
                if pos == -1:
                    break

                length = int.from_bytes(data[pos - 4:pos], "big")
                chunk_data = data[pos + 4:pos + 4 + length]

                if b"\x00" in chunk_data:
                    key_bytes, value_bytes = chunk_data.split(b"\x00", 1)
                    key = key_bytes.decode("ascii", errors="ignore")
                    value = value_bytes.decode("utf-8", errors="ignore")

                    #print(f"[CHAR LOAD] png chunk key: {key}")

                    if key in ["chara", "ccv3", "parameters"]:
                        # 1. data: 形式なら prefix を除去
                        if value.startswith("data:"):
                            value = value.split(",", 1)[1]

                        # 2. base64 → json を試す
                        try:
                            decoded = base64.b64decode(value).decode("utf-8")
                            card_data = json.loads(decoded)
                            if isinstance(card_data, dict):
                                return card_data
                        except Exception as e:
                            print(f"[CHAR LOAD] base64 decode failed: {e}")

                        # 3. そのまま json も試す
                        try:
                            card_data = json.loads(value)
                            if isinstance(card_data, dict):
                                return card_data
                        except Exception as e:
                            print(f"[CHAR LOAD] direct json failed: {e}")

                pos += length + 12

            return {}

        return {}

    except Exception as e:
        print(f"[CHAR LOAD ERROR] {file_path}: {e}")
        return {}

def find_character_memory_file(target: str, session_char_dir: Path):
    target_norm = string_utils._normalize_name(target)

    for file in session_char_dir.glob("*_memory.yaml"):
        name = file.stem.replace("_memory", "")
        name_norm = string_utils._normalize_name(name)

        if target_norm == name_norm or target_norm in name_norm:
            return file

    return None

def _find_character_file(char_name: str, st_char_dir: Path) -> Path | None:
    """スペース無視＋部分一致でキャラカードを探す"""
    target = string_utils._normalize_name(char_name)

    for file in st_char_dir.iterdir():
        if not file.is_file():
            continue

        # 拡張子除去
        name_no_ext = file.stem
        normalized = string_utils._normalize_name(name_no_ext)

        # 完全一致 or 部分一致
        if target == normalized or target in normalized:
            return file

    return None

def apply_dynamic_params_to_characters(session_id: str, dynamic_list: list[dict]):
    from config import config
    from helpers import file_utils

    session_char_dir = config.SESSIONS_DIR / session_id / "character"

    for dynamic in dynamic_list:
        if not isinstance(dynamic, dict):
            continue

        target = dynamic.get("target")
        param_data = dynamic.get("param_data")

        if not target or not param_data:
            continue

        memory_file = file_utils.find_character_memory_file(target, session_char_dir)
        if not memory_file:
            print(f"[DYNAMIC PARAM] target not found: {target}")
            continue

        data = file_utils.load_yaml_file(memory_file) or {}
        data["param_data"] = param_data
        file_utils.save_yaml_file(memory_file, data)

        #print(f"[DYNAMIC PARAM] applied → {memory_file.name}")

#ファイルから会話履歴を読み込み
def load_history(directory_full_path: str) -> list:
    path = create_file(directory_full_path, "history.json")
    if path.exists() and path.stat().st_size > 0:
        with path.open("r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = []

    #不要なt（タイムスタンプ）を落とす
    llm_history = [
        {"role": m["role"], "content": m["content"]}
        for m in history
    ]
    return llm_history

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