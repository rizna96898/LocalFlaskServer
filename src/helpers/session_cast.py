"""セッションの登場人物を読む。

登場人物は、セッションに写した世界設定（files/sessions/{session_id}/{world_id}_world.yaml）の
「登場人物 → 世界の登場人物」から取る。発言者のIDと名前は、ここで決めたものを使う（固定の名前を書かない）。
"""
from typing import Any, Dict, List

from config import config
from helpers import file_utils


def _session_world_path(session_id: str):
    """セッションに写した世界設定のファイルの場所。見つからなければ None。"""
    sessions_data = file_utils.load_yaml_file(config.SYSTEM_DIR / "sessions_list.yaml") or {}
    sessions = sessions_data.get("sessions") or []

    world_id = next(
        (s.get("world_id") for s in sessions if isinstance(s, dict) and s.get("session_id") == session_id),
        None,
    )
    if not world_id:
        return None
    return config.SESSIONS_DIR / session_id / f"{world_id}_world.yaml"


def load_session_world(session_id: str) -> Dict[str, Any]:
    """セッションに写した世界設定を返す。見つからなければ空の dict。"""
    path = _session_world_path(session_id)
    if path is None:
        return {}
    return file_utils.load_yaml_file(path) or {}


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


# ---------------------------------------------------------------- その場の参加者
# 世界の記憶（world_memory.yaml）の「現在の状態 → 参加者」が、今その場にいる人。発言のあとに毎回更新する。
# 返事をする人の判定・意識の確認・掛け合いの相手・記憶の更新は、その場にいる人だけで行う（プレイヤーは常にいる扱い）。

def load_world_memory(session_id: str) -> Dict[str, Any]:
    return file_utils.load_yaml_file(config.SESSIONS_DIR / session_id / "world_memory.yaml") or {}


def present_ids(session_id: str):
    """その場にいる人のIDの集まり。世界の記憶がまだ無い・参加者が書かれていないときは None（全員いる扱い）"""
    current = (load_world_memory(session_id).get("現在の状態") or {})
    people = current.get("参加者")
    if not isinstance(people, list):
        return None
    return {str(p.get("キャラクターID")) for p in people if isinstance(p, dict) and p.get("キャラクターID")}


def present_cast(session_id: str) -> Dict[str, Any]:
    """load_cast のうち、その場にいる人だけにしたもの。誰もいなければ、全員を返す（返事をする人がいなくならないように）"""
    cast = load_cast(session_id)
    ids = present_ids(session_id)
    if ids is None:
        return cast

    present = [c for c in cast["characters"] if c["id"] in ids]
    if not present:
        return cast
    return {"player": cast["player"], "characters": present}


def add_guest(session_id: str, name: str, role: str) -> Dict[str, Any]:
    """会話で新しく現れた人（世界設定にいない人）を、セッションの登場人物に足す。

    - ID は guest_1、guest_2… と振る。役割は sub、職業にはその人の立場（プレイヤーの友人 など）を入れる
    - セッションに写した世界設定と、character/{ID}_setting.yaml（名前と立場だけの小さな設定）を書く
    - Web側の世界設定（元のファイル）は変えない
    """
    path = _session_world_path(session_id)
    world = (file_utils.load_yaml_file(path) or {}) if path else {}
    people = (world.setdefault("登場人物", {}) or {}).setdefault("世界の登場人物", []) if path else []

    used = {str(p.get("参照ID")) for p in people if isinstance(p, dict)}
    no = 1
    while f"guest_{no}" in used:
        no += 1
    guest_id = f"guest_{no}"

    entry = {"参照種別": "inline", "参照ID": guest_id, "表示名": name, "役割": "sub", "職業": role or None}
    if path:
        people.append(entry)
        file_utils.save_yaml_file(path, world)

    setting = {"名前": {"表示名": name, "ふりがな": None, "識別子": guest_id}, "基本情報": {"職業": role or None}}
    file_utils.save_yaml_file(config.SESSIONS_DIR / session_id / "character" / f"{guest_id}_setting.yaml", setting)

    return {"id": guest_id, "name": name, "kind": "inline", "role": "sub", "job": role or ""}


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
