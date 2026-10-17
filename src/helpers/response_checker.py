from flask import jsonify
def is_invalid_world_memory(data):
    return (
        not data
        or "現在の状態" not in data
        or "世界の状態" not in data
    )

# レスポンスの統一
def response_ok(**kwargs):
    return jsonify({"ok": True, **kwargs})

# レスポンスの統一
def response_error(message: str, status: int = 400, **kwargs):
    return jsonify({"ok": False, "message": message, **kwargs}), status
