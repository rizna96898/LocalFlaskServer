from flask import jsonify
from typing import Dict
from uuid import uuid4
from services.memory.memory_manager import MemoryManager
from services.chat.chat_manager import ChatManager
from services.status import status_manager
from services.image import image_generation
from helpers import session_cast
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

    # 発言1回分。戻り値は、履歴に足す発言の並び [(発言者, 本文), ...]（返事と、あれば相談か掛け合いの行）
    # history: プレイヤーの発言まで入った会話ログ（書き換えない）
    def chat(self, session_id, body:Dict, message, cast, previous_message="", history=None) -> list:
        #session_id = body.get("session_id")

        #実行中に更新
        status_manager.mark_prepare_processing(
            session_id,
            complete_stage="main_chat",
        )

        # 1. 返事をする人を決める。まず、名前で呼ばれた人を探す（モデルが名前を抜き出し、だれに当たるかはプログラムで照らし合わせる）。
        # ここで失敗したら、名前で呼ばれた人はいない扱いにする
        log_before = list(history or [])[:-1]
        try:
            called = self.chat_manager.called_responders(session_id, cast, message)
        except Exception as e:
            log.info(f"[CHAT] 呼ばれた名前の確認を飛ばしました: {type(e).__name__}: {e}")
            called = []

        # 2人以上が名前で呼ばれたら、呼ばれた順にそれぞれが返事をする（相談・意識の確認・掛け合いはしない）。
        # あとの人の材料には、プレイヤーの発言と、先の人の返事まで入れる
        if len(called) >= 2:
            lines = []
            for no, person in enumerate(called):
                log_for = log_before if no == 0 else list(history or []) + [self._as_log(p, m) for p, m in lines]
                lines.append((person, self.chat_manager.reply(session_id, person, cast["player"], message, log_for)))
            return self._finish(session_id, lines)

        # 1人だけ呼ばれたらその人。呼ばれていなければ、誰に向けた発言かを判定する
        if called:
            responder = called[0]
        else:
            _, responder = self.chat_manager.main_chat(body, session_id, message, cast, previous_message)

        # 意識の確認・掛け合いは、メインキャラクター（参照種別 character）が返事をするときだけ。
        # サブや途中から来た人が返事をするときは、相談だけする（「お二人で読んでください」と頼まれたとき、連れと話してから答える）。
        is_main = responder.get("kind") == "character"
        if not is_main:
            log.info(f"[CHAT] メイン以外の返事なので、意識の確認・掛け合いはしません: {responder['id']}")

        # 相談できる相手（同じパーティーで、その場にいる人）。パーティーに入っていなければ None（相手を絞らない）
        mates = session_cast.party_mates(session_id, responder["id"]) if session_cast.in_party(session_id, responder["id"]) else None

        # 2a. 相談の確認: 同じパーティーの人がいれば、返事の前に相談するかを決める。
        # 相談するなら「相談 → 相手の返事 → プレイヤーへの返事」の順。ここで失敗したら、相談せずに返事をする
        consult_lines = []
        reply = None
        if mates:
            try:
                mate = self.chat_manager.consult_check(session_id, responder, mates, cast["player"], message, log_before)
                if mate:
                    ask = self.chat_manager.consult(session_id, responder, mate, cast["player"], message, log_before)
                    # 相談の一言が、相談の相手ではなくプレイヤーに向いていたら（「先生、〜」）、相談ではなく返事として使う。
                    # そのまま相手に返させると、相手がプレイヤーの代わりに答えてしまうため
                    addressed = self.chat_manager.addressed_to(responder, [mate, cast["player"]], message, ask)
                    if addressed and addressed["id"] == cast["player"]["id"]:
                        log.info("[CHAT] 相談の一言がプレイヤーに向いていたので、返事として使います")
                        reply = ask
                    else:
                        answer = self.chat_manager.reply(session_id, mate, responder, ask, list(history or []))
                        consult_lines = [(responder, ask), (mate, answer)]
            except Exception as e:
                log.info(f"[CHAT] 相談を飛ばしました: {type(e).__name__}: {e}")
                consult_lines = []

        # 2. 返事を作る（材料の会話ログは、プレイヤーの発言の手前まで。相談したときは、発言と相談まで）
        if consult_lines:
            log_consult = list(history or []) + [self._as_log(p, m) for p, m in consult_lines]
            reply = self.chat_manager.reply(session_id, responder, cast["player"], message, log_consult)
            # 相談の一言とまったく同じ返事なら、出さない（同じ文が2回並ぶため）
            if "".join(reply.split()) == "".join(consult_lines[0][1].split()):
                log.info("[CHAT] プレイヤーへの返事が相談の一言と同じだったので、出しません")
                return self._finish(session_id, consult_lines)
            # 相手と話したあとなので、意識の確認と掛け合いはしない
            return self._finish(session_id, consult_lines + [(responder, reply)])

        if reply is None:
            reply = self.chat_manager.reply(session_id, responder, cast["player"], message, log_before)
        lines = [(responder, reply)]

        # 3・4. 意識を確かめ、プレイヤー以外に向いていれば、掛け合いを1往復。
        # 掛け合いの相手は、同じパーティーの人だけ（パーティーに入っていない人は、相手を絞らない）。
        # ここで失敗しても、返事までは返す（掛け合いは無しにする）
        try:
            log_now = list(history or []) + [self._as_log(responder, reply)]
            target = None
            if is_main:
                target = self.chat_manager.attention(session_id, responder, cast, log_now)

            if target and mates is not None and target["id"] not in {m["id"] for m in mates}:
                log.info(f"[CHAT] 意識の相手が同じパーティーではないので、掛け合いはしません: {target['id']}")
                target = None

            if target and target["id"] not in (cast["player"]["id"], responder["id"]):
                opener = self.chat_manager.cross_talk(session_id, responder, target, log_now, reply)
                answer = self.chat_manager.reply(session_id, target, responder, opener, log_now)
                lines += [(responder, opener), (target, answer)]

                # 掛け合いのあとは、メインがプレイヤーに向き直って一言かける（意識をプレイヤーに戻す）
                log_after = log_now + [self._as_log(responder, opener), self._as_log(target, answer)]
                closing = self.chat_manager.cross_talk(session_id, responder, cast["player"], log_after, opener)
                lines.append((responder, closing))
        except Exception as e:
            log.info(f"[CHAT] 意識の確認・掛け合いを飛ばしました: {type(e).__name__}: {e}")

        return self._finish(session_id, lines)

    # 発言1回分の終わり。進行状態を ready に戻し、履歴に足す発言の並びを返す
    @staticmethod
    def _finish(session_id, lines) -> list:
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

    # 発言のあとの処理を、裏で始める。記憶の更新と画像作成を並べて動かす
    # turn_log: 今回の会話（プレイヤーの発言から、返事・掛け合いまでの履歴の行）
    def after_chat(self, session_id, cast, turn_log) -> None:
        self.memory_manager.update_after_chat(session_id, cast, turn_log)
        image_generation.start(session_id, turn_log)

    # 会話ログの1行の形（プロンプトの「これまでの会話」に使う）
    @staticmethod
    def _as_log(person, message):
        return {"message": message, "icon_data": {"character_id": person["id"], "character_name": person["name"]}}


    # 前処理・後処理は事前且つ、個別に呼ぶことがあるのかがポイント
    # 呼ばないならここに無くて良い
    # 前処理。入り口
