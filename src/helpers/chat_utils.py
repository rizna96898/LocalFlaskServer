from flask import jsonify
from typing import Dict
from uuid import uuid4
from services.memory.memory_manager import MemoryManager
from services.chat.chat_manager import ChatManager
from services.status import status_manager
# Orchestratorの初期化

class ChatUtils:
    def __init__(self, memory_manager: MemoryManager, chat_manager: ChatManager):
        self.memory_manager: MemoryManager = memory_manager
        self.chat_manager: ChatManager = chat_manager

    # 新規セッション作成
    def create_new_session(self, body: Dict) -> str:

        # """新規チャット作成（/new_chat）"""
        session_id = body.get("session_id") or str(uuid4())

        # ニューチャット用ステータス作成
        status_manager.create_prepare_status(session_id)

        # 初期記憶の非同期作成
        return self.memory_manager.create_initial_memory(session_id)

    def chat(self, session_id, body:Dict, message) -> str:
        #session_id = body.get("session_id")

        #実行中に更新
        status_manager.mark_prepare_processing(
            session_id,
            complete_stage="main_chat",
        )

        message = self.chat_manager.main_chat(body, session_id, message)

        #待機中に更新
        status_manager.update_prepare_status(
            session_id,
            status="ready",
            complete_stage="main_chat",
            error_stage=None,
            error_message=None,
            needs_mob_chat=None,
            mob_count=None,
            next_speakers=None,
        )

        return message


    # 前処理・後処理は事前且つ、個別に呼ぶことがあるのかがポイント
    # 呼ばないならここに無くて良い
    # 前処理。入り口
