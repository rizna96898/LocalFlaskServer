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
def _json_error(message: str, status: int = 400, **kwargs):
    return jsonify({"ok": False, "message": message, **kwargs}), status

def chat_response_ok(payload: dict, line_id: str, message: str, icon_data: str):
    return jsonify({
            "status": "ok",
            "session_id": payload.get("session_id"),
            "line_id": line_id,
            "message": message,
            "icon_data": icon_data
        })