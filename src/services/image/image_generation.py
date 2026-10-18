"""画像作成（発言のあとに、記憶の更新と並べて別スレッドで動かす）。

今は入口だけで、何もしない。画像生成の連携（StabilityMatrix など。docs/spec の Q37）を作るときに、
_run の中身を書く。起動確認は /v1/chat/check_stability（今は仮の実装）を使う予定。
"""
from threading import Thread

from logger import log


def start(session_id: str, turn_log: list) -> None:
    """発言1回分の会話（turn_log）を材料に、画像作成を別スレッドで始める。"""
    Thread(target=_run, args=(session_id, turn_log), daemon=True).start()


def _run(session_id: str, turn_log: list) -> None:
    try:
        # TODO: 画像生成の連携を作るときに、ここで画像を作る（今は何もしない）
        log.info(f"[IMAGE] session_id={session_id} 画像作成は未実装（{len(turn_log)} 行の会話を受け取った）")
    except Exception as e:
        log.info(f"[IMAGE ERROR] {type(e).__name__}: {e}")
