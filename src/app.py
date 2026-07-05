# src/app.py
"""
Flaskサーバーのエントリーポイント
ルーティングと簡単なエラーハンドリングのみを担当
"""
# src/app.py の一番上（他のimportより前に追加）
import sys
import os
from pathlib import Path
from services import local_llama_service
from shutil import copy2
from helpers import file_utils
import shutil

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# 以下を追加
sys.path.insert(0, str(ROOT_DIR / "src"))

# print(f"[DEBUG] Root: {ROOT_DIR}")

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
# importを以下に変更
from config import config                    # src/config.py
from core.orchestrator import ChatOrchestrator
from services import system_settings_reload_service
import yaml
import re
from datetime import datetime
from uuid import uuid4

app = Flask(__name__)

# これを一番上に書く
CORS(app)

# Orchestratorの初期化
orchestrator = ChatOrchestrator()

class LiteralString(str):
    pass

def literal_str_representer(dumper, data):
    return dumper.represent_scalar(
        "tag:yaml.org,2002:str",
        data,
        style="|"
    )

yaml.SafeDumper.add_representer(
    LiteralString,
    literal_str_representer
)

def _json_ok(**kwargs):
    return jsonify({"ok": True, **kwargs})

def _json_error(message: str, status: int = 400, **kwargs):
    return jsonify({"ok": False, "message": message, **kwargs}), status

@app.get("/health")
def health():
    return _json_ok(status="ok")

@app.post("/settings/select_base_path")
def select_base_path():
    # 注意:
    # Flaskを起動しているPC側にフォルダ選択ダイアログが出ます。
    try:
        import tkinter as tk
        from tkinter import filedialog

        payload = request.get_json(silent=True) or {}
        current_path = payload.get("current_path") or ""

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        selected = filedialog.askdirectory(
            title="LOCAL_FLASK_SERVER のフォルダを選択",
            initialdir=current_path if current_path and Path(current_path).exists() else None,
        )

        root.destroy()
        return _json_ok(base_path=selected or "")
    except Exception as exc:
        return _json_error(f"フォルダ選択に失敗しました: {exc}", status=500)

@app.post("/settings/open_system_yaml")
def open_system_yaml():
    payload = request.get_json(silent=True) or {}
    base_path = payload.get("base_path") or ""

    if not base_path:
        return _json_error("ベースパスが未設定です。", status=400)

    full_path = Path(base_path) / "files" / "settings" / "system_settings.yaml"

    if not full_path.exists() or not full_path.is_file():
        return _json_error("ファイル読み込み失敗", status=404, full_path=str(full_path))

    try:
        os.startfile(str(full_path))  # Windows専用。関連付けされたエディタで開きます。
        return _json_ok(full_path=str(full_path))
    except Exception as exc:
        return _json_error(f"ファイル読み込み失敗: {exc}", status=500, full_path=str(full_path))

@app.post("/settings/get_template_world_include_player_yaml")
def get_template_world_include_player_yaml():
    base_chat_path = request.json.get("base_chat_path", "")
    if not base_chat_path:
        return jsonify({"ok": False, "message": "base_chat_pathが未指定です"}), 400

    file_path = os.path.join(
        base_chat_path,
        "worlds",
        "template",
        "include_player_template.yaml"
    )

    if not os.path.exists(file_path):
        return jsonify({"ok": False, "message": f"ファイルが存在しません: {file_path}"}), 404

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

    return jsonify({
        "ok": True,
        "content": content
    })

@app.post("/settings/get_template_world_goal_setting_yaml")
def get_template_world_goal_setting_yaml():
    base_chat_path = request.json.get("base_chat_path", "")
    if not base_chat_path:
        return jsonify({"ok": False, "message": "base_chat_pathが未指定です"}), 400

    file_path = os.path.join(
        base_chat_path,
        "worlds",
        "template",
        "scenario_goal_setting_template.yaml"
    )

    if not os.path.exists(file_path):
        return jsonify({"ok": False, "message": f"ファイルが存在しません: {file_path}"}), 404

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

    return jsonify({
        "ok": True,
        "content": content
    })

@app.post("/settings/get_template_world_parameter_setting_yaml")
def get_template_world_parameter_setting_yaml():
    base_chat_path = request.json.get("base_chat_path", "")
    if not base_chat_path:
        return jsonify({"ok": False, "message": "base_chat_pathが未指定です"}), 400

    file_path = os.path.join(
        base_chat_path,
        "worlds",
        "template",
        "scenario_parameter_setting_template.yaml"
    )

    if not os.path.exists(file_path):
        return jsonify({"ok": False, "message": f"ファイルが存在しません: {file_path}"}), 404

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

    return jsonify({
        "ok": True,
        "content": content
    })

@app.post("/settings/get_template_player_yaml")
def get_template_player_yaml():
    base_chat_path = request.json.get("base_chat_path", "")
    if not base_chat_path:
        return jsonify({"ok": False, "message": "base_chat_pathが未指定です"}), 400

    file_path = os.path.join(
        base_chat_path,
        "players",
        "template",
        "player_setting_template.yaml"
    )

    if not os.path.exists(file_path):
        return jsonify({"ok": False, "message": f"ファイルが存在しません: {file_path}"}), 404

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

    return jsonify({
        "ok": True,
        "content": content
    })

@app.post("/settings/get_template_character_yaml")
def get_template_character_yaml():
    base_chat_path = request.json.get("base_chat_path", "")
    if not base_chat_path:
        return jsonify({"ok": False, "message": "base_chat_pathが未指定です"}), 400

    file_path = os.path.join(
        base_chat_path,
        "characters",
        "template",
        "character_setting_template.yaml"
    )

    if not os.path.exists(file_path):
        return jsonify({"ok": False, "message": f"ファイルが存在しません: {file_path}"}), 404

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

    return jsonify({
        "ok": True,
        "content": content
    })

@app.post("/settings/save_world_setting")
def save_world_setting():
    data = request.get_json(silent=True) or {}

    base_chat_path = data.get("base_chat_path", "").strip()
    world_id = data.get("world_id", "").strip()
    world_name = data.get("world_name", "").strip()
    purpose = data.get("purpose", "").strip()
    supplement = data.get("supplement", "").strip()
    include_str = data.get("include_data", "")
    goal_str = data.get("goal_data", "")
    parameter_str = data.get("parameter_data", "")   
    
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

    print("data", data)
    world_form_data = {
        "世界名": world_name,
        "登場人物": include_data,
        "シナリオの目標": goal_data,
        "シナリオ本文": {
            "過去": to_literal_if_multiline(data.get("past", "")),
            "現在": to_literal_if_multiline(data.get("current", "")),
            "未来": to_literal_if_multiline(data.get("future", "")),
        },
        "シナリオパラメータ": parameter_data,
        "目的": purpose,
        "補足": supplement,
        "開始メッセージ": to_literal_if_multiline(data.get("start_message", "")),
    }

    save_path = save_world_yaml(world_id, world_form_data, save_dir)

    return jsonify({
        "ok": True,
        "message": "世界設定を保存しました",
        "path": str(save_path)
    })

@app.post("/settings/load_world_settings")
def load_world_settings():
    data = request.get_json(silent=True) or {}

    base_chat_path = data.get("base_chat_path", "").strip()
    world_id = data.get("world_id", "").strip()

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

@app.post("/settings/save_player_setting")
def save_player_setting():
    data = request.get_json(silent=True) or {}

    base_chat_path = data.get("base_chat_path", "").strip()
    player_id = data.get("player_id", "").strip()
    player_name = data.get("player_name", "").strip()
    content = data.get("content", "")

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

@app.post("/settings/save_character_setting")
def save_character_setting():
    data = request.get_json(silent=True) or {}

    base_chat_path = data.get("base_chat_path", "").strip()
    character_id = data.get("character_id", "").strip()
    character_name = data.get("character_name", "").strip()
    content = data.get("content", "")

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

@app.post("/settings/load_character_settings")
def load_character_settings():
    data = request.get_json(silent=True) or {}

    base_chat_path = data.get("base_chat_path", "").strip()
    character_id = data.get("character_id", "").strip()

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

@app.get("/settings/load_image/<image_type>/<character_id>")
def load_image(image_type, character_id):

    base_chat_path = request.args.get("base_chat_path") or ""

    base_dir = Path(base_chat_path) / "characters"

    if image_type == "icon":
        save_dir = base_dir / "icon" / character_id
        filename = f"{character_id}.png"

    elif image_type == "standing":
        save_dir = base_dir / "standing" / character_id
        filename = f"{character_id}_standing.png"

    else:
        return jsonify({
            "ok": False,
            "message": "image_type が不正です"
        }), 400

    image_path = save_dir / filename

    print(image_path)
    
    if not image_path.exists():
        return jsonify({
            "ok": False,
            "message": "画像が存在しません"
        }), 404

    return send_file(image_path)

@app.post("/settings/save_image") 
def save_image():
    base_chat_path = request.form.get("base_chat_path") or ""
    image_type = request.form.get("image_type") or ""
    character_id = request.form.get("character_id") or ""
    file = request.files.get("file")

    base_dir = Path(base_chat_path) / "characters"

    if image_type == "icon":
        save_dir = base_dir / "icon" / character_id
        filename = f"{character_id}.png"

    elif image_type == "standing":
        save_dir = base_dir / "standing" / character_id
        filename = f"{character_id}_standing.png"

    save_dir.mkdir(parents=True, exist_ok=True)

    save_path = save_dir / filename

    file.save(save_path)

    return jsonify({
        "ok": True,
        "message": "画像を保存しました",
        "path": str(save_path)
    }), 200

def none_if_blank(value):
    if value is None:
        return None

    if isinstance(value, str):
        value = value.replace("\r\n", "\n").strip()
        return value if value else None

    return value

def save_world_yaml(world_id: str, form_data: dict, save_dir: Path):

    world_id = none_if_blank(world_id)
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

def to_literal_if_multiline(value):
    value = none_if_blank(value)

    if value is None:
        return None

    # 改行コード統一
    value = value.replace("\r\n", "\n")

    if "\n" in value:
        return LiteralString(value)

    return value

@app.post("/settings/load_model")
def load_model():
    payload = request.get_json(silent=True) or {}
    base_path = payload.get("base_path") or ""

    if not base_path:
        return _json_error("ベースパスが未設定です。", status=400)

    full_path = Path(base_path) / "files" / "settings" / "system_settings.yaml"

    if not full_path.exists() or not full_path.is_file():
        return _json_error("ファイル読み込み失敗", status=404, full_path=str(full_path))

    try:
        # TODO:
        # ここを既存のモデルロード処理に差し替えてください。
        # 例:
        # global loaded_model
        # loaded_model = load_model_from_yaml(full_path)
        return _json_ok(message="ロード完了", full_path=str(full_path))
    except Exception as exc:
        return _json_error(f"モデルロード失敗しました。{exc}", status=500, full_path=str(full_path))

############################################################################
# ここからメイン画面処理
############################################################################

@app.post("/load_session_list")
def load_session_list():
    data = request.get_json(silent=True) or {}

    try:
        world_id = data.get("world_id")

        if not world_id:
            return jsonify({
                "result": "error",
                "message": "world_id がありません"
            }), 400

        sessions_list_path = config.SYSTEM_DIR / "sessions_list.yaml"

        if sessions_list_path.exists():
            with sessions_list_path.open("r", encoding="utf-8") as f:
                sessions_data = yaml.safe_load(f) or {}
        else:
            sessions_data = {}

        sessions = sessions_data.get("sessions")
        if not isinstance(sessions, list):
            sessions = []

        world_sessions = [
            session for session in sessions
            if session.get("world_id") == world_id
        ]

        return jsonify({
            "result": "ok",
            "sessions": world_sessions
        })
    except Exception as e:
        return jsonify({
            "result": "error",
            "message": str(e)
        }), 500

# 世界選択
# 世界の名前、idと、該当世界の保持セッションID・セッション名一覧を返却
# セッションIDの新規作成はここでは行わない
@app.post("/world_start")
def world_start():
    try:
        data = request.get_json(silent=True) or {}

        world_id = data.get("world_id")
        world_name = data.get("world_name")

        if not world_id:
            return jsonify({
                "result": "error",
                "message": "world_id がありません"
            }), 400

        if not world_name:
            return jsonify({
                "result": "error",
                "message": "world_name がありません"
            }), 400

        sessions_list_path = config.SYSTEM_DIR / "sessions_list.yaml"

        if sessions_list_path.exists():
            with sessions_list_path.open("r", encoding="utf-8") as f:
                sessions_data = yaml.safe_load(f) or {}
        else:
            sessions_data = {}

        sessions = sessions_data.get("sessions")
        if not isinstance(sessions, list):
            sessions = []

        world_sessions = [
            session for session in sessions
            if session.get("world_id") == world_id
        ]

        return jsonify({
            "result": "ok",
            "world_id": world_id,
            "world_name": world_name,
            "sessions": world_sessions
        })

    except Exception as e:
        return jsonify({
            "result": "error",
            "message": str(e)
        }), 500
    
@app.post("/delete_session")
def delete_session():
    try:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")

        sessions_list_path = config.SYSTEM_DIR / "sessions_list.yaml"

        # ファイル読み込み
        if sessions_list_path.exists():
            with sessions_list_path.open("r", encoding="utf-8") as f:
                sessions_data = yaml.safe_load(f) or {}
        else:
            return jsonify({
                "status": "ok",
                "session_id": session_id
            }), 200

        # session削除
        sessions_data["sessions"] = [
            s for s in sessions_data.get("sessions", [])
            if s.get("session_id") != session_id
        ]

        # 保存
        with sessions_list_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                sessions_data,
                f,
                allow_unicode=True,
                sort_keys=False
            )


        # セッションディレクトリの削除

        session_dir = config.SESSIONS_DIR / session_id

        if session_dir.exists():
            shutil.rmtree(session_dir)

        return jsonify({
            "status": "ok",
            "session_id": session_id
        }), 200

    except Exception as e:
        return jsonify({
            "result": "error",
            "message": str(e)
        }), 500

#新しいチャットを開始する為の事前準備ファイル用意
@app.post("/chat_startup")
def chat_startup():
    body = request.get_json(force=True)
    # """新規チャット作成（/new_chat）"""
    session_id = str(uuid4())
    world_id = body.get("world_id")
    copy_source_dir = body.get("base_path")

    # pathの定義
    copy_source_character_dir = Path(copy_source_dir) / "characters" / "settings"
    copy_source_character_ico_dir = Path(copy_source_dir) / "characters" / "icon"
    copy_source_character_sta_dir = Path(copy_source_dir) / "characters" / "standing"
    copy_source_players_dir = Path(copy_source_dir) / "players" / "settings"
    copy_source_temp_file_path = Path(copy_source_dir) / "characters" / "template" / "character_setting_template.yaml"
    copy_dst_dir = config.SESSIONS_DIR / session_id
    copy_dst_char_dir = config.SESSIONS_DIR / session_id / "character"
    copy_dst_pic_dir = config.SESSIONS_DIR / session_id / "picture"
    copy_dst_ico_dir = config.SESSIONS_DIR / session_id / "picture" / "icon"
    copy_dst_sta_dir = config.SESSIONS_DIR / session_id / "picture" / "standing"

    # directryの用意
    copy_dst_dir.mkdir(exist_ok=True)
    copy_dst_char_dir.mkdir(exist_ok=True)
    copy_dst_pic_dir.mkdir(exist_ok=True)
    copy_dst_ico_dir.mkdir(exist_ok=True)
    copy_dst_sta_dir.mkdir(exist_ok=True)
    
    world_file_path = Path(copy_source_dir) / "worlds" / "settings" / f"{world_id}_world.yaml"
    world_file = file_utils.load_yaml_file(world_file_path)

    world_characters = (
        world_file
        .get("登場人物", {})
        .get("世界の登場人物", [])
    )

    # 世界ファイル保存
    copy2(world_file_path, copy_dst_dir)
    # 世界ファイル内の各キャラクターファイル保存
    for characters_info in world_characters:
        character_id = characters_info.get("参照ID")
        if characters_info.get("参照種別") == "player":
            print("プレイヤー用")
            src = copy_source_players_dir / f"{character_id}_setting.yaml"
            copy2(src, copy_dst_char_dir)
        
        if characters_info.get("参照種別") == "character":
            print("メインキャラ用")
            src = copy_source_character_dir / f"{character_id}_setting.yaml"
            src_ico = copy_source_character_ico_dir / f"{character_id}" / f"{character_id}.png"
            src_sta = copy_source_character_sta_dir / f"{character_id}" / f"{character_id}_standing.png"

            copy2(src, copy_dst_char_dir)
            copy2(src_ico, copy_dst_ico_dir)
            copy2(src_sta, copy_dst_sta_dir)
        
        if characters_info.get("参照種別") == "inline":
            print("その他作成する必要あり")
            #templateを一旦コピー
            copy2(
                copy_source_temp_file_path,
                copy_dst_char_dir / f"{character_id}.yaml"
            )
            #コピー先のテンプレートを読み込む
            sub_char_yaml = file_utils.load_yaml_file(copy_dst_char_dir / f"{character_id}.yaml")

            #読み込んだテンプレートのIDと名前を変更
            sub_display_name = characters_info.get("表示名")
            rubi = None
            sub_character_id = characters_info.get("参照ID")
            sub_char_yaml["名前"]["表示名"] = sub_display_name
            sub_char_yaml["名前"]["ふりがな"] = rubi
            sub_char_yaml["名前"]["識別子"] = sub_character_id
            #保存
            file_utils.save_yaml_file(copy_dst_char_dir / f"{character_id}.yaml", sub_char_yaml)
        print("その他作成する必要なし")
    
    #sessions_listの最終行へ追記
    sessions_list_path = config.SYSTEM_DIR / "sessions_list.yaml"

    # sessions_list.yaml 読み込み
    if sessions_list_path.exists():
        with sessions_list_path.open("r", encoding="utf-8") as f:
            sessions_data = yaml.safe_load(f) or {}
    else:
        sessions_data = {}

    sessions = sessions_data.get("sessions")

    same_world_sessions = [
        s for s in sessions
        if s.get("world_id") == world_id
    ]

    world_no = len(same_world_sessions) + 1

    now_text = datetime.now().strftime("%Y年%m月%d日 %H:%M")

    display_name = f"{world_file.get('世界名')}-{world_no}"
    world_name = world_file.get("世界名")

    new_session = {
        "session_id": session_id,
        "display_name": display_name,
        "world_id": world_id,
        "world_name": world_name,
        "created_at": now_text,
        "updated_at": now_text,
    }

    sessions.append(new_session)
    sessions_data["sessions"] = sessions

    with sessions_list_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            sessions_data,
            f,
            allow_unicode=True,
            sort_keys=False
        )
        
    print("初期ファイル用意完了", copy_dst_dir.as_uri())
    return jsonify({
        "status": "ok",
        "session_id": session_id,
        "world_id": world_id,
        "world_name": world_name,
        "display_name": display_name
    }), 200

@app.post("/new_chat")
def new_chat():
    print("ニューチャット開始")
    """SillyTavernのNew Chat時に呼ばれる初期化処理"""
    if request.method == "OPTIONS":
        return "", 200

    try:

        body = request.get_json(force=True)
        # start_message = orchestrator.create_new_session(body)
        
        print("ニューチャット終了")
        # print("body全量", body)
        return jsonify({
            "status": "ok",
            "session_id": body.get("session_id"),
            "start_message": "モデルを使わないテスト返却",
            "icon_data": {"character_id": "shirai_yui",
                          "character_name": "白井　結"}
        }), 200

    except Exception as e:
        print(f"[ERROR] /new_chat: {e}")
        return jsonify({"error": str(e)}), 500

#前処理受け口
@app.post("/v1/chat/prepare")
def chat_prepare():
    print("前処理のログ")

    try:
        # Yamlの設定に変更があれば読み直しておく
        system_settings_reload_service.SystemSettingsReloadCheckService()

        body = request.get_json(force=True)
        # デバッグログ（必要に応じて残す）
        # print("=== Request Headers ===")
        # for key, value in request.headers.items():
        #     print(f"{key}: {value}")
        # print("=====================")
        # print("body全量:", body)

        # 前処理します
        # TODO 1文字は恐らく判別出来ないから何もしない
        if len(body.get("message")) > 1:
            result = {}
            result = orchestrator.chat_pretreatment(body)
        return "", 200

    except Exception as e:
        print(f"[ERROR] /v1/chat/prepare: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500

#後処理受け口
@app.post("/v1/chat/after")
def chat_after():
    print("後処理のログ")

    try:
        # Yamlの設定に変更があれば読み直しておく
        system_settings_reload_service.SystemSettingsReloadCheckService()

        body = request.get_json(force=True)
        allow_image = request.headers.get("X-Allow-Image", "false").lower() == "true"
        session_id = body.get("session_id")
        
        error_response = _wait_chat_stage_or_response(
            session_id,
            "prepare",
            "prepare が error で終了しました。prepare_status.yaml を確認してください。",
        )
        if error_response:
            return error_response

        result = orchestrator.chat_post_processing(body)
        return "", 200

    except Exception as e:
        print(f"[ERROR] /v1/chat/after: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500

#チャット時受け口
@app.post("/v1/chat/completions")
def chat_completions():
    if request.method == "OPTIONS":
        return "", 200

    try:
        # Yamlの設定に変更があれば読み直しておく
        system_settings_reload_service.SystemSettingsReloadCheckService()

        body = request.get_json(force=True)
        allow_image = request.headers.get("X-Allow-Image", "false").lower() == "true"
        session_id = body.get("session_id")

        result = {}

        if body.get("first_flag") == "first":
            print("１回目のログ")

            error_response = _wait_chat_stage_or_response(
                session_id,
                "prepare",
                "prepare が error で終了しました。prepare_status.yaml を確認してください。",
            )
            if error_response:
                return error_response

            result = orchestrator.handle_chat_completion(body, allow_image)

        else:
            print("２回目のログ")

            error_response = _wait_chat_stage_or_response(
                session_id,
                "main_chat",
                "main_chat が error で終了しました。prepare_status.yaml を確認してください。",
            )
            if error_response:
                return error_response

            result = orchestrator.handle_mob_chat_completion(body, allow_image)

        return jsonify(result["response"]), result.get("status_code", 200)

    except Exception as e:
        print(f"[ERROR] /v1/chat/completions: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500
    
# 使用モデル受け口
@app.get("/v1/models")
def list_models():
    """SillyTavernのモデル一覧要求へのダミー応答"""
    return jsonify({
        "object": "list",
        "data": [
            {"id": config.DEFAULT_MODEL, "object": "model", "owned_by": "local-proxy"}
        ]
    })

# StabilityMatrix起動確認受け口
@app.route("/v1/chat/check_stability", methods=["GET", "POST", "OPTIONS"])
def check_stability():
    """Stability Matrixの起動確認（Silly Tavern改造対応）"""
    # OPTIONSプリフライト対応（重要）
    if request.method == "OPTIONS":
        return "", 200

    try:

        # Yamlの設定に変更があれば読み直しておく
        system_settings_reload_service.SystemSettingsReloadCheckService()

        result = True
        message = "起動してます。OK"

#        if generateImage.test_communication_confirmation():
#            message = "起動してます。OK"
#        else:
        result = False
        message = "起動してないよ。"

        return jsonify({
            "ok": result,
            "message": message
        }), 200

    except Exception as e:
        print(f"[ERROR] check_stability: {e}")
        return jsonify({
            "ok": False,
            "message": f"チェック中にエラー: {str(e)}"
        }), 500
    
# 前中後処理が失敗した際に使っているが、置き場はここじゃないと思うのでTODO
def _wait_chat_stage_or_response(session_id: str, target_stage: str, error_message: str):
    if not session_id:
        return None

    ok = file_utils.wait_until_prepare_status(
        session_id,
        target_stage=target_stage,
        interval_sec=0.2,
    )

    if ok:
        return None

    return jsonify({"error": error_message}), 500

if __name__ == "__main__":
    print(f"Starting RP Backend on http://0.0.0.0:{config.PORT}")

    app.run(host="0.0.0.0", port=5000, debug=False)