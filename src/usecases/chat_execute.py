import yaml
from uuid import uuid4
import time
import shutil
from typing import Dict, Any, Iterable
from datetime import datetime
from flask import jsonify
from config import config
from shutil import copy2
from helpers import file_utils
from pathlib import Path
from exception import exception_proc
from helpers import string_utils
from helpers import data_utils
from services.llm import llm_service
from constant import (
    Bootstrap,
    PromptsPreprocess,
    PromptsMain,
    PromptsPostprocess,
)
from helpers import response_checker
from helpers.chat_utils import ChatUtils
from services.memory.memory_manager import MemoryManager
from services.status import status_manager
from usecases import chat_execute
import os
import sys

class ChatExecute:
    def __init__(self):
        self.model_handling_service = None
        self.memory_manager = MemoryManager()
        self.chat_utils = ChatUtils(self.memory_manager)

    def load_session_list(self, payload):

        try:
            world_id = payload.get("world_id")

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

    def world_start(self, payload):
        try:

            world_id = payload.get("world_id")
            world_name = payload.get("world_name")

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

    def delete_session(self, payload):
        session_ids = payload.get("session_ids")

        deleted_session_ids = []
        failed_session_ids = []

        for session_id in session_ids:
            try:

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
                    deleted_session_ids.append(session_id)

            except Exception as error:
                print(f"セッション削除失敗: {session_id}")
                print(error)

                failed_session_ids.append(session_id)

        return jsonify({
            "status": "ok",
            "deleted_session_ids": deleted_session_ids,
            "failed_session_ids": failed_session_ids
        }), 200

    def selected_session(self, payload):

        session_id = payload.get("session_id")
        session_dir = config.SESSIONS_DIR / session_id
        historyList = file_utils.load_history(session_dir)
        history = {}

        makeHistoryList = []
        page = len(historyList) // 10
        if page > 0:
            for i in range(page):
                message = str(i + 1)
                icon_data = {"character_id": "system",
                            "character_name": "システム"}
                history = {
                    "line_id": message,
                    "message": message,
                    "icon_data": icon_data
                }

                makeHistoryList.append(history)

        startNo = page * 10
        endNo = min(startNo + 10, len(historyList))

        for i in range(startNo, endNo):
            history = {
                "line_id": str(i + 1),
                "message": historyList[i]["message"],
                "icon_data": historyList[i]["icon_data"]
            }
            makeHistoryList.append(history)

        return jsonify({
            "status": "ok",
            "session_id": payload.get("session_id"),
            "message_list": makeHistoryList
        }), 200

    def selected_message(self, payload):
        session_id = payload.get("session_id")
        print("session_id", session_id, flush=True)
        line_Id = int(payload.get("line_id"))
        print("line_Id", line_Id, flush=True)

        # メッセージ取得基準値
        min_no = (line_Id - 1) * 10
        max_no = line_Id * 10
        message_list = []

        session_dir = config.SESSIONS_DIR / session_id
        historyList = file_utils.load_history(session_dir)

        for i in range(min_no, max_no):
            print("内容", historyList[i], flush=True)
            index = str(i + 1)
            message_obj = {}
            message_obj["message"] = historyList[i]["message"]
            message_obj["line_id"] = index
            message_obj["icon_data"] =  historyList[i]["icon_data"]
            message_list.append(message_obj)

        return jsonify({
            "status": "ok",
            "session_id": payload.get("session_id"),
            "message_list": message_list
        }), 200

    def chat_startup(self, payload):
        # """新規チャット作成（/new_chat）"""
        session_id = str(uuid4())
        world_id = payload.get("world_id")
        copy_source_dir = payload.get("base_path")

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

    # ニューチャットの入り口
    def new_chat(self, payload):
        print("ニューチャット開始")

        try:
            start_message = self.chat_utils.create_new_session(payload)

            session_id = payload.get("session_id")
            session_dir = config.SESSIONS_DIR / session_id
            history = file_utils.load_history(session_dir)

            icon_data = {
                "character_id": "shirai_yui",
                "character_name": "白井　結"
            }

            string_utils.history_append(
                history,
                "shirai_yui",
                "main",
                "1",
                start_message,
                icon_data
            )

            file_utils.save_history(session_dir, history)

            print("ニューチャット終了")
            return response_checker.chat_response_ok(
                payload,
                "1",
                start_message,
                icon_data
            ), 200
        except Exception as e:
            print(f"[ERROR] /new_chat: {e}")
            return exception_proc.error_response(str(e), 500)

    # 多分トータルのチャットハンドラーが必要になる（と思ってる）

    # チャット処理。入り口
    def chat(self, payload):
        os.write(1, b"=== FD1 stdout test ===\n")
        os.write(2, b"=== FD2 stderr test ===\n")

        sys.stdout.write("=== sys.stdout.write test ===\n")
        sys.stdout.flush()

        sys.stderr.write("=== sys.stderr.write test ===\n")
        sys.stderr.flush()

        print("=== print stdout test ===", flush=True)
        print("=== print stderr test ===", file=sys.stderr, flush=True)
        print("=== /session_start 到達 ===", flush=True)
        print("チャット開始")
        try:
            # start_message = orchestrator.create_new_session(body)

            session_id = payload.get("session_id")
            session_dir = config.SESSIONS_DIR / session_id
            history = file_utils.load_history(session_dir)

            message = payload.get("message")
            icon_data = {"character_id": "player",
                        "character_name": "プレイヤー"}
            
            string_utils.history_append(history, "player", "player", "1", message, icon_data)

            message = "モデルを使わないテスト返却。チャットボタン",
            icon_data = {"character_id": "shirai_yui",
                        "character_name": "白井　結"}
            
            string_utils.history_append(history, "shirai_yui", "main", "1", message, icon_data)

            file_utils.save_history(session_dir, history)

            print("チャット終了")
            # print("body全量", body)
            return response_checker.chat_response_ok(payload, "1", message, icon_data), 200

        except Exception as e:
            print(f"[ERROR] /chat: {e}")
            return jsonify({"error": str(e)}), 500

    # 多分要らないのでコメントアウト。上の入り口に移植
    # def chat_completions():
    #     if request.method == "OPTIONS":
    #         return "", 200

    #     try:
    #         # Yamlの設定に変更があれば読み直しておく
    #         system_settings_reload_service.SystemSettingsReloadCheckService()

    #         body = request.get_json(force=True)
    #         allow_image = request.headers.get("X-Allow-Image", "false").lower() == "true"
    #         session_id = body.get("session_id")

    #         result = {}

    #         if body.get("first_flag") == "first":
    #             print("１回目のログ")

    #             error_response = _wait_chat_stage_or_response(
    #                 session_id,
    #                 "prepare",
    #                 "prepare が error で終了しました。prepare_status.yaml を確認してください。",
    #             )
    #             if error_response:
    #                 return error_response

    #             result = orchestrator.handle_chat_completion(body, allow_image)

    #         else:
    #             print("２回目のログ")

    #             error_response = _wait_chat_stage_or_response(
    #                 session_id,
    #                 "main_chat",
    #                 "main_chat が error で終了しました。prepare_status.yaml を確認してください。",
    #             )
    #             if error_response:
    #                 return error_response

    #             result = orchestrator.handle_mob_chat_completion(body, allow_image)

    #         return jsonify(result["response"]), result.get("status_code", 200)

    #     except Exception as e:
    #         print(f"[ERROR] /v1/chat/completions: {e}")
    #         import traceback
    #         print(traceback.format_exc())
    #         return jsonify({"error": "Internal server error"}), 500

    # 再送。入り口
    def re_chat(self, payload):
        print("再送開始")

        try:            
            session_id = payload.get("session_id")
            session_dir = config.SESSIONS_DIR / session_id
            history = file_utils.load_history(session_dir)
            message = payload.get("message")
            icon_data = {"character_id": "player",
                        "character_name": "プレイヤー"}
            
            string_utils.history_append(history, "player", "player", "1", message, icon_data)

            message = "モデルを使わないテスト返却。再送ボタン"
            icon_data = {"character_id": "shirai_yui",
                        "character_name": "白井　結"}
            
            string_utils.history_append(history, "player", "player", "1", message, icon_data)

            file_utils.save_history(session_dir, history)

            print("再送終了")
            # print("body全量", body)
            return response_checker.chat_response_ok(payload, "1", message, icon_data), 200

        except Exception as e:
            print(f"[ERROR] /chat: {e}")
            return jsonify({"error": str(e)}), 500

    # メインプレイヤーチャット（予定）
    def handle_chat_completion(self, body: Dict, allow_image: bool = False) -> Dict:
        session_id = body.get("session_id")

        try:
            if not session_id:
                return exception_proc.error_response("session_idがありません。", 503)

            file_utils.mark_prepare_processing(session_id, "main_chat")

            context = self._load_main_chat_context(session_id, body)

            # キャラクター返信作成
            response_text = self._generate_response(
                session_id=session_id,
                messages=context["messages"],
                system_prompt=context["system_message"],
            )

            # 次の話者確定（ここはもう少し工夫がいるはず）
            target_speakers = self._judge_reply_target_speakers(
                world_data=context["world_data"],
                messages=context["messages"],
                response_text=response_text,
            )

            needs_mob_chat = len(target_speakers) > 0
            mob_count = len(target_speakers)

            # 履歴作成
            self._append_chat_history(
                session_id=session_id,
                speaker_name=context["character_full_name"],
                user_message=context["last_user_message"],
                assistant_message=response_text,
            )

            # 返信情報作成
            display_text = self._build_display_text(
                world_time=context["world_time"],
                response_text=response_text,
                character_memory_data=context["character_memory_data"],
            )

            # 画面返信情報作成
            result = self._build_chat_completion_response(
                session_id=session_id,
                body=body,
                character_name=context["character_full_name"],
                content=display_text,
                next_speakers=target_speakers,
                needs_mob_chat=needs_mob_chat,
                mob_count=mob_count,
            )

            # prepare_status.yaml更新
            status_manager.update_prepare_status(
                session_id,
                status="ready",
                complete_stage="main_chat",
                error_stage=None,
                error_message=None,
                needs_mob_chat=needs_mob_chat,
                mob_count=mob_count,
                next_speakers=target_speakers,
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

            return exception_proc.error_response("Internal server error", 500)
        
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

    # キャラクター情報用意
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
        if data_utils.has_changes(current, new_data):
            # print("has_changes start")
            updated = data_utils.merge_character_data(current, new_data)
            success = file_utils.save_yaml_file(character_file, updated)
            if success:
                print(f"[CHARACTER] Updated for session {session_id}")
            else:
                print(f"[WARN] Failed to update character.yaml for {session_id}")
        print("_sync_character_if_changed end")

    # 最終応答作成
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
            response_text = llm_service.openrouter.send_message(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=system_prompt,
                temperature=config.TEMPERATURE,
                max_tokens=config.MAX_TOKENS
            )
            return response_text

        except Exception as e:
            print(f"[ERROR] _generate_response: {e}")
            return "すみません、今ちょっと調子が悪いみたいです…"

    # 発言対象確定
    def _judge_reply_target_speakers(self, world_data: Dict, messages: list, response_text: str) -> list[str]:
        
        prompt_data = file_utils.load_yaml_file(
            config.MAIN / PromptsMain.CHARACTER_IDENTIFICATION
        ) or {}

        player_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                player_message = msg.get("content", "")
                break

        participants = world_data.get("current_state", {}).get("participants", [])
        characters_text = string_utils.build_characters_text(participants)

        system_prompt = prompt_data["system"]
        template_prompt = prompt_data["template"]
        template_prompt = template_prompt.replace("{characters}", characters_text)
        template_prompt = template_prompt.replace("{player_message}", player_message)
        template_prompt = template_prompt.replace("{player_answer}", response_text)

        print("置換後プロンプト全文", template_prompt)
        # model_handling_service = ModelHandlingService("openrouter")
        result = llm_service.get_model_handling_service.send_message(
            messages=[{"role": "user", "content": template_prompt}],
            system_prompt=system_prompt,
        )

        parsed = yaml.safe_load(string_utils.strip_code_block(result)) or {}
        target_speakers = parsed.get("target_speakers") or []

        if isinstance(target_speakers, str):
            target_speakers = [target_speakers]

        print("今回の発話対象：", target_speakers)
        return target_speakers

    # 関数名からメインチャットを作ってるのはわかるけど、処理の流れが良く判んない
    def _load_main_chat_context(self, session_id: str, body: Dict) -> Dict:
        session_dir = config.SESSIONS_DIR / session_id
        char_dir = session_dir / "character"

        messages = body.get("messages", [])
        last_user_message = string_utils.get_reversed_user_message(messages)

        world_file = session_dir / "world_memory.yaml"
        world_data = file_utils.load_yaml_file(world_file) or {}

        player_name = world_data.get("player_name")
        print("プレイヤー名：", player_name)

        player_path = file_utils.find_character_file(player_name, char_dir)
        player_data = file_utils.load_yaml_file(player_path) or {}

        character_name = player_data.get("last_target")
        print("誰向けの発言か", character_name)

        world_time = file_utils.get_world_time(world_data)

        system_message = file_utils.build_character_comment_system_message(
            session_id=session_id,
            character_name=character_name,
            sessions_dir=config.SESSIONS_DIR,
            prompt_file=config.MAIN / PromptsMain.CHAT
        )

        character_path = file_utils.find_character_file(character_name, char_dir)
        character_data = file_utils.load_yaml_file(character_path) or {}
        character_full_name = character_data.get("name", character_name)

        memory_path = file_utils.find_character_memory_file(character_full_name, char_dir)
        print("load target", memory_path)

        character_memory_data = file_utils.load_yaml_file(memory_path) or {}

        return {
            "messages": messages,
            "last_user_message": last_user_message,
            "world_data": world_data,
            "world_time": world_time,
            "system_message": system_message,
            "character_full_name": character_full_name,
            "character_memory_data": character_memory_data,
        }

    # 履歴作ってる
    # 多分不要になる（トップでモック作った）
    def _append_chat_history(self, 
        session_id: str,
        speaker_name: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        session_dir = config.SESSIONS_DIR / session_id
        history = file_utils.load_history(session_dir)

        history.append({
            "t": time.time(),
            "speaker": "player",
            "role": "user",
            "content": user_message,
        })

        history.append({
            "t": time.time(),
            "speaker": speaker_name,
            "role": "assistant",
            "content": assistant_message,
        })

        file_utils.save_history(session_dir, history)

    # チャット送信用
    # 必要だけどここに必要じゃない
    def _build_display_text(self, 
        world_time: str,
        response_text: str,
        character_memory_data: Dict,
    ) -> str:
        display_parts = []

        if world_time:
            display_parts.append(f"（{world_time}）")

        display_parts.append(response_text)

        parameter_lines = _build_parameter_lines(character_memory_data)
        if parameter_lines:
            display_parts.append("\n".join(parameter_lines))

        return "\n".join(display_parts)

    # 返信のオブジェクト作ってるけど
    # 正直必要なのかわからん
    def _build_chat_completion_response(self, 
        session_id: str,
        body: Dict,
        character_name: str,
        content: str,
        next_speakers: list[str],
        needs_mob_chat: bool,
        mob_count: int,
    ) -> Dict:
        return {
            "response": {
                "id": f"chatcmpl-{session_id[:8]}",
                "object": "chat.completion",
                "created": int(datetime.now().timestamp()),
                "model": body.get("model", config.DEFAULT_MODEL),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "name": character_name,
                        "original_avatar": character_name + ".png",
                        "force_avatar": character_name + ".png",
                        "content": content,
                    },
                    "finish_reason": "stop",
                    "target_speakers": next_speakers,
                    "remaining_speakers": next_speakers,
                    "needs_mob_chat": needs_mob_chat,
                    "mob_count": mob_count,
                }],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            },
            "status_code": 200,
        }

    # キャラメモリをパラメータとして作ってる？
    # 必要そうではあるけどここにあるべきではなさそう
    def _build_parameter_lines(self, character_memory_data: Dict) -> list[str]:
        result = []

        parameter_list = character_memory_data.get("parameter", [])
        if not isinstance(parameter_list, list):
            return result

        for item in parameter_list:
            if not isinstance(item, dict):
                continue

            display_name = str(item.get("display_name", "")).strip()
            count = item.get("count", 0)

            if display_name:
                result.append(f"{display_name}：{count}")

        return result
