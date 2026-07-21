import yaml

import re
from flask import jsonify
from pathlib import Path
from helpers import file_utils
from helpers import string_utils

class ChatSettings:
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
            return jsonify({"ok": False, "message": "base_chat_pathが未指定です"}), 400

        if not world_id:
            return jsonify({"ok": False, "message": "世界IDが未指定です"}), 400

        if not re.fullmatch(r"[A-Za-z0-9_]+", world_id):
            return jsonify({"ok": False, "message": "世界IDは半角英数字と_のみ使用できます"}), 400

        if not world_name:
            return jsonify({"ok": False, "message": "世界名が未指定です"}), 400

        if not include_str.strip():
            return jsonify({"ok": False, "message": "登場人物が空です"}), 400

        if not goal_str.strip():
            return jsonify({"ok": False, "message": "シナリオの目標が空です"}), 400

        if not parameter_str.strip():
            return jsonify({"ok": False, "message": "シナリオパラメーターが空です"}), 400


        try:
            include_data = yaml.safe_load(include_str)
            data_list = include_data["世界の登場人物"]
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
            return jsonify({
                "ok": False,
                "message": "YAML形式が正しくありません",
                "detail": str(e)
            }), 400
        try:
            goal_data = yaml.safe_load(goal_str)
        except yaml.YAMLError as e:
            return jsonify({
                "ok": False,
                "message": "YAML形式が正しくありません",
                "detail": str(e)
            }), 400
        try:
            parameter_data = yaml.safe_load(parameter_str)
        except yaml.YAMLError as e:
            return jsonify({
                "ok": False,
                "message": "YAML形式が正しくありません",
                "detail": str(e)
            }), 400
            
        save_dir = Path(base_chat_path) / "worlds" / "settings"
        save_dir.mkdir(parents=True, exist_ok=True)

        print("data", payload)
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

        save_path = file_utils.save_world_yaml(world_id, world_form_data, save_dir)

        return jsonify({
            "ok": True,
            "message": "世界設定を保存しました",
            "path": str(save_path)
        })

    def load_world_settings(self, payload):

        base_chat_path = payload.get("base_chat_path", "").strip()
        world_id = payload.get("world_id", "").strip()

        world_setting_file = Path(base_chat_path) / f"worlds/settings/{world_id}_world.yaml"

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

        return jsonify({
            "ok": True,
            "message": "",
            "world_id": world_id,
            "world_name": world_name,
            "characters": characters,
            "goal_target": goal_target,
            "past": past,
            "now": now,
            "future": future,
            "purpose": purpose,
            "supplement": supplement,
            "scenario_parameter": scenario_parameter,
            "start_message": start_message,

        }), 200

    def save_player_setting(self, payload):

        base_chat_path = payload.get("base_chat_path", "").strip()
        player_id = payload.get("player_id", "").strip()
        player_name = payload.get("player_name", "").strip()
        content = payload.get("content", "")

        print("base_chat_path", base_chat_path)
        print("player_id", player_id)
        print("player_name", player_name)
        print("content", content)
        
        if not base_chat_path:
            return jsonify({"ok": False, "message": "base_chat_pathが未指定です"}), 400

        if not player_id:
            return jsonify({"ok": False, "message": "プレイヤーIDが未指定です"}), 400

        if not re.fullmatch(r"[A-Za-z0-9_]+", player_id):
            return jsonify({"ok": False, "message": "プレイヤーIDは半角英数字と_のみ使用できます"}), 400

        if not player_name:
            return jsonify({"ok": False, "message": "プレイヤー名が未指定です"}), 400

        if not content.strip():
            return jsonify({"ok": False, "message": "プレイヤー設定が空です"}), 400

        try:
            yaml_data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return jsonify({
                "ok": False,
                "message": "YAML形式が正しくありません",
                "detail": str(e)
            }), 400

        if yaml_data is None:
            yaml_data = {}

        if not isinstance(yaml_data, dict):
            return jsonify({
                "ok": False,
                "message": "プレイヤー設定YAMLの最上位はオブジェクト形式にしてください"
            }), 400

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
            return jsonify({
                "ok": False,
                "message": "プレイヤー設定の保存に失敗しました",
                "detail": str(e)
            }), 500

        return jsonify({
            "ok": True,
            "message": "プレイヤー設定を保存しました",
            "path": str(save_path)
        })

    def save_character_setting(self, payload):

        base_chat_path = payload.get("base_chat_path", "").strip()
        character_id = payload.get("character_id", "").strip()
        character_name = payload.get("character_name", "").strip()
        content = payload.get("content", "")

        if not base_chat_path:
            return jsonify({"ok": False, "message": "base_chat_pathが未指定です"}), 400

        if not character_id:
            return jsonify({"ok": False, "message": "キャラクターIDが未指定です"}), 400

        if not re.fullmatch(r"[A-Za-z0-9_]+", character_id):
            return jsonify({"ok": False, "message": "キャラクターIDは半角英数字と_のみ使用できます"}), 400

        if not character_name:
            return jsonify({"ok": False, "message": "キャラクター名が未指定です"}), 400

        if not content.strip():
            return jsonify({"ok": False, "message": "キャラクター設定が空です"}), 400

        try:
            yaml_data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return jsonify({
                "ok": False,
                "message": "YAML形式が正しくありません",
                "detail": str(e)
            }), 400

        if yaml_data is None:
            yaml_data = {}

        if not isinstance(yaml_data, dict):
            return jsonify({
                "ok": False,
                "message": "キャラクター設定YAMLの最上位はオブジェクト形式にしてください"
            }), 400

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
            return jsonify({
                "ok": False,
                "message": "キャラクター設定の保存に失敗しました",
                "detail": str(e)
            }), 500

        return jsonify({
            "ok": True,
            "message": "キャラクター設定を保存しました",
            "path": str(save_path)
        })

    def load_character_settings(self, payload):

        base_chat_path = payload.get("base_chat_path", "").strip()
        character_id = payload.get("character_id", "").strip()

        character_setting_file = Path(base_chat_path) / f"characters/settings/{character_id}_setting.yaml"

        character_setting_data = file_utils.load_yaml_file(character_setting_file)
        result = yaml.safe_dump(
            character_setting_data,
            allow_unicode=True,
            sort_keys=False
        )
        
        character_id = character_setting_data.get("名前").get("識別子")
        character_name = character_setting_data.get("名前").get("表示名")

        return jsonify({
            "ok": True,
            "message": "",
            "character_id": character_id,
            "character_name": character_name,
            "character_info": result,
        }), 200

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