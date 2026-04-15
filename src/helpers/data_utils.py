# src/helpers/data_utils.py
"""
データ比較・マージに関するユーティリティ
"""

from typing import Dict, Any
from config import config
import time
from helpers import file_utils

def has_changes(current: Dict[str, Any], new_data: Dict[str, Any], keys_to_check: list = None) -> bool:
    """
    現在のデータと新しいデータに差分があるかチェックする
    
    Args:
        current: 現在のworld.yamlの内容
        new_data: SillyTavernから送られてきた新しいデータ
        keys_to_check: 比較対象のキー（指定しない場合はnew_dataのキー全部）
    
    Returns:
        差分があれば True
    """
    if not new_data:
        return False

    if keys_to_check is None:
        keys_to_check = list(new_data.keys())

    for key in keys_to_check:
        if key in new_data and new_data[key]:
            current_value = current.get(key)
            new_value = new_data[key]
            
            # 文字列の場合は前後の空白を無視して比較
            if isinstance(current_value, str) and isinstance(new_value, str):
                if current_value.strip() != new_value.strip():
                    return True
            else:
                if current_value != new_value:
                    return True
    return False


def merge_character_data(current: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    新しいデータで現在のデータを更新する（差分があるフィールドだけ更新）
    """
    if not new_data:
        return current.copy()

    merged = current.copy()
    
    for key, value in new_data.items():
        if value:  # 新しい値がある場合のみ更新
            if isinstance(value, str):
                merged[key] = value.strip()
            else:
                merged[key] = value

    return merged

def wait_world_ready(session_id: str, timeout_sec=30, interval_sec=0.5):
    world_file = config.SESSIONS_DIR / session_id / "world_memory.yaml"
    # print(f"[WAIT] start session_id={session_id}")
    # print(f"[WAIT] target={world_file}")

    start = time.monotonic()

    while True:
        if timeout_sec > 0 and (time.monotonic() - start) >= timeout_sec:
            print(f"[WAIT] timeout: {session_id}")
            return False

        if not world_file.exists():
            print("[WAIT] world file not exists yet")
            time.sleep(interval_sec)
            continue

        data = file_utils.load_yaml_file(world_file) or {}
        status = data.get("file_status", {}).get("status")
        # print(f"[WAIT] status={status}")

        if status == "ready":
            print(f"[WAIT] world ready: {session_id}")
            return True

        if status == "error":
            print(f"[WAIT] world error: {session_id}")
            return False

        time.sleep(interval_sec)