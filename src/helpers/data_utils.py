# src/helpers/data_utils.py
"""
データ比較・マージに関するユーティリティ
"""

from typing import Dict, Any


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

