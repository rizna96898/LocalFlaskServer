# src/helpers/file_utils.py
"""
ファイル・ディレクトリ操作に関するユーティリティ
"""

from __future__ import annotations
from config import config
from pathlib import Path
import yaml
from typing import Dict, Any
import json
from pathlib import Path
from typing import Dict
from PIL import Image
from helpers import string_utils
from helpers import file_utils
import base64
import time

def ensure_session_dir(sessions_dir: Path, session_id: str) -> Path:
    """セッションディレクトリを作成してPathを返す"""
    session_dir = sessions_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir

def get_prepare_status_file(session_id: str) -> Path:
    return config.SESSIONS_DIR / session_id / "prepare_status.yaml"

def mark_prepare_processing(session_id: str, complete_stage: str = "new_chat") -> bool:
    return update_prepare_status(
        session_id,
        status="processing",
        complete_stage=complete_stage,
        error_stage=None,
        error_message=None,
    )

def mark_prepare_ready(session_id: str, complete_stage: str = "new_chat") -> bool:
    return update_prepare_status(
        session_id,
        status="ready",
        complete_stage=complete_stage,
        error_stage=None,
        error_message=None,
    )

def mark_prepare_error(
    session_id: str,
    error_stage: str,
    error_message: str,
    complete_stage: str = "new_chat",
) -> bool:
    return update_prepare_status(
        session_id,
        status="error",
        complete_stage=complete_stage,
        error_stage=error_stage,
        error_message=error_message,
    )

def str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)

def save_yaml_file(file_path: Path, data: Dict[str, Any]) -> bool:
    """YAMLファイルを保存"""
    try:
        # print("save_yaml_file start");
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # print(f"[DEBUG] save target = {file_path}")

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

def find_character_yaml_file(char_name: str, session_char_dir: Path):
    target = string_utils._normalize_name(char_name)

    for path in session_char_dir.glob("*.yaml"):
        if path.name.endswith("_memory.yaml"):
            continue

        raw_name = path.stem
        if string_utils._normalize_name(raw_name) == target:
            return path

    return None

# 引数のキャラに対するmemoryファイルのパスを返却
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

def build_character_comment_system_message(
    session_id: str,
    character_name: str,
    sessions_dir: Path,
    prompt_file: Path,
) -> str:
    """
    キャラ memory の current_state を読み込み、
    character_comment_prompt.yaml のテンプレートに差し込んで
    system_message を返す。

    想定:
      - memory file:
          files/sessions/{session_id}/character/{キャラ名}_memory.yaml
      - prompt file:
          files/prompts/character_comment_prompt.yaml

    prompt yaml の中身は、以下どちらかを想定:
      1. 文字列そのもの
      2. dict で system / prompt / template / content のいずれかを持つ
    """
    # print("session_id", session_id)
    # print("character_name", character_name)
    # print("sessions_dir", sessions_dir)
    memory = get_character_memory(session_id, character_name, sessions_dir)
    if not memory:
        raise ValueError(f"character memory not found: {character_name}")

    current_state = memory.get("current_state", {}) or {}
    current_state_text = string_utils.build_current_state_text(current_state)

    template = string_utils.load_prompt_template(prompt_file)

    system_message = template.format(
        character_name=character_name,
        character_info=current_state_text,
    )

    return system_message

def get_character_memory(
    session_id: str,
    character_name: str,
    sessions_dir: Path,
) -> dict[str, Any] | None:
    """
    files/sessions/{session_id}/character/*_memory.yaml を読み込み、
    指定キャラの memory dict を返す。
    """
    all_memories = load_character_memories(session_id, sessions_dir)
    key = string_utils._normalize_name(character_name)
    return all_memories.get(key)

def load_character_memories(
    session_id: str,
    sessions_dir: Path,
) -> dict[str, dict[str, Any]]:
    """
    files/sessions/{session_id}/character/*_memory.yaml を読み込み、
    {正規化済みキャラ名: YAML内容dict} の形で返す。
    """
    character_memory_dir = sessions_dir / session_id / "character"
    result: dict[str, dict[str, Any]] = {}

    # print("読み込み対象のyamlファイル名", character_memory_dir)

    if not character_memory_dir.exists():
        return result

    for yaml_file in character_memory_dir.glob("*_memory.yaml"):
        try:
            with yaml_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[CHAR MEMORY LOAD ERROR] {yaml_file}: {e}")
            continue

        raw_name = yaml_file.stem.removesuffix("_memory")
        char_name = string_utils._normalize_name(raw_name)

        if char_name in result:
            print(
                f"[CHAR MEMORY WARN] duplicate: raw={raw_name}, normalized={char_name}"
            )

        result[char_name] = data

    return result

# def wait_until_session_memory_ready(
#     session_id: str,
#     timeout_sec: float = 60.0,
#     interval_sec: float = 0.5,
# ) -> bool:
#     """
#     session配下の初期memory作成完了を待つ。

#     判定条件:
#     - world_memory.yaml が存在する
#     - file_status.status == "ready"
#     - character フォルダが存在する
#     - 必要なら *_memory.yaml が1件以上ある

#     戻り値:
#     - True: ready
#     - False: timeout または error
#     """
#     session_dir = config.SESSIONS_DIR / session_id
#     world_memory_file = session_dir / "world_memory.yaml"
#     character_dir = session_dir / "character"

#     started_at = time.monotonic()

#     while True:
#         if timeout_sec > 0 and (time.monotonic() - started_at) >= timeout_sec:
#             print(f"[WAIT] timeout: session_id={session_id}")
#             return False

#         if not world_memory_file.exists():
#             time.sleep(interval_sec)
#             continue

#         world_memory = file_utils.load_yaml_file(world_memory_file) or {}
#         if not isinstance(world_memory, dict):
#             time.sleep(interval_sec)
#             continue

#         file_status = world_memory.get("file_status", {})
#         status = file_status.get("status") if isinstance(file_status, dict) else None

#         if status == "error":
#             print(f"[WAIT] world_memory status=error: session_id={session_id}")
#             return False

#         if status != "ready":
#             time.sleep(interval_sec)
#             continue

#         if not character_dir.exists():
#             time.sleep(interval_sec)
#             continue

#         character_memory_files = list(character_dir.glob("*_memory.yaml"))
#         if not character_memory_files:
#             time.sleep(interval_sec)
#             continue

#         print(f"[WAIT] session ready: session_id={session_id}")
#         return True

def get_prepare_status_path(session_id: str) -> Path:
    return config.SESSIONS_DIR / session_id / "prepare_status.yaml"


def load_prepare_status(session_id: str) -> dict[str, Any]:
    path = get_prepare_status_path(session_id)
    data = load_yaml_file(path) or {}
    return data if isinstance(data, dict) else {}


def create_prepare_status(session_id: str) -> bool:
    return save_yaml_file(
        get_prepare_status_path(session_id),
        {
            "status": "processing",
            "complete_stage": "new_chat",   # new_chat / prepare / main_chat / after
            "error_stage": None,
            "error_message": None,
        },
    )


def update_prepare_status(
    session_id: str,
    *,
    status: str | None = None,
    complete_stage: str | None = None,
    error_stage: str | None = None,
    error_message: str | None = None,
) -> bool:
    path = get_prepare_status_path(session_id)
    data = load_yaml_file(path) or {}

    if not isinstance(data, dict):
        data = {}

    if status is not None:
        data["status"] = status
    if complete_stage is not None:
        data["complete_stage"] = complete_stage
    if error_stage is not None:
        data["error_stage"] = error_stage
    if error_message is not None:
        data["error_message"] = error_message

    return save_yaml_file(path, data)


def mark_prepare_processing(session_id: str, complete_stage: str) -> bool:
    return update_prepare_status(
        session_id,
        status="processing",
        complete_stage=complete_stage,
        error_stage=None,
        error_message=None,
    )


def mark_prepare_ready(session_id: str, complete_stage: str) -> bool:
    return update_prepare_status(
        session_id,
        status="ready",
        complete_stage=complete_stage,
        error_stage=None,
        error_message=None,
    )


def mark_prepare_error(
    session_id: str,
    *,
    complete_stage: str,
    error_stage: str,
    error_message: str,
) -> bool:
    return update_prepare_status(
        session_id,
        status="error",
        complete_stage=complete_stage,
        error_stage=error_stage,
        error_message=error_message,
    )


def wait_until_prepare_status(
    session_id: str,
    *,
    target_stage: str,
    timeout_sec: float = 60.0,
    interval_sec: float = 0.2,
) -> bool:
    """
    prepare_status.yaml が target_stage / ready になるまで待つ
    error なら False
    timeout でも False
    """
    started_at = time.monotonic()

    while True:
        if timeout_sec > 0 and (time.monotonic() - started_at) >= timeout_sec:
            print(f"[WAIT] prepare_status timeout: session_id={session_id}, target_stage={target_stage}")
            return False

        data = load_prepare_status(session_id)
        if not data:
            time.sleep(interval_sec)
            continue

        status = data.get("status")
        complete_stage = data.get("complete_stage")

        if status == "error":
            print(f"[WAIT] prepare_status error: session_id={session_id}, data={data}")
            return False

        if status == "ready" and complete_stage == target_stage:
            print(f"[WAIT] prepare_status ready: session_id={session_id}, target_stage={target_stage}")
            return True

        time.sleep(interval_sec)

class BlockStyleDumper(yaml.SafeDumper):
    pass
BlockStyleDumper.add_representer(str, str_presenter)