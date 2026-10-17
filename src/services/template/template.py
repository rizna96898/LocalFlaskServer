import os
from helpers import response_checker

def get_template_world_include_player_yaml(payload):
    base_chat_path = payload.get("base_chat_path", "")
    if not base_chat_path:
        return response_checker.response_error("base_chat_pathが未指定です", 400)

    file_path = os.path.join(
        base_chat_path,
        "worlds",
        "template",
        "include_player_template.yaml"
    )

    if not os.path.exists(file_path):
        return response_checker.response_error(f"ファイルが存在しません: {file_path}", 404)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return response_checker.response_error(str(e), 500)

    return response_checker.response_ok(content=content) 

def get_template_world_goal_setting_yaml(payload):
    base_chat_path = payload.get("base_chat_path", "")
    if not base_chat_path:
        return response_checker.response_error("base_chat_pathが未指定です", 400)

    file_path = os.path.join(
        base_chat_path,
        "worlds",
        "template",
        "scenario_goal_setting_template.yaml"
    )

    if not os.path.exists(file_path):
        return response_checker.response_error(f"ファイルが存在しません: {file_path}", 404)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return response_checker.response_error(str(e), 500)

    return response_checker.response_ok(content=content)

def get_template_world_parameter_setting_yaml(payload):
    base_chat_path = payload.get("base_chat_path", "")
    if not base_chat_path:
        return response_checker.response_error("base_chat_pathが未指定です", 400)

    file_path = os.path.join(
        base_chat_path,
        "worlds",
        "template",
        "scenario_parameter_setting_template.yaml"
    )

    if not os.path.exists(file_path):
        return response_checker.response_error(f"ファイルが存在しません: {file_path}", 404)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return response_checker.response_error(str(e), 500)

    return response_checker.response_ok(content=content)

def get_template_player_yaml(payload):
    base_chat_path = payload.get("base_chat_path", "")
    if not base_chat_path:
        return response_checker.response_error("base_chat_pathが未指定です", 400)

    file_path = os.path.join(
        base_chat_path,
        "players",
        "template",
        "player_setting_template.yaml"
    )

    if not os.path.exists(file_path):
        return response_checker.response_error(f"ファイルが存在しません: {file_path}", 404)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return response_checker.response_error(str(e), 500)

    return response_checker.response_ok(content=content)

def get_template_character_yaml(payload):
    base_chat_path = payload.get("base_chat_path", "")
    if not base_chat_path:
        return response_checker.response_error("base_chat_pathが未指定です", 400)

    file_path = os.path.join(
        base_chat_path,
        "characters",
        "template",
        "character_setting_template.yaml"
    )

    if not os.path.exists(file_path):
        return response_checker.response_error(f"ファイルが存在しません: {file_path}", 404)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return response_checker.response_error(str(e), 500)

    return response_checker.response_ok(content=content)
