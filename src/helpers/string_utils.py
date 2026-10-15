"""
文字列操作・整形に関するユーティリティ関数
"""
from __future__ import annotations
from typing import List
import re
import time
from copy import deepcopy
from typing import Any
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any
from helpers import string_utils
from logger import log

class LiteralString(str):
    pass


# モデルの応答で```が付くことがあるから消す
def strip_code_block(text: str) -> str:
    pattern = r"^```[a-zA-Z]*\n([\s\S]*?)\n```$"
    match = re.match(pattern, text.strip())
    if match:
        return match.group(1)
    return text

import re

def cleanup_model_output(text: str) -> str:
    # <think>...</think> を丸ごと削除
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # 片方だけ出たタグも削除
    text = text.replace("<think>", "")
    text = text.replace("</think>", "")

    # ### Response: が混ざった時用
    if "### Response:" in text:
        text = text.split("### Response:", 1)[-1]

    return text.strip()


# 改行コードの統一
# pythonコード上は\r\nの為、\rは\nに置換
def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


# def _convert_to_yaml_format(data: dict) -> dict:
#     """必要な項目だけ抽出"""
#     return {
#         "name": data.get("name", ""),
#         "description": data.get("description", ""),
#         "personality": data.get("personality", ""),
#         "scenario": data.get("scenario", ""),
#         "first_mes": data.get("first_mes", ""),
#         "mes_example": data.get("mes_example", ""),
#     }


_DEFAULT = {
    "プレイヤーID": "",
    "プレイヤー名": "",
    "現在の状態": {
        "日付": None,
        "参加者": [],
        "パーティー一覧": []
    },
    "世界の状態": {
        "参加者": [],
    },
}


# 既存コードとの互換用エイリアス
SUMMARY_DEFAULT = _DEFAULT


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


def normalize_person_item(item: Any) -> dict[str, Any] | None:
    """
    name/role 形式の人物データに正規化する。
    旧形式 "名前：役割" も一応吸収。
    """
    character_str = "キャラクターID"
    name_str = "名前"
    role_str = "役割"

    if isinstance(item, dict):
        id = _clean_string_or_none(item.get(character_str))
        name = _clean_string_or_none(item.get(name_str))
        role = _clean_string_or_none(item.get(role_str))
        if not name:
            return None

        result = {character_str: id}
        if name:
            result[name_str] = name

        if role:
            result[role_str] = role
        return result

    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None

        if "：" in text:
            id, name, role = text.split("：", 1)
        elif ":" in text:
            id, name, role = text.split(":", 1)
        else:
            id, name, role = text, ""

        id = id.strip()
        name = name.strip()
        role = role.strip()

        if not id:
            return None

        result = {character_str: id}

        if name:
            result[name_str] = name

        if role:
            result[role_str] = role
        return result

    return None


def normalize_person_list(value: Any) -> list[dict[str, Any]]:
    if _is_null_like(value):
        return []

    if not isinstance(value, list):
        return []

    result: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in value:
        normalized = normalize_person_item(item)
        log.info("normalized", normalized)
        if not normalized:
            continue

        id = normalized["キャラクターID"]
        if id in seen:
            continue

        name = normalized["名前"]
        if name in seen:
            continue

        seen.add(id)
        seen.add(name)
        result.append(normalized)

    return result


def normalize_parties(value: Any) -> list[dict[str, Any]]:
    member_str = "メンバー一覧"
    name_str = "名前"
    character_id = "キャラクターID"

    if _is_null_like(value):
        return []

    if not isinstance(value, list):
        return []

    result: list[dict[str, Any]] = []

    for item in value:

        if not isinstance(item, dict):
            continue

        name = _clean_string_or_none(item.get(name_str))
        members_raw = item.get(member_str)

        if not name:
            continue

        members: list[str] = []
        if isinstance(members, list):
            for member in members_raw:
                if isinstance(member, dict):
                    members.append({
                        character_id: member.get(character_id),
                        name_str: member.get(name_str),
                    })

        if not members:
            continue

        result.append({
            name_str: name,
            member_str: members,
        })

    return result


def normalize_world_memory_data(player_id: str, player_name: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    current_state_str = "現在の状態"
    world_state_str = "世界の状態"
    player_id_str = "プレイヤーID"
    player_name_str = "プレイヤー名"
    date_str = "日付"
    member_str = "参加者"
    current_member_str = "空間の参加者"
    world_member_str = "世界の参加者"
    parties_str = "パーティー一覧"

    data = deepcopy(_DEFAULT)
    if not isinstance(raw, dict):
        return data

    data[player_id_str] = player_id
    data[player_name_str] = player_name

    current_state = raw.get(current_state_str)

    if isinstance(current_state, dict):
        time_val = _clean_string_or_none(current_state.get("time"))
        if not time_val:
            time_val = datetime.now().strftime("%Y年%m月%d日")

        data[current_state_str][date_str] = time_val
        # data["current_state"]["participants"] = _clean_string_list(current_state.get("participants"))

        data[current_state_str][member_str] = normalize_person_list(
            current_state.get(current_member_str)
        )
        data[current_state_str][parties_str] = normalize_parties(
            current_state.get(parties_str)
        )
    else:
        data[current_state_str][date_str] = datetime.now().strftime("%Y年%m月%d日")
        data[current_state_str][member_str] = []

    # # 新構造を優先し、旧構造 world_relation も互換で読む
    world = raw.get(world_state_str)

    data[world_state_str][member_str] = normalize_person_list(
        world.get(world_member_str)
    )
    
    return data

# 既存コード互換
normalize_summary_data = normalize_world_memory_data


def extract_list_items(text: str) -> list[str]:
    result = []

    for line in text.splitlines():
        line = line.strip()

        # "- "形式
        if line.startswith("- "):
            result.append(line[2:].strip())
            continue

        # "・"形式（日本語対策）
        if line.startswith("・"):
            result.append(line[1:].strip())
            continue

    return result

def none_if_blank(value):
    if value is None:
        return None

    if isinstance(value, str):
        value = value.replace("\r\n", "\n").strip()
        return value if value else None

    return value

def to_literal_if_multiline(value):
    value = string_utils.none_if_blank(value)

    if value is None:
        return None

    # 改行コード統一
    value = value.replace("\r\n", "\n")

    if "\n" in value:
        return LiteralString(value)

    return value

# 履歴に1件足し、振った line_id を返す。
# line_id は発言ごとの通し番号（1から）。履歴を読み出すAPIも「何件目か」で番号を振るので、それと一致する。
def history_append(history: list, speaker: str, role: str, message: str, icon_data: dict) -> str:
    line_id = str(len(history) + 1)
    history.append({
        "t": time.time(),
        "speaker": speaker,
        "role": role,
        "line_id": line_id,
        "message": message,
        "icon_data": icon_data
    })
    return line_id

def _join_sections(*parts: str) -> str:
    """空文字を除外しつつ、改行の崩れを抑えて連結する"""
    cleaned: list[str] = []
    for part in parts:
        if part is None:
            continue
        text = normalize_newlines(str(part)).strip()
        if text:
            cleaned.append(text)
    return "\n\n".join(cleaned)

def build_messages(prompt_data: dict, user_parts: list | tuple = ()) -> list[dict]:
    """プロンプトYAMLから、モデルへ送る system と user のメッセージを作る（全プロンプト共通の組み立て方）

    system ← YAMLの system
    user   ← header ＋ user_parts ＋ template ＋ tail_template（空のものは飛ばし、空行でつなぐ）

    差し込み口（{summary} など）は、呼ぶ側で埋めた prompt_data を渡す。
    """
    user_content = _join_sections(
        prompt_data.get("header", ""),
        *user_parts,
        prompt_data.get("template", ""),
        prompt_data.get("tail_template", ""),
    )

    return [
        {"role": "system", "content": prompt_data.get("system", "")},
        {"role": "user", "content": user_content},
    ]

def fill_template(prompt_data: dict, values: dict) -> dict:
    """prompt_data の写しを作り、template の差し込み口 {キー} を values で埋めて返す"""
    filled = dict(prompt_data)
    template = filled.get("template") or ""
    for key, value in values.items():
        template = template.replace("{" + key + "}", value or "")
    filled["template"] = template
    return filled
