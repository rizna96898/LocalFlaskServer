from flask import jsonify, send_file
from pathlib import Path

def load_image(self, base_chat_path, image_type, character_id):
    
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

def save_image(self, base_chat_path, image_type, character_id, file):

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
