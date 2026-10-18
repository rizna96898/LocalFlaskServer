"""セッションの登場人物を読む。

登場人物は、セッションに写した世界設定（files/sessions/{session_id}/{world_id}_world.yaml）の
「登場人物 → 世界の登場人物」から取る。発言者のIDと名前は、ここで決めたものを使う（固定の名前を書かない）。
"""
from typing import Any, Dict, List

from config import config
from helpers import file_utils


def load_session_world(session_id: str) -> Dict[str, Any]:
    """セッションに写した世界設定を返す。見つからなければ空の dict。"""
    sessions_data = file_utils.load_yaml_file(config.SYSTEM_DIR / "sessions_list.yaml") or {}
    sessions = sessions_data.get("sessions") or []

    world_id = next(
        (s.get("world_id") for s in sessions if isinstance(s, dict) and s.get("session_id") == session_id),
        None,
    )
    if not world_id:
        return {}

    return file_utils.load_yaml_file(config.SESSIONS_DIR / session_id / f"{world_id}_world.yaml") or {}


def _display_name(session_id: str, person: Dict[str, Any], person_id: str) -> str:
    """表示名。世界設定に無ければ、セッションに写した設定YAMLの 名前 → 表示名、それも無ければID。"""
    name = person.get("表示名")
    if name and name != "null":
        return str(name)

    setting = file_utils.load_yaml_file(config.SESSIONS_DIR / session_id / "character" / f"{person_id}_setting.yaml") or {}
    name_block = setting.get("名前")
    if isinstance(name_block, dict) and name_block.get("表示名"):
        return str(name_block["表示名"])

    return person_id


def load_cast(session_id: str) -> Dict[str, Any]:
    """セッションの登場人物を返す。

    {
        "player": {"id": ..., "name": ..., "kind": "player", "role": ...},
        "characters": [{"id": ..., "name": ..., "kind": "character" | "inline", "role": "main" | "sub" | "mob"}, ...],
    }
    参照種別が null の人物は入れない。プレイヤーが見つからなければ id: player / name: プレイヤー にする。
    """
    world = load_session_world(session_id)
    people = (world.get("登場人物") or {}).get("世界の登場人物") or []

    player = None
    characters: List[Dict[str, Any]] = []

    for person in people:
        if not isinstance(person, dict):
            continue

        kind = person.get("参照種別")
        person_id = person.get("参照ID")
        if kind in (None, "null") or not person_id or person_id == "null":
            continue

        person_id = str(person_id)
        job = person.get("職業")
        entry = {
            "id": person_id,
            "name": _display_name(session_id, person, person_id),
            "kind": kind,
            "role": person.get("役割"),
            "job": "" if job in (None, "null") else str(job),
        }

        if kind == "player":
            if player is None:
                player = entry
        else:
            characters.append(entry)

    if player is None:
        player = {"id": "player", "name": "プレイヤー", "kind": "player", "role": "player"}

    return {"player": player, "characters": characters}


def first_main(cast: Dict[str, Any]) -> Dict[str, Any]:
    """最初のメインキャラクター（参照種別が character の最初の人）。いなければ、プレイヤー以外の最初の人。"""
    characters = cast.get("characters") or []
    mains = [c for c in characters if c.get("kind") == "character"]
    if mains:
        return mains[0]
    if characters:
        return characters[0]
    return {"id": "system", "name": "システム", "kind": "system", "role": None}


def label(person: Dict[str, Any]) -> str:
    """プロンプトの候補に並べる書き方。「ID（表示名・職業）」。職業が無ければ「ID（表示名）」。

    職業（世界設定の登場人物の 職業。例: カッコウ医院の先生）を付けるのは、会話の「先生」と人物を結び付けられるようにするため。
    """
    detail = person["name"] + (f"・{person['job']}" if person.get("job") else "")
    return f"{person['id']}（{detail}）"


def icon_data(person: Dict[str, Any]) -> Dict[str, str]:
    """履歴と画面に渡す発言者の情報"""
    return {"character_id": person["id"], "character_name": person["name"]}
