"""
世界関係管理モジュール（PNGカード対応・非同期キャッシュ）
"""

from pathlib import Path
from typing import Dict, List, Optional
import json
import re
import base64
from threading import Thread

from config import config
from PIL import Image
from helpers.file_utils import save_json_file, load_yaml_file, save_yaml_file


class WorldManager:
    def __init__(self):
        self.characters_dir = Path(config.CHARACTERS_DIR)
        print(f"[WorldManager] キャラクターカードフォルダ: {self.characters_dir}")

    def find_character_by_name(self, name: str) -> Optional[Dict]:
        """名前から.pngカードを検索して情報を返す"""
        if not self.characters_dir.exists():
            print(f"[ERROR] キャラクターカードフォルダが見つかりません")
            return None

        search_name = name.replace(" ", "").replace("　", "").replace("\u3000", "").lower()

        for file in self.characters_dir.glob("*.png"):
            try:
                card_data = self.extract_json_from_png(file)
                if not card_data:
                    continue

                card_name = card_data.get("name", "").replace(" ", "").replace("　", "").replace("\u3000", "").lower()

                if search_name in card_name or card_name in search_name:
                    print(f"[WorldManager] キャラカード発見: {card_data.get('name')} ({file.name})")

                    return {
                        "name": card_data.get("name", "").strip(),
                        "description": card_data.get("description", ""),
                        "personality": card_data.get("personality", ""),
                        "scenario": card_data.get("scenario", ""),
                        "first_mes": card_data.get("first_mes", ""),
                        "mes_example": card_data.get("mes_example", ""),
                        "file_path": str(file)
                    }
            except Exception as e:
                print(f"[WARN] カード処理失敗 {file.name}: {e}")

        print(f"[WorldManager] 該当キャラが見つかりませんでした: {name}")
        return None

    def extract_json_from_png(self, png_path: Path) -> Optional[Dict]:
        """PNGからJSONを抽出（Silly Tavern対応強化版）"""
        try:
            with open(png_path, "rb") as f:
                data = f.read()

            pos = 0
            while True:
                pos = data.find(b"tEXt", pos)
                if pos == -1:
                    break

                length = int.from_bytes(data[pos-4:pos], "big")
                chunk_data = data[pos+4:pos+4+length]

                if b'\x00' in chunk_data:
                    key_bytes, value_bytes = chunk_data.split(b'\x00', 1)
                    key = key_bytes.decode("ascii", errors="ignore")
                    value = value_bytes.decode("utf-8", errors="ignore")

                    if key in ["chara", "ccv3", "parameters"]:
                        try:
                            if value.startswith("data:"):
                                value = value.split(",", 1)[1]
                            decoded = base64.b64decode(value).decode("utf-8")
                            card_data = json.loads(decoded)
                            if isinstance(card_data, dict) and card_data.get("name"):
                                return card_data
                        except:
                            try:
                                card_data = json.loads(value)
                                if isinstance(card_data, dict) and card_data.get("name"):
                                    return card_data
                            except:
                                pass

                pos += length + 12

        except Exception as e:
            print(f"[WARN] PNG抽出失敗 {png_path.name}: {e}")

        return None

    def add_character_to_world_async(self, session_id: str, character_name: str):
        """会話中に新しいキャラが登場したら、非同期で解析してキャッシュする"""
        def task():
            try:
                print(f"[WorldManager] 非同期解析開始: {character_name}")

                card = self.find_character_by_name(character_name)
                if not card:
                    print(f"[WorldManager] キャラカード未発見: {character_name}")
                    return

                # char_cardフォルダを作成
                char_card_dir = config.SESSIONS_DIR / session_id / "char_card"
                char_card_dir.mkdir(exist_ok=True)

                # JSONとして保存
                cache_file = char_card_dir / f"{character_name}.json"
                save_json_file(cache_file, card)

                # world_relationにも追加
                memory_path = config.SESSIONS_DIR / session_id / "memory.yaml"
                memory = load_yaml_file(memory_path) or {}

                if "world_relation" not in memory:
                    memory["world_relation"] = []

                if character_name not in memory["world_relation"]:
                    memory["world_relation"].append(character_name)

                save_yaml_file(memory_path, memory)
                print(f"[WorldManager] キャッシュ保存完了: {character_name}")

            except Exception as e:
                print(f"[WorldManager] 非同期処理エラー: {e}")

        Thread(target=task, daemon=True).start()