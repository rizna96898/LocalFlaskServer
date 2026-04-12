"""
チャット処理の全体を統括するオーケストレーター
- 新規チャット時の初期化
- キャラクター設定同期
- 記憶管理（MemoryManager連携）
- 最終応答生成
"""

import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Iterable

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
        print("[Orchestrator] Initialized")

    def create_new_session(self, body: Dict) -> str:
        """新規チャット作成（/new_chat）"""
        session_id = body.get("session_id") or str(uuid.uuid4())

        # セッションディレクトリ作成
        file_utils.ensure_session_dir(config.SESSIONS_DIR, session_id)

        # キャラクター設定の同期
        self._sync_character_if_changed(session_id, body)

        # bodyにsession_idを明示的に入れて渡す
        call_body = body.copy()
        call_body["session_id"] = session_id

        # 初期記憶の非同期作成
        print(f"[NEW SESSION] session_id={session_id} → 初期記憶作成を開始")
        self.memory_manager.create_initial_memory(call_body, session_id)

        print(f"[NEW SESSION] Created session: {session_id}")
        return session_id

    def handle_chat_completion(self, body: Dict, allow_image: bool = False) -> Dict:
        """メインのチャット処理

        現在想定している大まかな流れ（ドラフト）:
        1. チャットを受け取る
        2. session_id を確定する
        3. 事前の主人公キャラ設定を同期する
        4. 事前の記憶更新を行う
           - 世界観や関係性の変更を先に memory.yaml へ反映したい想定
        5. memory.yaml の world_relation を見て関連キャラyamlを同期する
        6. LLMへチャットを投げて応答を生成する
        7. 履歴を残す（未実装）
        8. 応答結果を踏まえて事後の記憶更新を行う（未実装）
        9. 新規キャラがいればキャラ設定を追加する（未実装）

        注意:
        - 今の実装は「事前更新」寄りで、応答後の更新はまだ入っていない
        - そのため、記憶や進展が1ターンずれる可能性がある
        """
        try:
            session_id = body.get("session_id")
            print("一応確認：", session_id);
            if not session_id:
                session_id = "temp_session_" + str(int(datetime.now().timestamp()))
                print(f"[WARN] session_id missing → generated: {session_id}")

            # 履歴ファイルをロードする。
            directory_full_path = config.SESSIONS_DIR / session_id
            history = file_utils.load_history(directory_full_path)
            # 今回のユーザ発言を取得する
            messages = body.get("messages", [])
            last_user_message = string_utils.get_reversed_user_message(messages)
            # session_idの取得
            call_body = body.copy()
            call_body["session_id"] = session_id

            # yamlから各種プロンプト読み込み
            all_memories = file_utils.load_character_memories(session_id, config.SESSIONS_DIR)
            yui_memory = all_memories.get("白井 結")

            # 2) 事前キャラ同期
            #    SillyTavern 側で主人公カードが更新されていたら、session/world.yamlへ反映
            self._sync_character_if_changed(session_id, body)

            # 5) 関連キャラ同期 こっちはまだ必要な気はする。ただしキャラ説明から
            #    memory.yaml の world_relation を見て、会話に関係するキャラのカードを session 配下へ同期する
            #    SillyTavern 上のキャラ情報を次の発話に反映したいので、ここで毎回実行している
            #self._sync_related_characters_from_memory(session_id)
            character_name = "白井　結"
            system_message = file_utils.build_character_comment_system_message(
                session_id=session_id,
                character_name=character_name,
                sessions_dir=config.SESSIONS_DIR,
                prompt_file=Path("files/prompts/character_comment_prompt.yaml"),
            )

            # print("システムプロンプト：", system_message)

            # 6) 応答生成
            #    ここで LLM にチャットを投げる
            response_text = self._generate_response(session_id, messages, system_message)

            last_assistant_message = string_utils.get_reserved_assistant_message(messages)

            # 7) 履歴保存（未実装）
            #    ここで chat log を session 単位で保存する想定
            #    例: logs/chat_history.jsonl, latest_response.txt など
            history.append({"t": time.time(), "role": "user", "content": last_user_message})
            history.append({"t": time.time(), "role": "assistant", "content": response_text})
            file_utils.save_history(directory_full_path, history)

            # 8) 応答後の記憶更新（未実装）
            #    今回の response_text を使って progress や history を確定したい場合はここで再更新する
            #    例: self.memory_manager.update_memory(call_body, session_id, last_user_message, response_text)
            self.memory_manager.update_memory(
                body=call_body,
                session_id=session_id,
                character_name=character_name,
                last_user_content=last_user_message,
                last_assistant_content=response_text,
            )

            # 9) 新規キャラ追加（未実装）
            #    response_text や更新後 memory.yaml を見て、新しく world_relation に追加されたキャラを
            #    cards / yaml へ取り込む処理をここへ足す想定

            return {
                "response": {
                    "id": f"chatcmpl-{session_id[:8]}",
                    "object": "chat.completion",
                    "created": int(datetime.now().timestamp()),
                    "model": body.get("model", config.DEFAULT_MODEL),
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant"
                                    , "name": "白井　結"
                                    , "original_avatar": "白井　結.png"
                                    , "force_avatar": "白井　結.png"
                                    , "content": response_text},
                        "finish_reason": "stop",
                        "group_count": 0
                    }],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                },
                "status_code": 200
            }

        except Exception as e:
            print(f"[ERROR] handle_chat_completion: {e}")
            import traceback
            print(traceback.format_exc())
            return {"error": "Internal server error"}, 500

    def _sync_character_if_changed(self, session_id: str, body: Dict):
        print("sync character if changed start")
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

        print(f"[WORLD_RELATION] session_id={session_id} → {related_names}")

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
