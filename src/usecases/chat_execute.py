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
from services.status import status_manager
from helpers.chat_utils import ChatUtils
from helpers import session_cast
from services.memory.memory_manager import MemoryManager
from services.chat.chat_manager import ChatManager
import os
import sys
from logger import log

class ChatExecute:
    def __init__(self):
        self.model_handling_service = None
        self.memory_manager = MemoryManager()
        self.chat_manager = ChatManager()
        self.chat_utils = ChatUtils(self.memory_manager, self.chat_manager)

    # 世界に属するセッションの一覧（sessions_list.yaml から、その世界の分だけ取り出す）
    def _world_sessions(self, world_id: str) -> list:
        sessions_list_path = config.SYSTEM_DIR / "sessions_list.yaml"

        if sessions_list_path.exists():
            with sessions_list_path.open("r", encoding="utf-8") as f:
                sessions_data = yaml.safe_load(f) or {}
        else:
            sessions_data = {}

        sessions = sessions_data.get("sessions")
        if not isinstance(sessions, list):
            sessions = []

        return [
            session for session in sessions
            if session.get("world_id") == world_id
        ]

    # セッション一覧の更新日時を、今にする。書いた日時を返す（一覧に無ければ空文字）
    def _touch_session(self, session_id: str) -> str:
        sessions_list_path = config.SYSTEM_DIR / "sessions_list.yaml"
        sessions_data = file_utils.load_yaml_file(sessions_list_path) or {}
        sessions = sessions_data.get("sessions")
        if not isinstance(sessions, list):
            return ""

        now_text = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        for session in sessions:
            if isinstance(session, dict) and session.get("session_id") == session_id:
                session["updated_at"] = now_text
                file_utils.save_yaml_file(sessions_list_path, sessions_data)
                return now_text
        return ""

    # セッション一覧の読み込み（画面を開いたときなど）
    def load_session_list(self, payload):

        try:
            world_id = payload.get("world_id")

            if not world_id:
                return response_checker.response_error("world_id がありません", 400)

            world_sessions = self._world_sessions(world_id)

            return response_checker.response_ok(sessions=world_sessions)
        except Exception as e:
            return response_checker.response_error(str(e), 500)

    # 世界の開始（世界を選んだときの入口）。/load_session_list とは別物として残す。
    # 今はその世界のセッション一覧を添えて返すだけ。世界を選んだときにサーバーで準備することができたら、ここに入れる
    def world_start(self, payload):
        try:

            world_id = payload.get("world_id")
            world_name = payload.get("world_name")

            if not world_id:
                return response_checker.response_error("world_id がありません", 400)

            if not world_name:
                return response_checker.response_error("world_name がありません", 400)

            world_sessions = self._world_sessions(world_id)

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

                # 記憶生成の途中結果（temp/{キャラクター}_{セッションID}_middle*.yaml）も消す
                for temp_file in config.TEMP_DIR.glob(f"*_{session_id}_*"):
                    temp_file.unlink(missing_ok=True)

                # モデルへの問い合わせの記録（logs/{セッションID}/）も消す
                session_logs = log.session_log_dir(session_id)
                if session_id and session_logs.is_dir():
                    shutil.rmtree(session_logs)

            except Exception as error:
                log.info(f"セッション削除失敗: {session_id}")
                log.info(error)

                failed_session_ids.append(session_id)

        return response_checker.response_ok(
            deleted_session_ids=deleted_session_ids,
            failed_session_ids=failed_session_ids,
        )

    # セッションの進行状態を返す。画面は、初期記憶を作っている間これを繰り返し問い合わせ、
    # 発言系のボタンを止めたり、プログレスバーを出したりする
    def session_status(self, payload):
        session_id = (payload or {}).get("session_id") or ""

        if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
            return response_checker.response_error("session_id が不正です", 400)

        status_path = status_manager.get_prepare_status_path(session_id)
        if not status_path.exists():
            return response_checker.response_error("セッションの状態がありません", 404)

        data = file_utils.load_yaml_file(status_path) or {}

        return response_checker.response_ok(
            session_id=session_id,
            status=data.get("status"),
            complete_stage=data.get("complete_stage"),
            error_stage=data.get("error_stage"),
            error_message=data.get("error_message"),
            progress={
                "done": data.get("progress_done") or 0,
                "total": data.get("progress_total") or 0,
                "label": data.get("progress_label") or "",
            },
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
                    "icon_data": icon_data,
                    "role": "system",
                }

                makeHistoryList.append(history)

        startNo = page * 10
        endNo = min(startNo + 10, len(historyList))

        for i in range(startNo, endNo):
            history = {
                "line_id": str(i + 1),
                "message": historyList[i]["message"],
                "icon_data": historyList[i]["icon_data"],
                "role": historyList[i].get("role"),
            }
            makeHistoryList.append(history)

        return response_checker.response_ok(
            session_id=payload.get("session_id"),
            message_list=makeHistoryList,
            player=session_cast.icon_data(session_cast.load_cast(session_id)["player"]),
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
            message_obj["role"] = historyList[i].get("role")
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

    # アイコンと立ち絵を、あればセッションへ退避する。無くてもチャットは始められる
    # （チャット画面は、画像が無ければ名前の頭文字を出す）
    def _copy_images_if_exist(self, owner_dir: Path, owner_id: str, dst_icon_dir: Path, dst_standing_dir: Path):
        for src, dst_dir in (
            (owner_dir / "icon" / owner_id / f"{owner_id}.png", dst_icon_dir),
            (owner_dir / "standing" / owner_id / f"{owner_id}_standing.png", dst_standing_dir),
        ):
            if src.is_file():
                copy2(src, dst_dir)
            else:
                log.info(f"画像が無いので退避しない: {src}")

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
                self._copy_images_if_exist(Path(copy_source_dir) / "players", character_id, copy_dst_ico_dir, copy_dst_sta_dir)

            if characters_info.get("参照種別") == "character":
                log.info("メインキャラ用")
                src = copy_source_character_dir / f"{character_id}_setting.yaml"
                copy2(src, copy_dst_char_dir)
                self._copy_images_if_exist(Path(copy_source_dir) / "characters", character_id, copy_dst_ico_dir, copy_dst_sta_dir)
            
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
            created_at=now_text,
            updated_at=now_text,
        )

    # ニューチャットの入り口
    def new_chat(self, payload):
        log.info("ニューチャット開始")

        try:
            # セッションは /chat_startup で作ってあるはず。無ければ何も作らずに断る（中身の無いフォルダを作らない）
            session_id = (payload or {}).get("session_id") or ""
            if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
                return response_checker.response_error("session_id が不正です", 400)
            if not (config.SESSIONS_DIR / session_id).is_dir():
                return response_checker.response_error("セッションがありません。新規チャットを押し直してください", 404)

            start_message = self.chat_utils.create_new_session(payload)

            session_id = payload.get("session_id")
            session_dir = config.SESSIONS_DIR / session_id
            history = file_utils.load_history(session_dir)

            # 開始メッセージの発言者は、最初のメインキャラクター
            cast = session_cast.load_cast(session_id)
            speaker = session_cast.first_main(cast)
            icon_data = session_cast.icon_data(speaker)

            line_id = string_utils.history_append(
                history,
                speaker["id"],
                "main",
                start_message,
                icon_data
            )

            file_utils.save_history(session_dir, history)

            log.info("ニューチャット終了")
            return response_checker.response_ok(
                session_id=session_id,
                line_id=line_id,
                message=start_message,
                icon_data=icon_data,
                player=session_cast.icon_data(cast["player"]),
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
            log.set_session(session_id)
            session_dir = config.SESSIONS_DIR / session_id
            history = file_utils.load_history(session_dir)

            message = payload.get("message")
            # 返事をする人・意識・掛け合いの候補は、その場にいる人だけ（プレイヤーは常にいる）
            cast = session_cast.present_cast(session_id)
            player = cast["player"]

            # 直前の発言（判定の材料）。プレイヤーの発言を足す前に取る
            previous_message = history[-1].get("message", "") if history else ""

            player_line_id = string_utils.history_append(history, player["id"], "player", message, session_cast.icon_data(player))

            lines = self.chat_utils.chat(session_id, payload, message, cast, previous_message, history)

            # 返事と掛け合いを、この順で履歴に足す。画面にはまとめて返す
            messages = []
            for speaker, text in lines:
                speaker_icon = session_cast.icon_data(speaker)
                speaker_line_id = string_utils.history_append(history, speaker["id"], "main", text, speaker_icon)
                messages.append({"line_id": speaker_line_id, "message": text, "icon_data": speaker_icon, "role": "main"})

            # 1件目（プレイヤーへの返事）は、今までどおり line_id・message・icon_data でも返す
            line_id = messages[0]["line_id"]
            message = messages[0]["message"]
            icon_data = messages[0]["icon_data"]

            file_utils.save_history(session_dir, history)

            # セッション一覧の「更新」日時を、今にする
            updated_at = self._touch_session(session_id)

            # 裏で、記憶の更新と画像作成を始める（今回の会話 = プレイヤーの発言から最後まで）
            self.chat_utils.after_chat(session_id, cast, history[int(player_line_id) - 1:])

            log.info("チャット終了")
            # log.info("body全量", body)
            return response_checker.response_ok(
                session_id=session_id,
                line_id=line_id,
                message=message,
                icon_data=icon_data,
                player_line_id=player_line_id,
                messages=messages,
                updated_at=updated_at,
            ), 200

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
