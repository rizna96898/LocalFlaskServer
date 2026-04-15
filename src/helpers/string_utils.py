"""
文字列操作・整形に関するユーティリティ関数
"""
from __future__ import annotations
from typing import List
import re
from copy import deepcopy
from typing import Any
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any
from helpers import string_utils


def clean_for_save(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = text.split("\n")

    result = []
    prev_blank = False

    for line in lines:
        line = line.strip()

        if not line:
            if not prev_blank:
                result.append("")
            prev_blank = True
            continue

        result.append(line)
        prev_blank = False

    while result and result[0] == "":
        result.pop(0)
    while result and result[-1] == "":
        result.pop()

    return "".join(result)


def clean_for_prompt(text: str) -> str:
    """プロンプトに渡す用の整形（モデルに読みやすくする）"""
    if not text:
        return ""
    return clean_for_save(text)


def clean_multiline_text(text: str, max_line_length: int = 1000) -> str:
    """長いテキストをより読みやすく整形する（オプション）"""
    if not text:
        return ""
    cleaned = clean_for_save(text)
    return cleaned


# モデルの応答で```が付くことがあるから消す
def strip_code_block(text: str) -> str:
    pattern = r"^```[a-zA-Z]*\n([\s\S]*?)\n```$"
    match = re.match(pattern, text.strip())
    if match:
        return match.group(1)
    return text


def ensure_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


# 文字列のnullをNoneに変換する
def normalize_nulls(value):
    if isinstance(value, dict):
        return {k: normalize_nulls(v) for k, v in value.items()}

    if isinstance(value, list):
        return [normalize_nulls(v) for v in value]

    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"null", "none", ""}:
            return None

    return value


# モデルの応答で夫:関係のような返却を指定しているのに
# 夫: 関係となりyamlとして困る形式になる為空白を消す
def remove_space(obj) -> str:
    fixed = []
    if not obj:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        fixed = []
        for k, v in obj.items():
            fixed.append(f"{k}：{v}")
        return ",".join(fixed)

    for item in obj:
        if isinstance(item, dict):
            for k, v in item.items():
                fixed.append(f"{k}：{v}")
        else:
            fixed.append(item)

    return ",".join(fixed)


# 改行コードの統一
# pythonコード上は\r\nの為、\rは\nに置換
def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def extract_character_names(text: str, known_names: List[str]) -> List[str]:
    """
    テキストから既知のキャラクター名を部分一致で検知する
    - 空白・全角スペースを除去して比較
    - 誤検知を減らすために最低2文字以上を対象とする
    """
    if not text or not known_names:
        return []

    normalized_text = text.replace(" ", "").replace("　", "").replace("　", "").lower()

    detected = []
    for name in known_names:
        if len(name) < 2:
            continue
        normalized_name = name.replace(" ", "").replace("　", "").replace("　", "").lower()
        if normalized_name in normalized_text and name not in detected:
            detected.append(name)

    return detected


def sanitize_relationships_line(text: str) -> str:
    """relationships行のYAML不正を軽減する"""
    if "relationships:" not in text:
        return text
    return re.sub(r':(?=\S)', ': ', text)


def _convert_to_yaml_format(data: dict) -> dict:
    """必要な項目だけ抽出"""
    return {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "personality": data.get("personality", ""),
        "scenario": data.get("scenario", ""),
        "first_mes": data.get("first_mes", ""),
        "mes_example": data.get("mes_example", ""),
    }


def _normalize_name(name: str) -> str:
    """スペース（全角・半角）を除去して正規化"""
    if not isinstance(name, str):
        return ""
    return name.replace(" ", "").replace("　", "").strip()


WORLD_MEMORY_DEFAULT = {
    "file_status": {
        "status": None,
    },
    "current_state": {
        "time": None,
        "participants": [],
    },
    "world": {
        "world_relationships": [],
    },
}


# 既存コードとの互換用エイリアス
SUMMARY_DEFAULT = WORLD_MEMORY_DEFAULT


def _is_null_like(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        s = value.strip().lower()
        return s in {"", "null", "none", "nil"}
    return False


def _clean_scalar(value: Any) -> Any:
    if _is_null_like(value):
        return None
    if isinstance(value, str):
        return value.strip()
    return value


def _clean_string_or_none(value: Any) -> str | None:
    if isinstance(value, (list, dict)):
        return None

    value = _clean_scalar(value)
    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None

    if value.lower() == "null":
        return None

    return value


def _split_tokens(text: str) -> list[str]:
    """
    カンマ区切り、読点区切り、改行区切り、箇条書きを吸収
    """
    if not text:
        return []

    lines = text.splitlines()
    raw_parts: list[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("-"):
            line = line.lstrip("-").strip()

        parts = re.split(r"[,、]", line)
        for part in parts:
            part = part.strip()
            if part:
                raw_parts.append(part)

    result: list[str] = []
    for item in raw_parts:
        if item not in result:
            result.append(item)
    return result


def _clean_string_list(value: Any) -> list[str]:
    """
    list[str] 用の共通正規化
    - null / "" -> []
    - "A,B" -> ["A", "B"]
    - "- A\n- B" -> ["A", "B"]
    - ["A,B", "- C"] -> ["A", "B", "C"]
    """
    if _is_null_like(value):
        return []

    result: list[str] = []

    if isinstance(value, str):
        return _split_tokens(value)

    if not isinstance(value, list):
        return []

    for item in value:
        if isinstance(item, str):
            for token in _split_tokens(item):
                if token not in result:
                    result.append(token)
        else:
            cleaned = _clean_string_or_none(item)
            if cleaned and cleaned not in result:
                result.append(cleaned)

    return result


def _clean_world_relation(value: Any) -> list[str]:
    return _clean_string_list(value)


def normalize_relationship_item(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    text = text.replace(":", "：")
    text = re.sub(r"：\s*", "：", text)
    return text

def build_characters_text(participants: list[str]) -> str:
    lines = []
    for p in participants:
        if "：" in p:
            name, role = p.split("：", 1)
            lines.append(f"- {name} : {role}")
        else:
            lines.append(f"- {p}")
    return "\n".join(lines)

def normalize_world_memory_data(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = deepcopy(WORLD_MEMORY_DEFAULT)

    if not isinstance(raw, dict):
        return data

    file_status = raw.get("file_status")
    if isinstance(file_status, dict):
        data["file_status"]["status"] = _clean_string_or_none(file_status.get("status"))

    current_state = raw.get("current_state")

    if isinstance(current_state, dict):
        time_val = _clean_string_or_none(current_state.get("time"))
        if not time_val:
            time_val = datetime.now().strftime("%Y年%m月%d日")

        data["current_state"]["time"] = time_val
        data["current_state"]["participants"] = _clean_string_list(current_state.get("participants"))
    else:
        data["current_state"]["time"] = datetime.now().strftime("%Y年%m月%d日")
        data["current_state"]["participants"] = []

    # 新構造を優先し、旧構造 world_relation も互換で読む
    world = raw.get("world")
    if isinstance(world, dict):
        relationships = _clean_world_relation(world.get("world_relationships"))
    else:
        relationships = _clean_world_relation(raw.get("world_relation", []))

    data["world"]["world_relationships"] = [
        normalize_relationship_item(x)
        for x in relationships
    ]

    return data


# 既存コード互換
normalize_summary_data = normalize_world_memory_data


def load_summary(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return normalize_world_memory_data(raw)


def save_summary(path: str, data: dict[str, Any]) -> None:
    normalized = normalize_world_memory_data(data)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            normalized,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )

def extract_dynamic_params_from_mes_example(mes_example: str) -> list[dict]:
    import yaml

    if not mes_example:
        return []

    try:
        parsed = yaml.safe_load(mes_example)
        if not isinstance(parsed, dict):
            return []

        dp = parsed.get("dynamic_params")

        # 単体対応（後方互換）
        if isinstance(dp, dict):
            return [dp]

        if isinstance(dp, list):
            return dp

        return []

    except Exception as e:
        print(f"[DYNAMIC PARAM] parse error: {e}")
        return []

def get_reversed_user_message(messages:list[str]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""

def get_reserved_assistant_message(messages:list[str]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            return msg.get("content", "")
    return ""

def build_current_state_text(current_state: dict[str, Any]) -> str:
    """
    current_state のうち、会話に効きやすいものだけを文字列化する。
    """
    lines: list[str] = []

    location = current_state.get("location")
    if location:
        lines.append(f"場所: {location}")

    status = current_state.get("status")
    if status:
        lines.append(f"状態: {status}")

    action = current_state.get("action") or []
    if action:
        action_list = [str(x) for x in action if x]
        if action_list:
            lines.append("行動:")
            lines.extend(f"- {x}" for x in action_list)

    outfit = current_state.get("outfit") or []
    if outfit:
        outfit_list = [str(x) for x in outfit if x]
        if outfit_list:
            lines.append("服装:")
            lines.extend(f"- {x}" for x in outfit_list)

    mood = current_state.get("mood") or []
    if mood:
        mood_list = [str(x) for x in mood if x]
        if mood_list:
            lines.append("気分:")
            lines.extend(f"- {x}" for x in mood_list)

    participants = current_state.get("participants") or []
    if participants:
        participant_list = [str(x) for x in participants if x]
        if participant_list:
            lines.append("参加者:")
            lines.extend(f"- {x}" for x in participant_list)

    focus_targets = current_state.get("focus_targets") or []
    if focus_targets:
        target_list = [str(x) for x in focus_targets if x]
        if target_list:
            lines.append("注目対象:")
            lines.extend(f"- {x}" for x in target_list)

    # 必要なら後で追加
    # carried_items / money などは今はまだ入れない

    return "\n".join(lines).strip()


def load_prompt_template(prompt_file: Path) -> str:
    """
    prompt yaml からテンプレート文字列を取り出す。

    対応例:
      - YAML自体が文字列
      - {system: "..."}
      - {prompt: "..."}
      - {template: "..."}
      - {content: "..."}
    """
    if not prompt_file.exists():
        raise FileNotFoundError(f"prompt file not found: {prompt_file}")

    with prompt_file.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if isinstance(data, str):
        return data

    if isinstance(data, dict):
        for key in ("system", "prompt", "template", "content"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value

    raise ValueError(f"invalid prompt yaml format: {prompt_file}")

def _merge_memory_data(old_data, new_data):
    if not isinstance(old_data, dict):
        return new_data if isinstance(new_data, dict) else {}
    if not isinstance(new_data, dict):
        return old_data

    result = dict(old_data)

    for key, new_value in new_data.items():
        old_value = result.get(key)

        if isinstance(old_value, dict) and isinstance(new_value, dict):
            result[key] = _merge_memory_data(old_value, new_value)

        elif isinstance(old_value, list) and isinstance(new_value, list):
            result[key] = _dedupe_list(old_value + new_value)

        elif new_value is not None:
            result[key] = new_value

    return result


def _dedupe_list(items: list):
    result = []
    seen = set()

    for item in items:
        if isinstance(item, dict):
            # dictは簡易的にreprキーで重複除去
            marker = repr(item)
        else:
            marker = str(item).strip()

        if not marker:
            continue

        if marker in seen:
            continue

        seen.add(marker)
        result.append(item)

    return result

def find_existing_character(message: str, participants: list[str]) -> list[str]:
    if not message or not participants:
        return []

    result = []

    for name in participants:
        if not name:
            continue

        full_name = name.strip()
        parts = full_name.replace("　", " ").split()

        last_name = parts[0] if len(parts) >= 1 else ""
        first_name = parts[1] if len(parts) >= 2 else ""

        # フルネーム優先
        if full_name and is_valid_hit(message, full_name):
            result.append(full_name)
            continue

        if last_name and is_valid_hit(message, last_name):
            result.append(full_name)
            continue

        if first_name and is_valid_hit(message, first_name):
            result.append(full_name)
            continue

    # 重複除去（念のため）
    return list(dict.fromkeys(result))

def is_valid_hit(message: str, target: str) -> bool:
    return (
        message.startswith(target) or
        f"{target}、" in message or
        f"{target} " in message or
        f"{target}　" in message
    )