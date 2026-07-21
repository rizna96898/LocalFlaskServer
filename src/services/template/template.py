import os
from flask import jsonify

def get_template_world_include_player_yaml(self, payload):
    base_chat_path = payload.get("base_chat_path", "")
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

def get_template_world_goal_setting_yaml(self, payload):
    base_chat_path = payload.get("base_chat_path", "")
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

def get_template_world_parameter_setting_yaml(self, payload):
    base_chat_path = payload.get("base_chat_path", "")
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

def get_template_player_yaml(self, payload):
    base_chat_path = payload.get("base_chat_path", "")
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

def get_template_character_yaml(self, payload):
    base_chat_path = payload.get("base_chat_path", "")
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
