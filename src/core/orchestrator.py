"""
チャット処理の全体を統括するオーケストレーター
- 新規チャット時の初期化
- チャット時前処理
- 応答作成
- チャット時後処理
- 画像作成
"""

import uuid
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Iterable
from helpers import data_utils
from config import config
from services.openrouter_service import OpenRouterService

# ヘルパー
from helpers import string_utils
from helpers import file_utils
from helpers.data_utils import has_changes, merge_character_data

# 記憶管理
from core.memory_manager import MemoryManager

# プロンプト構築
from core.prompt_builder import PromptBuilder


class ChatOrchestrator:
    def __init__(self):
        self.openrouter = OpenRouterService()
        self.memory_manager = MemoryManager()
        self.prompt_builder = PromptBuilder()
        # print("[Orchestrator] Initialized")

    # ニューチャット
    def create_new_session(self, body: Dict) -> str:
        # """新規チャット作成（/new_chat）"""
        session_id = body.get("session_id") or str(uuid.uuid4())

        # セッションディレクトリ作成
        file_utils.ensure_session_dir(config.SESSIONS_DIR, session_id)

        # ニューチャット用ステータス作成
        file_utils.create_prepare_status(session_id)

        # キャラクター設定の同期
        self._sync_character_if_changed(session_id, body)

        # bodyにsession_idを明示的に入れて渡す
        call_body = body.copy()
        call_body["session_id"] = session_id

        # 初期記憶の非同期作成
        self.memory_manager.create_initial_memory(call_body, session_id)

        return session_id

    # 前処理
    def chat_pretreatment(self, body: Dict) -> Dict:
        print("[ORCH] chat_pretreatment start")

        session_id = body.get("session_id")

        try:
            print(f"[ORCH] session_id={session_id}")

            if not session_id:
                print("[ERROR] chat_pretreatment: session_id取得エラー")
                return {
                    "response": {
                        "error": "session_idが何らかの理由で取れなかったので新しいチャットを開始してください。"
                    },
                    "status_code": 503,
                }

            file_utils.mark_prepare_processing(session_id, "prepare")

            self.memory_manager.create_target_speakers(session_id, body)

            return {
                "ok": True,
                "body": body,
            }

        except Exception as e:
            print(f"[ERROR] chat_pretreatment: {e}")
            import traceback
            print(traceback.format_exc())

            if session_id:
                file_utils.mark_prepare_error(
                    session_id,
                    complete_stage="prepare",
                    error_stage="prepare",
                    error_message=f"{type(e).__name__}: {e}",
                )

            return {"error": "Internal server error"}, 500
    
    # 後処理
    def chat_post_processing(self, body: Dict) -> Dict:
        print("[ORCH] chat_post_processing start")

        session_id = body.get("session_id")

        try:
            print(f"[ORCH] session_id={session_id}")

            if not session_id:
                print("[ERROR] chat_post_processing: session_id取得エラー")
                return {
                    "response": {
                        "error": "session_idが何らかの理由で取れなかったので新しいチャットを開始してください。"
                    },
                    "status_code": 503,
                }

            needs_mob_chat = file_utils.get_needs_mob_chat(session_id)
            wait_stage = "mob_chat" if needs_mob_chat else "main_chat"

            ok = file_utils.wait_until_prepare_status(
                session_id,
                target_stage=wait_stage,
                interval_sec=0.2,
            )
            if not ok:
                return {
                    "response": {"error": f"{wait_stage} が error で終了しました。"},
                    "status_code": 500,
                }

            file_utils.mark_prepare_processing(session_id, "after")

            # TODO:
            # 履歴作成
            # world_memory 更新
            # character_memory 更新

            file_utils.mark_prepare_ready(session_id, "after")

            return {
                "ok": True,
                "history": None,
            }

        except Exception as e:
            print(f"[ERROR] chat_post_processing: {e}")
            import traceback
            print(traceback.format_exc())

            if session_id:
                file_utils.mark_prepare_error(
                    session_id,
                    complete_stage="after",
                    error_stage="after",
                    error_message=f"{type(e).__name__}: {e}",
                )

            return {"error": "Internal server error"}, 500
    
    # 多分トータルのチャットハンドラーが必要になる（と思ってる）

    # メインプレイヤーチャット（予定）
    def handle_chat_completion(self, body: Dict, allow_image: bool = False) -> Dict:
        session_id = body.get("session_id")

        try:
            if not session_id:
                return {
                    "response": {"error": "session_idがありません。"},
                    "status_code": 503,
                }

            # 更新管理ファイルのステータスチェック
            ok = file_utils.wait_until_prepare_status(
                session_id,
                target_stage="prepare",
                interval_sec=0.2,
            )
            if not ok:
                return {
                    "response": {"error": "prepare が error で終了しました。"},
                    "status_code": 500,
                }
            file_utils.mark_prepare_processing(session_id, "main_chat")

            # 履歴ファイルをロードする。
            directory_full_path = config.SESSIONS_DIR / session_id
            history = file_utils.load_history(directory_full_path)

            # world.yaml を読み込む（日付用）
            world_file = config.SESSIONS_DIR / session_id / "world_memory.yaml"
            world_data = file_utils.load_yaml_file(world_file) or {}

            # session_idの取得
            call_body = body.copy()
            call_body["session_id"] = session_id

            # TODO
            # 返信が壊れないようにメモリを作る必要あり

            # print("システムプロンプト：", system_message)
            # 今回のユーザ発言を取得する
            messages = body.get("messages", [])
            last_user_message = string_utils.get_reversed_user_message(messages)

            player_name = world_data["player_name"]
            print("プレイヤー名：", player_name)

            # メインプレイヤーのyamlを読み込む
            char_file = config.SESSIONS_DIR / session_id / "character"
            player_path = file_utils.find_character_file(player_name, char_file)
            player_data = file_utils.load_yaml_file(player_path) or {}

            # 誰向けの発言か。
            character_name = player_data["last_target"]
            print("誰向けの発言か", character_name) 

            
            # 日付取得
            world_time = ""
            current_state = world_data.get("current_state", {})
            if isinstance(current_state, dict):
                world_time = str(current_state.get("time", "")).strip()

            # print("[ORCH] before main reply generation")
            # 6) 応答生成
            #    ここで LLM にチャットを投げる
            # キャラ名と情報を渡しているが足りない
            system_message = file_utils.build_character_comment_system_message(
                session_id=session_id,
                character_name=character_name,
                sessions_dir=config.SESSIONS_DIR,
                prompt_file = config.PROMPTS_DIR / "character_comment_prompt.yaml"
            )

            response_text = self._generate_response(session_id, messages, system_message)

            # 今回の発言がプレイヤーに向けられた物かどうか判別
            # yamlのロード
            prompt_data = file_utils.load_yaml_file(
                config.PROMPTS_DIR / "character_identification.yaml"
            ) or {}

            world_participants = string_utils.build_characters_text(world_data["current_state"]["participants"])

            print("current participantsの編集後文字列", world_participants)
            print("実行プロンプト原文", prompt_data)
            system_prompt = prompt_data["system"]
            template_prompt = prompt_data["template"]

            template_prompt = template_prompt.replace("{characters}", world_participants)
            template_prompt = template_prompt.replace("{player_message}", response_text)
            
            print("置換後プロンプト全文", template_prompt)

            service = OpenRouterService()
            
            result = service.send_message(
                messages=[
                    {"role": "user", "content": template_prompt}
                ],
                system_prompt=system_prompt
            )

            parsed = yaml.safe_load(string_utils.strip_code_block(result)) or {}
            
            target_text = parsed.get("target_speakers")

            print("今回の結の発話対象：", target_text)

            # キャラファイルを読み込む
            caracter_path = file_utils.find_character_file(character_name, char_file)
            caracter_data = file_utils.load_yaml_file(caracter_path) or {}
            caracter_full_name = caracter_data["name"]

            # キャラ_memoryを読み込む
            memory_file = config.SESSIONS_DIR / session_id / "character"
            memory_path = file_utils.find_character_memory_file(caracter_full_name, memory_file)
            print("load target", memory_path)
            character_memory_data = file_utils.load_yaml_file(memory_path) or {}

            # parameter取得
            parameter_lines = []
            parameter_list = character_memory_data.get("parameter", [])
            if isinstance(parameter_list, list):
                for item in parameter_list:
                    if not isinstance(item, dict):
                        continue

                    display_name = str(item.get("display_name", "")).strip()
                    count = item.get("count", 0)

                    if not display_name:
                        continue

                    parameter_lines.append(f"{display_name}：{count}")

            # 表示用本文を組み立て
            display_parts = []

            if world_time:
                display_parts.append(f"（{world_time}）")

            display_parts.append(response_text)

            if parameter_lines:
                display_parts.append("\n".join(parameter_lines))

            display_text = "\n".join(display_parts)
            
            # ここが変だよ日本人
            # 今回の発言で話しかけたかどうか判定しないと駄目かな？
            # その場にいるからと言って話しかけたかどうかは中身を見ないといけない
            print("load character memory. focus_targets", character_memory_data["current_state"]["focus_targets"])

            forcus_target = character_memory_data["current_state"]["focus_targets"]
            participants = character_memory_data.get("participants", [])

            # 本チャット後の「次話者候補」
            next_speakers = []

            call_target_text = string_utils.find_existing_character(last_user_message, participants)

            # 1. focus_targets が1人なら、その人を次話者候補にする
            if len(forcus_target) == 1:
                # name配列だけ持つ
                next_speakers = [
                    str(item.get("name")).strip()
                    for item in forcus_target
                    if isinstance(item, dict) and item.get("name")
                ]

            else:
                # 2. ２名以上 focus_targets に存在する場合や、
                #    引っかからない / 新規モブの場合は後でLLM判定
                print("TODO: ask target judge LLM")

            needs_mob_chat = len(next_speakers) > 0
            mob_count = len(next_speakers)

            # 履歴保存
            history.append({
                "t": time.time(),
                "speaker": "player",
                "role": "user",
                "content": last_user_message
            })
            history.append({
                "t": time.time(),
                "speaker": caracter_full_name,
                "role": "assistant",
                "content": response_text
            })
            file_utils.save_history(directory_full_path, history)

            print("次の発言者予定", next_speakers)
            print("フラグ", needs_mob_chat)

            result = {
                "response": {
                    "id": f"chatcmpl-{session_id[:8]}",
                    "object": "chat.completion",
                    "created": int(datetime.now().timestamp()),
                    "model": body.get("model", config.DEFAULT_MODEL),
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "name": caracter_full_name,
                            "original_avatar": caracter_full_name + ".png",
                            "force_avatar": caracter_full_name + ".png",
                            "content": display_text
                        },
                        "finish_reason": "stop",
                        # ↓ 次話者情報
                        "target_speakers": next_speakers,
                        "remaining_speakers": next_speakers,
                        "needs_mob_chat": needs_mob_chat,
                        "mob_count": mob_count,
                    }],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    }
                },
                "status_code": 200
            }

            file_utils.update_prepare_status(
                session_id,
                status="ready",
                complete_stage="main_chat",
                error_stage=None,
                error_message=None,
                needs_mob_chat=needs_mob_chat,
                mob_count=mob_count,
                next_speakers=next_speakers,
            )

            return result

        except Exception as e:
            print(f"[ERROR] handle_chat_completion: {e}")
            import traceback
            print(traceback.format_exc())

            if session_id:
                file_utils.mark_prepare_error(
                    session_id,
                    complete_stage="main_chat",
                    error_stage="main_chat",
                    error_message=f"{type(e).__name__}: {e}",
                )

            return {
                "response": {"error": "Internal server error"},
                "status_code": 500,
            }

    # サブキャラクターチャット（予定）
    def handle_mob_chat_completion(self, body: Dict, allow_image: bool = False) -> Dict:
        print("[ORCH] handle_mob_chat_completion start")

        session_id = body.get("session_id")
        print(f"[ORCH] session_id={session_id}")

        try:
            if not session_id:
                return {
                    "response": {"error": "session_idがありません。"},
                    "status_code": 503,
                }

            ok = file_utils.wait_until_prepare_status(
                session_id,
                target_stage="main_chat",
                interval_sec=0.2,
            )
            if not ok:
                return {
                    "response": {"error": "main_chat が error で終了しました。"},
                    "status_code": 500,
                }

            file_utils.mark_prepare_processing(session_id, "mob_chat")
            # TODO
            # mob同士の会話をどうするか悩む（多分発生しないか、禁止が良さげ）
            # mobの履歴も一応持つ（名前を付ければ判別できるから）

            result = {
                "response": {
                    "id": f"chatcmpl-{session_id[:8]}",
                    "object": "chat.completion",
                    "created": int(datetime.now().timestamp()),
                    "model": body.get("model", config.DEFAULT_MODEL),
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "name": "白井　圭太",
                            "original_avatar": "白井　圭太.png",
                            "force_avatar": "白井　圭太.png",
                            "content": "二人目の発言だよ",
                        },
                        "finish_reason": "stop",
                        # ↓ 次話者情報
                        "target_speakers": "",
                        "remaining_speakers": "",
                        "needs_mob_chat": False,
                        "mob_count": 0,
                    }],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    }
                },
                "status_code": 200
            }
        
            file_utils.mark_prepare_ready(session_id, "mob_chat")

            return result

        except Exception as e:
            print(f"[ERROR] handle_mob_chat_completion: {e}")
            import traceback
            print(traceback.format_exc())

            if session_id:
                file_utils.mark_prepare_error(
                    session_id,
                    complete_stage="mob_chat",
                    error_stage="mob_chat",
                    error_message=f"{type(e).__name__}: {e}",
                )

            return {
                "response": {"error": "Internal server error"},
                "status_code": 500,
            }

    def _sync_character_if_changed(self, session_id: str, body: Dict):
        print("_sync_character_if_changed start")
        """SillyTavernから来たメインキャラクター情報を session の world.yaml に同期

        役割:
        - 主人公 / メインキャラの最新カード情報を session 側へ持ってくる
        - ここは world_relation の関連キャラ同期とは別枠
        """
        
        character_file = config.SESSIONS_DIR / session_id / "world.yaml"
        # print(f"[DEBUG] load target = {character_file}")
        current = file_utils.load_yaml_file(character_file) or {}

        new_data = {
            "name": body.get("name"),
            "description": string_utils.clean_for_save(body.get("description", "")),
            "personality": string_utils.clean_for_save(body.get("personality", "")),
            "scenario": string_utils.clean_for_save(body.get("scenario", "")),
            "first_mes": string_utils.clean_for_save(body.get("first_mes", "")),
            "mes_example": string_utils.clean_for_save(body.get("mes_example", "")),
        }

        # print("比較元内容（ファイルの中)", current);
        # print("比較先内容（bodyの中）", new_data);
        # print("比較結果", has_changes(current, new_data));
        if has_changes(current, new_data):
            # print("has_changes start")
            updated = merge_character_data(current, new_data)
            success = file_utils.save_yaml_file(character_file, updated)
            if success:
                print(f"[CHARACTER] Updated for session {session_id}")
            else:
                print(f"[WARN] Failed to update character.yaml for {session_id}")
        print("_sync_character_if_changed end")

    def _sync_related_characters_from_memory(self, session_id: str):
        """
        memory.yaml の world_relation を見て、関連キャラの最新カードを
        session配下の characters フォルダへ同期する。

        目的:
        - SillyTavern 上で更新されたキャラ情報を次の発話から反映させる
        - 会話に登場中のキャラだけを必要な分だけ毎回更新する
        """
        memory_file = config.SESSIONS_DIR / session_id / "memory.yaml"
        memory_data = file_utils.load_yaml_file(memory_file) or {}
        related_names = string_utils._clean_world_relation(memory_data.get("world_relation", []))

        if not related_names:
            print(f"[WORLD_RELATION] session_id={session_id} → 対象なし")
            return

        # world_relation から拾うだけなので、import失敗時は全体を落とさずスキップする
        try:
            from core.world_manager import WorldManager
        except Exception as e:
            print(f"[WARN] WorldManager import failed: {e}")
            return

        world_manager = WorldManager()
        output_dir = config.SESSIONS_DIR / session_id / "characters"
        output_dir.mkdir(parents=True, exist_ok=True)

        # print(f"[WORLD_RELATION] session_id={session_id} → {related_names}")

        for character_name in related_names:
            try:
                card_data = world_manager.find_character_by_name(character_name)
                if not card_data:
                    print(f"[WORLD_RELATION] 未検出: {character_name}")
                    continue

                safe_name = string_utils._normalize_name(str(card_data.get("name") or character_name))
                character_file = output_dir / f"{safe_name}.yaml"
                current = file_utils.load_yaml_file(character_file) or {}
                latest = string_utils._convert_to_yaml_format(card_data)

                if has_changes(current, latest):
                    updated = merge_character_data(current, latest)
                    if file_utils.save_yaml_file(character_file, updated):
                        print(f"[WORLD_RELATION] 同期: {character_name} -> {character_file.name}")
                    else:
                        print(f"[WARN] 保存失敗: {character_file}")
                else:
                    print(f"[WORLD_RELATION] 変更なし: {character_name}")

            except Exception as e:
                print(f"[WARN] 関連キャラ同期失敗: {character_name}: {e}")

    def _generate_response(self, session_id: str, messages: list, system_prompt: str) -> str:
        """最終応答生成

        現状:
        - 最後の user メッセージだけを抜き出して LLM へ渡している

        今後の見直し候補:
        - 会話履歴をどこまで渡すか
        - memory.yaml や related characters をプロンプトへどう混ぜるか
        - response_text 生成後に事後更新をどう差し込むか
        """
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        try:
            response_text = self.openrouter.send_message(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=system_prompt,
                temperature=config.TEMPERATURE,
                max_tokens=config.MAX_TOKENS
            )
            return response_text

        except Exception as e:
            print(f"[ERROR] _generate_response: {e}")
            return "すみません、今ちょっと調子が悪いみたいです…"
