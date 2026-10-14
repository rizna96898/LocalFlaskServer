import re
import yaml
from flask import send_file
from uuid import uuid4
import time
import shutil
from typing import Dict, Any, Iterable
from datetime import datetime
from config import config
from shutil import copy2
from helpers import file_utils
from pathlib import Path
from exception import exception_proc
from helpers import string_utils
from constant import (
    Bootstrap,
    PromptsPreprocess,
    PromptsMain,
    PromptsPostprocess,
)
from helpers import response_checker
from helpers.chat_utils import ChatUtils
from services.memory.memory_manager import MemoryManager
from services.chat.chat_manager import ChatManager
from usecases import chat_execute
import os
import sys
from logger import log

class ChatExecute:
    def __init__(self):
        self.model_handling_service = None
        self.memory_manager = MemoryManager()
        self.chat_manager = ChatManager()
        self.chat_utils = ChatUtils(self.memory_manager, self.chat_manager)

    def load_session_list(self, payload):

        try:
            world_id = payload.get("world_id")

            if not world_id:
                return response_checker.response_error("world_id がありません", 400)

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

            return response_checker.response_ok(sessions=world_sessions)
        except Exception as e:
            return response_checker.response_error(str(e), 500)

    def world_start(self, payload):
        try:

            world_id = payload.get("world_id")
            world_name = payload.get("world_name")

            if not world_id:
                return response_checker.response_error("world_id がありません", 400)

            if not world_name:
                return response_checker.response_error("world_name がありません", 400)

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

            return response_checker.response_ok(
                world_id=world_id,
                world_name=world_name,
                sessions=world_sessions,
            )

        except Exception as e:
            return response_checker.response_error(str(e), 500)

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
                    return response_checker.response_ok(session_id=session_id)

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
                log.info(f"セッション削除失敗: {session_id}")
                log.info(error)

                failed_session_ids.append(session_id)

        return response_checker.response_ok(
            deleted_session_ids=deleted_session_ids,
            failed_session_ids=failed_session_ids,
        )

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

        return response_checker.response_ok(
            session_id=payload.get("session_id"),
            message_list=makeHistoryList,
        )

    def selected_message(self, payload):
        session_id = payload.get("session_id")
        log.info("session_id", session_id)
        line_Id = int(payload.get("line_id"))
        log.info("line_Id", line_Id)

        # メッセージ取得基準値
        min_no = (line_Id - 1) * 10
        max_no = line_Id * 10
        message_list = []

        session_dir = config.SESSIONS_DIR / session_id
        historyList = file_utils.load_history(session_dir)

        for i in range(min_no, max_no):
            log.info("内容", historyList[i])
            index = str(i + 1)
            message_obj = {}
            message_obj["message"] = historyList[i]["message"]
            message_obj["line_id"] = index
            message_obj["icon_data"] =  historyList[i]["icon_data"]
            message_list.append(message_obj)

        return response_checker.response_ok(
            session_id=payload.get("session_id"),
            message_list=message_list,
        )

    # チャット画面用の画像を返却する。
    # chat_startup でセッションフォルダの picture/ に退避したものを読むので、
    # 後からキャラクター画面で画像を変えても、進行中のチャットには影響しない。
    def load_session_image(self, session_id, image_type, character_id):

        # どちらもそのままパスの一部になるので、文字種を限定する
        if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id or ""):
            return response_checker.response_error("session_id が不正です", 400)

        if not re.fullmatch(r"[A-Za-z0-9_]+", character_id or ""):
            return response_checker.response_error("character_id が不正です", 400)

        picture_dir = config.SESSIONS_DIR / session_id / "picture"

        if image_type == "icon":
            image_path = picture_dir / "icon" / f"{character_id}.png"

        elif image_type == "standing":
            image_path = picture_dir / "standing" / f"{character_id}_standing.png"

        else:
            return response_checker.response_error("image_type が不正です", 400)

        if not image_path.exists():
            return response_checker.response_error("画像が存在しません", 404)

        return send_file(image_path)

    def chat_startup(self, payload):
        # """新規チャット作成（/new_chat）"""
        session_id = str(uuid4())
        world_id = payload.get("world_id")
        copy_source_dir = payload.get("base_chat_path")

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
                log.info("プレイヤー用")
                src = copy_source_players_dir / f"{character_id}_setting.yaml"
                copy2(src, copy_dst_char_dir)
            
            if characters_info.get("参照種別") == "character":
                log.info("メインキャラ用")
                src = copy_source_character_dir / f"{character_id}_setting.yaml"
                src_ico = copy_source_character_ico_dir / f"{character_id}" / f"{character_id}.png"
                src_sta = copy_source_character_sta_dir / f"{character_id}" / f"{character_id}_standing.png"

                copy2(src, copy_dst_char_dir)
                copy2(src_ico, copy_dst_ico_dir)
                copy2(src_sta, copy_dst_sta_dir)
            
            if characters_info.get("参照種別") == "inline":
                log.info("その他作成する必要あり")
                #templateを一旦コピー
                copy2(
                    copy_source_temp_file_path,
                    copy_dst_char_dir / f"{character_id}_setting.yaml"
                )
                #コピー先のテンプレートを読み込む
                sub_char_yaml = file_utils.load_yaml_file(copy_dst_char_dir / f"{character_id}_setting.yaml")

                #読み込んだテンプレートのIDと名前を変更
                sub_display_name = characters_info.get("表示名")
                rubi = None
                sub_character_id = characters_info.get("参照ID")
                sub_char_yaml["名前"]["表示名"] = sub_display_name
                sub_char_yaml["名前"]["ふりがな"] = rubi
                sub_char_yaml["名前"]["識別子"] = sub_character_id
                #保存
                file_utils.save_yaml_file(copy_dst_char_dir / f"{character_id}_setting.yaml", sub_char_yaml)
            log.info("その他作成する必要なし")
        
        #sessions_listの最終行へ追記
        sessions_list_path = config.SYSTEM_DIR / "sessions_list.yaml"

        # sessions_list.yaml 読み込み
        if sessions_list_path.exists():
            with sessions_list_path.open("r", encoding="utf-8") as f:
                sessions_data = yaml.safe_load(f) or {}
        else:
            sessions_data = {}

        sessions = sessions_data.get("sessions")
        if not isinstance(sessions, list):
            sessions = []

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

        sessions_list_path.parent.mkdir(parents=True, exist_ok=True)
        with sessions_list_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                sessions_data,
                f,
                allow_unicode=True,
                sort_keys=False
            )
            
        log.info("初期ファイル用意完了", copy_dst_dir.as_uri())
        return response_checker.response_ok(
            session_id=session_id,
            world_id=world_id,
            world_name=world_name,
            display_name=display_name,
        )

    # ニューチャットの入り口
    def new_chat(self, payload):
        log.info("ニューチャット開始")

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

            log.info("ニューチャット終了")
            return response_checker.chat_response_ok(
                payload,
                "1",
                start_message,
                icon_data
            ), 200
        except Exception as e:
            log.info(f"[ERROR] /new_chat: {e}")
            return exception_proc.error_response(str(e), 500)

    # 多分トータルのチャットハンドラーが必要になる（と思ってる）

    # チャット処理。入り口
    def chat(self, payload):

        log.info("chat chat_execute.py")
        log.info("チャット開始")

        try:
            # start_message = orchestrator.create_new_session(body)

            session_id = payload.get("session_id")
            session_dir = config.SESSIONS_DIR / session_id
            history = file_utils.load_history(session_dir)

            message = payload.get("message")
            icon_data = {"character_id": "player",
                        "character_name": "プレイヤー"}
            
            string_utils.history_append(history, "player", "player", "1", message, icon_data)

            message = self.chat_utils.chat(session_id, payload, message)

            icon_data = {"character_id": "shirai_yui",
                        "character_name": "白井　結"}
            
            string_utils.history_append(history, "shirai_yui", "main", "1", message, icon_data)

            file_utils.save_history(session_dir, history)

            log.info("チャット終了")
            # log.info("body全量", body)
            return response_checker.chat_response_ok(payload, "1", message, icon_data), 200

        except Exception as e:
            log.info(f"[ERROR] /chat: {e}")
            return response_checker.response_error(str(e), 500)

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
    #             log.info("１回目のログ")

    #             error_response = _wait_chat_stage_or_response(
    #                 session_id,
    #                 "prepare",
    #                 "prepare が error で終了しました。prepare_status.yaml を確認してください。",
    #             )
    #             if error_response:
    #                 return error_response

    #             result = orchestrator.handle_chat_completion(body, allow_image)

    #         else:
    #             log.info("２回目のログ")

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
    #         log.info(f"[ERROR] /v1/chat/completions: {e}")
    #         import traceback
    #         log.info(traceback.format_exc())
    #         return jsonify({"error": "Internal server error"}), 500

    # 再送。入り口
    def re_chat(self, payload):
        log.info("再送開始")

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

            log.info("再送終了")
            # log.info("body全量", body)
            return response_checker.chat_response_ok(payload, "1", message, icon_data), 200

        except Exception as e:
            log.info(f"[ERROR] /chat: {e}")
            return response_checker.response_error(str(e), 500)
