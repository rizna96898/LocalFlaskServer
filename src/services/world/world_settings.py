import yaml

import re
import shutil
from helpers import response_checker
from pathlib import Path
from helpers import file_utils
from helpers import string_utils
from logger import log

# 一覧の種類ごとの、フォルダとファイル名の末尾
# {base_chat_path}/{フォルダ}/settings/{ID}{末尾}
LIST_SOURCES = {
    "world": ("worlds", "_world.yaml"),
    "character": ("characters", "_setting.yaml"),
    "player": ("players", "_setting.yaml"),
}

# タグの一覧。Web側フォルダの tags/tags.yaml に「タグ一覧: [名前, ...]」で持つ（画面の「タグ」で管理する）
TAGS_FILE = Path("tags") / "tags.yaml"
TAG_NAME_MAX = 30


class WorldSettings:
    def __init__(self):
        self.model_handling_service = None

    def save_world_setting(self, payload):

        base_chat_path = payload.get("base_chat_path", "").strip()
        world_id = payload.get("world_id", "").strip()
        world_name = payload.get("world_name", "").strip()
        purpose = payload.get("purpose", "").strip()
        supplement = payload.get("supplement", "").strip()
        include_str = payload.get("include_data", "")
        goal_str = payload.get("goal_data", "")
        parameter_str = payload.get("parameter_data", "")   
        
        if not base_chat_path:
            return response_checker.response_error("base_chat_pathが未指定です", 400)

        if not world_id:
            return response_checker.response_error("世界IDが未指定です", 400)

        if not re.fullmatch(r"[A-Za-z0-9_]+", world_id):
            return response_checker.response_error("世界IDは半角英数字と_のみ使用できます", 400)

        if not world_name:
            return response_checker.response_error("世界名が未指定です", 400)

        if not include_str.strip():
            return response_checker.response_error("登場人物が空です", 400)

        if not goal_str.strip():
            return response_checker.response_error("シナリオの目標が空です", 400)

        if not parameter_str.strip():
            return response_checker.response_error("シナリオパラメーターが空です", 400)


        try:
            include_data = yaml.safe_load(include_str)
            data_list = include_data["世界の登場人物"]

            # 参照IDは全員に必須（サブ・モブも、セッションのファイル名に使う）
            for no, c in enumerate(data_list, 1):
                if not isinstance(c, dict) or c.get("参照種別") in (None, "null"):
                    continue
                ref_id = str(c.get("参照ID") or "")
                if not re.fullmatch(r"[A-Za-z0-9_]+", ref_id):
                    return response_checker.response_error(f"登場人物の{no}件目: 参照IDは半角英数字と_で必ず入れてください", 400)

            # プレイヤーは必ず1人
            player_count = sum(1 for c in data_list if isinstance(c, dict) and c.get("参照種別") == "player")
            if player_count != 1:
                return response_checker.response_error(f"登場人物の player は1人だけにしてください（今は {player_count} 人）", 400)

            for index, character_data in enumerate(data_list):
                if character_data["表示名"] is None:
                    reference_file_path = ""
                    if character_data["参照種別"] == "player":
                        reference_file_path = Path(base_chat_path) / "players" / "settings" / f"{character_data['参照ID']}_setting.yaml"
                    elif character_data["参照種別"] is not None:
                        reference_file_path = Path(base_chat_path) / "characters" / "settings" / f"{character_data['参照ID']}_setting.yaml"
                    else:
                        continue

                    file_data = file_utils.load_yaml_file(reference_file_path)

                    if file_data is not None:
                        if file_data["名前"]["表示名"] is not None \
                        and file_data["名前"]["表示名"] != "":
                            #キャラカードから名称を参照
                            character_data["表示名"] = file_data["名前"]["表示名"]
                
                
        except yaml.YAMLError as e:
            return response_checker.response_error("YAML形式が正しくありません", 400, detail=str(e))
        try:
            goal_data = yaml.safe_load(goal_str)
        except yaml.YAMLError as e:
            return response_checker.response_error("YAML形式が正しくありません", 400, detail=str(e))
        try:
            parameter_data = yaml.safe_load(parameter_str)
        except yaml.YAMLError as e:
            return response_checker.response_error("YAML形式が正しくありません", 400, detail=str(e))
            
        save_dir = Path(base_chat_path) / "worlds" / "settings"
        save_dir.mkdir(parents=True, exist_ok=True)

        log.info("data", payload)
        world_form_data = {
            "世界名": world_name,
            "登場人物": include_data,
            "シナリオの目標": goal_data,
            "シナリオ本文": {
                "過去": string_utils.to_literal_if_multiline(payload.get("past", "")),
                "現在": string_utils.to_literal_if_multiline(payload.get("current", "")),
                "未来": string_utils.to_literal_if_multiline(payload.get("future", "")),
            },
            "シナリオパラメータ": parameter_data,
            "目的": purpose,
            "補足": supplement,
            "開始メッセージ": string_utils.to_literal_if_multiline(payload.get("start_message", "")),
        }

        save_path = self.save_world_yaml(world_id, world_form_data, save_dir)

        return response_checker.response_ok(message="世界設定を保存しました", path=str(save_path))

    def load_world_settings(self, payload):

        base_chat_path = payload.get("base_chat_path", "").strip()
        world_id = payload.get("world_id", "").strip()

        world_setting_file = Path(base_chat_path) / f"worlds/settings/{world_id}_world.yaml"

        if not world_setting_file.is_file():
            return response_checker.response_error(f"世界設定がありません: {world_id}", 404)

        world_setting_data = file_utils.load_yaml_file(world_setting_file)
        
        world_id = world_setting_data.get("世界ID")
        world_name = world_setting_data.get("世界名")
        characters = world_setting_data.get("登場人物")
        goal_target = world_setting_data.get("シナリオの目標")
        past = world_setting_data.get("シナリオ本文").get("過去")
        now = world_setting_data.get("シナリオ本文").get("現在")
        future = world_setting_data.get("シナリオ本文").get("未来")
        purpose = world_setting_data.get("目的")
        supplement = world_setting_data.get("補足")
        scenario_parameter = world_setting_data.get("シナリオパラメータ")
        start_message = world_setting_data.get("開始メッセージ")

        characters = yaml.safe_dump(
            characters,
            allow_unicode=True,
            sort_keys=False
        )
        goal_target = yaml.safe_dump(
            goal_target,
            allow_unicode=True,
            sort_keys=False
        )
        scenario_parameter = yaml.safe_dump(
            scenario_parameter,
            allow_unicode=True,
            sort_keys=False
        )

        # 項目名は、保存(/settings/save_world_setting)で受け取る名前と揃えている
        return response_checker.response_ok(
            message="",
            world_id=world_id,
            world_name=world_name,
            include_data=characters,
            goal_data=goal_target,
            past=past,
            current=now,
            future=future,
            purpose=purpose,
            supplement=supplement,
            parameter_data=scenario_parameter,
            start_message=start_message,
        )

    def save_player_setting(self, payload):

        base_chat_path = payload.get("base_chat_path", "").strip()
        player_id = payload.get("player_id", "").strip()
        player_name = payload.get("player_name", "").strip()
        content = payload.get("content", "")

        log.info("base_chat_path", base_chat_path)
        log.info("player_id", player_id)
        log.info("player_name", player_name)
        log.info("content", content)
        
        if not base_chat_path:
            return response_checker.response_error("base_chat_pathが未指定です", 400)

        if not player_id:
            return response_checker.response_error("プレイヤーIDが未指定です", 400)

        if not re.fullmatch(r"[A-Za-z0-9_]+", player_id):
            return response_checker.response_error("プレイヤーIDは半角英数字と_のみ使用できます", 400)

        if not player_name:
            return response_checker.response_error("プレイヤー名が未指定です", 400)

        if not content.strip():
            return response_checker.response_error("プレイヤー設定が空です", 400)

        try:
            yaml_data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return response_checker.response_error("YAML形式が正しくありません", 400, detail=str(e))

        if yaml_data is None:
            yaml_data = {}

        if not isinstance(yaml_data, dict):
            return response_checker.response_error("プレイヤー設定YAMLの最上位はオブジェクト形式にしてください", 400)

        # 名前欄を画面入力で上書き
        name_block = yaml_data.get("名前")
        if not isinstance(name_block, dict):
            name_block = {}

        name_block["表示名"] = player_name
        name_block["識別子"] = player_id

        # ふりがなが無ければ null 扱い
        if "ふりがな" not in name_block:
            name_block["ふりがな"] = None

        yaml_data["名前"] = name_block

        save_dir = Path(base_chat_path) / "players" / "settings"
        save_dir.mkdir(parents=True, exist_ok=True)

        save_path = save_dir / f"{player_id}_setting.yaml"

        try:
            with open(save_path, "w", encoding="utf-8", newline="\n") as f:
                yaml.safe_dump(
                    yaml_data,
                    f,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False
                )
        except Exception as e:
            return response_checker.response_error("プレイヤー設定の保存に失敗しました", 500, detail=str(e))

        return response_checker.response_ok(message="プレイヤー設定を保存しました", path=str(save_path))

    def save_character_setting(self, payload):

        base_chat_path = payload.get("base_chat_path", "").strip()
        character_id = payload.get("character_id", "").strip()
        character_name = payload.get("character_name", "").strip()
        content = payload.get("content", "")

        if not base_chat_path:
            return response_checker.response_error("base_chat_pathが未指定です", 400)

        if not character_id:
            return response_checker.response_error("キャラクターIDが未指定です", 400)

        if not re.fullmatch(r"[A-Za-z0-9_]+", character_id):
            return response_checker.response_error("キャラクターIDは半角英数字と_のみ使用できます", 400)

        if not character_name:
            return response_checker.response_error("キャラクター名が未指定です", 400)

        if not content.strip():
            return response_checker.response_error("キャラクター設定が空です", 400)

        try:
            yaml_data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return response_checker.response_error("YAML形式が正しくありません", 400, detail=str(e))

        if yaml_data is None:
            yaml_data = {}

        if not isinstance(yaml_data, dict):
            return response_checker.response_error("キャラクター設定YAMLの最上位はオブジェクト形式にしてください", 400)

        # 名前欄を画面入力で上書き
        name_block = yaml_data.get("名前")
        if not isinstance(name_block, dict):
            name_block = {}

        name_block["表示名"] = character_name
        name_block["識別子"] = character_id

        # ふりがなが無ければ null 扱い
        if "ふりがな" not in name_block:
            name_block["ふりがな"] = None

        yaml_data["名前"] = name_block

        save_dir = Path(base_chat_path) / "characters" / "settings"
        save_dir.mkdir(parents=True, exist_ok=True)

        save_path = save_dir / f"{character_id}_setting.yaml"

        try:
            with open(save_path, "w", encoding="utf-8", newline="\n") as f:
                yaml.safe_dump(
                    yaml_data,
                    f,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False
                )
        except Exception as e:
            return response_checker.response_error("キャラクター設定の保存に失敗しました", 500, detail=str(e))

        return response_checker.response_ok(message="キャラクター設定を保存しました", path=str(save_path))

    # 世界・キャラクター・プレイヤーの一覧を、フォルダのYAMLから作って返す
    # kind: world / character / player
    def list_settings(self, payload):
        payload = payload or {}
        base_chat_path = (payload.get("base_chat_path") or "").strip()
        kind = (payload.get("kind") or "").strip()

        if not base_chat_path:
            return response_checker.response_error("base_chat_pathが未指定です", 400)

        if kind not in LIST_SOURCES:
            return response_checker.response_error(f"kind は {' / '.join(LIST_SOURCES)} のどれかにしてください", 400)

        if not Path(base_chat_path).is_dir():
            return response_checker.response_error(f"base_chat_pathのフォルダがありません: {base_chat_path}", 404)

        folder, suffix = LIST_SOURCES[kind]
        settings_dir = Path(base_chat_path) / folder / "settings"

        items = []
        if settings_dir.is_dir():
            for path in sorted(settings_dir.glob(f"*{suffix}")):
                item_id = path.name[:-len(suffix)]

                # ID に使えない文字のファイルは、画面から開けないので一覧に出さない
                if not re.fullmatch(r"[A-Za-z0-9_]+", item_id):
                    continue

                data = file_utils.load_yaml_file(path)
                if kind == "world":
                    name = data.get("世界名")
                else:
                    name_block = data.get("名前")
                    name = name_block.get("表示名") if isinstance(name_block, dict) else None

                items.append({"id": item_id, "name": name or item_id})

        return response_checker.response_ok(message="", kind=kind, items=items)

    # 世界・キャラクター・プレイヤーを削除する（設定YAMLと、キャラクター・プレイヤーは画像のフォルダも）
    # kind: world / character / player
    # - 世界を消しても、その世界のセッションは残す（セッション側に世界のコピーがある）
    # - キャラクター・プレイヤーは、登場人物にしている世界があれば消さない（409）
    # タグの一覧を返す。ファイルがまだ無ければ空
    def load_tags(self, payload):
        base_chat_path = ((payload or {}).get("base_chat_path") or "").strip()
        if not base_chat_path:
            return response_checker.response_error("base_chat_pathが未指定です", 400)
        if not Path(base_chat_path).is_dir():
            return response_checker.response_error(f"base_chat_pathのフォルダがありません: {base_chat_path}", 404)

        data = file_utils.load_yaml_file(Path(base_chat_path) / TAGS_FILE) or {}
        tags = [str(tag) for tag in (data.get("タグ一覧") or []) if tag not in (None, "")]
        return response_checker.response_ok(message="", tags=tags)

    # タグの一覧を、送られた並びで丸ごと保存する（登録・名前の変更・削除は、画面が一覧を直して送る）。
    # 空の名前、長すぎる名前、同じ名前の重複は断る
    def save_tags(self, payload):
        payload = payload or {}
        base_chat_path = (payload.get("base_chat_path") or "").strip()
        tags = payload.get("tags")

        if not base_chat_path:
            return response_checker.response_error("base_chat_pathが未指定です", 400)
        if not Path(base_chat_path).is_dir():
            return response_checker.response_error(f"base_chat_pathのフォルダがありません: {base_chat_path}", 404)
        if not isinstance(tags, list):
            return response_checker.response_error("tags は、タグ名の配列にしてください", 400)

        names = [str(tag).strip() if tag is not None else "" for tag in tags]
        if any(not name for name in names):
            return response_checker.response_error("タグ名が空です", 400)
        too_long = [name for name in names if len(name) > TAG_NAME_MAX]
        if too_long:
            return response_checker.response_error(f"タグ名は{TAG_NAME_MAX}文字までです: {too_long[0]}", 400)
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            return response_checker.response_error(f"同じ名前のタグがあります: {'、'.join(duplicated)}", 400)

        if not file_utils.save_yaml_file(Path(base_chat_path) / TAGS_FILE, {"タグ一覧": names}):
            return response_checker.response_error("タグの保存に失敗しました", 500)
        return response_checker.response_ok(message="タグを保存しました", tags=names)

    def delete_setting(self, payload):
        payload = payload or {}
        base_chat_path = (payload.get("base_chat_path") or "").strip()
        kind = (payload.get("kind") or "").strip()
        item_id = (payload.get("id") or "").strip()

        if not base_chat_path:
            return response_checker.response_error("base_chat_pathが未指定です", 400)

        if kind not in LIST_SOURCES:
            return response_checker.response_error(f"kind は {' / '.join(LIST_SOURCES)} のどれかにしてください", 400)

        if not re.fullmatch(r"[A-Za-z0-9_]+", item_id):
            return response_checker.response_error("IDは半角英数字と_で指定してください", 400)

        folder, suffix = LIST_SOURCES[kind]
        setting_file = Path(base_chat_path) / folder / "settings" / f"{item_id}{suffix}"

        if not setting_file.is_file():
            return response_checker.response_error(f"設定がありません: {item_id}", 404)

        if kind != "world":
            used_in = self._worlds_using(base_chat_path, kind, item_id)
            if used_in:
                names = "、".join(w["name"] for w in used_in)
                return response_checker.response_error(f"これらの世界で使われているので削除できません: {names}", 409, worlds=used_in)

        try:
            setting_file.unlink()

            # キャラクター・プレイヤーは、アイコンと立ち絵のフォルダも消す
            if kind != "world":
                for image_type in ("icon", "standing"):
                    image_dir = Path(base_chat_path) / folder / image_type / item_id
                    if image_dir.is_dir():
                        shutil.rmtree(image_dir)
        except Exception as e:
            log.info(f"[ERROR] 削除に失敗しました {setting_file}: {e}")
            return response_checker.response_error(f"削除に失敗しました: {e}", 500)

        return response_checker.response_ok(message="削除しました", kind=kind, id=item_id)

    # 指定したキャラクター・プレイヤーを登場人物にしている世界の一覧 [{id, name}]
    def _worlds_using(self, base_chat_path: str, kind: str, item_id: str) -> list:
        folder, suffix = LIST_SOURCES["world"]
        worlds_dir = Path(base_chat_path) / folder / "settings"
        used_in = []

        if not worlds_dir.is_dir():
            return used_in

        for path in sorted(worlds_dir.glob(f"*{suffix}")):
            data = file_utils.load_yaml_file(path)
            participants = (data.get("登場人物") or {}).get("世界の登場人物") or []
            if any(isinstance(p, dict) and p.get("参照種別") == kind and str(p.get("参照ID")) == item_id
                   for p in participants):
                world_id = path.name[:-len(suffix)]
                used_in.append({"id": world_id, "name": data.get("世界名") or world_id})

        return used_in

    # プレイヤー設定を読み込んで返却（キャラクター設定の読み込みと同じ形）
    def load_player_settings(self, payload):
        payload = payload or {}
        base_chat_path = (payload.get("base_chat_path") or "").strip()
        player_id = (payload.get("player_id") or "").strip()

        if not base_chat_path:
            return response_checker.response_error("base_chat_pathが未指定です", 400)

        if not re.fullmatch(r"[A-Za-z0-9_]+", player_id):
            return response_checker.response_error("プレイヤーIDは半角英数字と_で指定してください", 400)

        player_setting_file = Path(base_chat_path) / f"players/settings/{player_id}_setting.yaml"

        if not player_setting_file.is_file():
            return response_checker.response_error(f"プレイヤー設定がありません: {player_id}", 404)

        player_setting_data = file_utils.load_yaml_file(player_setting_file)
        result = yaml.safe_dump(
            player_setting_data,
            allow_unicode=True,
            sort_keys=False
        )

        name_block = player_setting_data.get("名前")
        if not isinstance(name_block, dict):
            name_block = {}

        return response_checker.response_ok(
            message="",
            player_id=name_block.get("識別子") or player_id,
            player_name=name_block.get("表示名") or player_id,
            player_info=result,
        )

    def load_character_settings(self, payload):

        base_chat_path = payload.get("base_chat_path", "").strip()
        character_id = payload.get("character_id", "").strip()

        character_setting_file = Path(base_chat_path) / f"characters/settings/{character_id}_setting.yaml"

        if not character_setting_file.is_file():
            return response_checker.response_error(f"キャラクター設定がありません: {character_id}", 404)

        character_setting_data = file_utils.load_yaml_file(character_setting_file)
        result = yaml.safe_dump(
            character_setting_data,
            allow_unicode=True,
            sort_keys=False
        )
        
        character_id = character_setting_data.get("名前").get("識別子")
        character_name = character_setting_data.get("名前").get("表示名")

        return response_checker.response_ok(
            message="",
            character_id=character_id,
            character_name=character_name,
            character_info=result,
        )

    # 世界設定を保存
    def save_world_yaml(self, world_id: str, form_data: dict, save_dir: Path):

        world_id = string_utils.none_if_blank(world_id)
        if world_id is None:
            raise ValueError("世界IDが空です")

        save_dir.mkdir(parents=True, exist_ok=True)

        save_path = save_dir / f"{world_id}_world.yaml"

        scenario_body = form_data.get("シナリオ本文")
        if not isinstance(scenario_body, dict):
            scenario_body = {}

        scenario_body = {
            k: v
            for k, v in scenario_body.items()
            if v is not None
        }

        data = {
            "世界ID": world_id,
            "世界名": form_data.get("世界名"),
            "登場人物": form_data.get("登場人物"),
            "シナリオの目標": form_data.get("シナリオの目標"),
            "シナリオ本文": scenario_body,
            "シナリオパラメータ": form_data.get("シナリオパラメータ"),
            "目的": form_data.get("目的"),
            "補足": form_data.get("補足"),
            "開始メッセージ": form_data.get("開始メッセージ"),
        }

        with save_path.open("w", encoding="utf-8", newline="\n") as f:
            yaml.safe_dump(
                data,
                f,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
                width=1000,
            )

        return save_path