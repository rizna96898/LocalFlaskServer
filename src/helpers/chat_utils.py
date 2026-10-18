from flask import jsonify
from typing import Dict
from uuid import uuid4
from services.memory.memory_manager import MemoryManager
from services.chat.chat_manager import ChatManager
from services.status import status_manager
from logger import log
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

    # 発言1回分。戻り値は、履歴に足す発言の並び [(発言者, 本文), ...]（返事と、あれば掛け合いの2行）
    # history: プレイヤーの発言まで入った会話ログ（書き換えない）
    def chat(self, session_id, body:Dict, message, cast, previous_message="", history=None) -> list:
        #session_id = body.get("session_id")

        #実行中に更新
        status_manager.mark_prepare_processing(
            session_id,
            complete_stage="main_chat",
        )

        # 1. 返事をする人を決める（誰に向けた発言かの判定）
        _, responder = self.chat_manager.main_chat(body, session_id, message, cast, previous_message)

        # 2. 返事を作る（材料の会話ログは、プレイヤーの発言の手前まで）
        log_before = list(history or [])[:-1]
        reply = self.chat_manager.reply(session_id, responder, cast["player"], message, log_before)
        lines = [(responder, reply)]

        # 3・4. 意識を確かめ、プレイヤー以外に向いていれば、掛け合いを1往復。
        # ここで失敗しても、返事までは返す（掛け合いは無しにする）
        try:
            log_now = list(history or []) + [self._as_log(responder, reply)]
            target = self.chat_manager.attention(session_id, responder, cast, log_now)

            if target and target["id"] not in (cast["player"]["id"], responder["id"]):
                opener = self.chat_manager.cross_talk(session_id, responder, target, log_now)
                answer = self.chat_manager.reply(session_id, target, responder, opener, log_now)
                lines += [(responder, opener), (target, answer)]
        except Exception as e:
            log.info(f"[CHAT] 意識の確認・掛け合いを飛ばしました: {type(e).__name__}: {e}")

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

        return lines

    # 会話ログの1行の形（プロンプトの「これまでの会話」に使う）
    @staticmethod
    def _as_log(person, message):
        return {"message": message, "icon_data": {"character_id": person["id"], "character_name": person["name"]}}


    # 前処理・後処理は事前且つ、個別に呼ぶことがあるのかがポイント
    # 呼ばないならここに無くて良い
    # 前処理。入り口
