from flask import jsonify
from typing import Dict
from uuid import uuid4
from helpers import file_utils
from services.systems import system_settings_reload_service
from exception import exception_proc
from services.memory.memory_manager import MemoryManager
from services.status import status_manager
from helpers import response_checker
# Orchestratorの初期化

class ChatUtils:
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager: MemoryManager = memory_manager

    # 新規セッション作成
    def create_new_session(self, body: Dict) -> str:

        # """新規チャット作成（/new_chat）"""
        session_id = body.get("session_id") or str(uuid4())

        # ニューチャット用ステータス作成
        status_manager.create_prepare_status(session_id)

        # 初期記憶の非同期作成
        return self.memory_manager.create_initial_memory(session_id)

    # 前処理・後処理は事前且つ、個別に呼ぶことがあるのかがポイント
    # 呼ばないならここに無くて良い
    # 前処理。入り口
    def chat_prepare(self, payload):
        log.info("前処理のログ")

        try:
            # Yamlの設定に変更があれば読み直しておく
            system_settings_reload_service.SystemSettingsReloadCheckService()

            # デバッグログ（必要に応じて残す）
            # log.info("=== Request Headers ===")
            # for key, value in request.headers.items():
            #     log.info(f"{key}: {value}")
            # log.info("=====================")
            # log.info("body全量:", body)

            # 前処理します
            # TODO 1文字は恐らく判別出来ないから何もしない
            if len(payload.get("message")) > 1:
                result = {}
                result = self.chat_pretreatment(payload)
            return "", 200

        except Exception as e:
            log.info(f"[ERROR] /v1/chat/prepare: {e}")
            return jsonify({"error": "Internal server error"}), 500

    # 前処理
    def chat_pretreatment(self, body: Dict) -> Dict:
        log.info("[ORCH] chat_pretreatment start")

        session_id = body.get("session_id")

        try:
            log.info(f"[ORCH] session_id={session_id}")

            if not session_id:
                log.info("[ERROR] chat_pretreatment: session_id取得エラー")
                return {
                    "response": {
                        "error": "session_idが何らかの理由で取れなかったので新しいチャットを開始してください。"
                    },
                    "status_code": 503,
                }

            file_utils.mark_prepare_processing(session_id, "prepare")

            self.memory_manager.create_target_speakers(session_id, body)

            return response_checker.response_ok(body)

        except Exception as e:
            log.info(f"[ERROR] chat_pretreatment: {e}")
            import traceback
            log.info(traceback.format_exc())

            if session_id:
                file_utils.mark_prepare_error(
                    session_id,
                    complete_stage="prepare",
                    error_stage="prepare",
                    error_message=f"{type(e).__name__}: {e}",
                )

            return {"error": "Internal server error"}, 500

    # 後処理。入り口
    def chat_after(self, payload):
        log.info("後処理のログ")

        try:
            # Yamlの設定に変更があれば読み直しておく
            system_settings_reload_service.SystemSettingsReloadCheckService()

            allow_image = payload.headers.get("X-Allow-Image", "false").lower() == "true"
            session_id = payload.get("session_id")
            
            error_response = exception_proc._wait_chat_stage_or_response(
                session_id,
                "prepare",
                "prepare が error で終了しました。prepare_status.yaml を確認してください。",
            )
            if error_response:
                return error_response

            return self.chat_post_processing(payload), 200

        except Exception as e:
            log.info(f"[ERROR] /v1/chat/after: {e}")
            error_response
            return exception_proc.error_response("Internal server error", 500), 500

    # 後処理
    def chat_post_processing(self, body: Dict) -> Dict:
        log.info("[ORCH] chat_post_processing start")

        session_id = body.get("session_id")

        try:
            # ファイルステータスを更新
            file_utils.mark_prepare_processing(session_id, "after")

            # TODO:
            # world_memory 更新
            # self.memory_manager._run_memory_async(body, session_id, "update")
            # character_memory 更新
            # パラメーター 更新
            # イラストタグ？

            # ファイルステータスを更新
            file_utils.mark_prepare_ready(session_id, "after")

            return response_checker.response_ok(None)

        except Exception as e:
            log.info(f"[ERROR] chat_post_processing: {e}")
            if session_id:
                file_utils.mark_prepare_error(
                    session_id,
                    complete_stage="after",
                    error_stage="after",
                    error_message=f"{type(e).__name__}: {e}",
                )
            return exception_proc.error_response("Internal server error", 500), 500