from typing import Dict, Any, Iterable
from flask import jsonify
from helpers import file_utils
import traceback

# エラー発生時。共通してログ書いたりできそうだから
# ここじゃないけど必要
def error_response(message: str, status_code: int) -> Dict:
    print(traceback.format_exc())
    return jsonify({
        "response": {"error": message},
        "status_code": status_code,
    })

def _wait_chat_stage_or_response(session_id: str, target_stage: str, error_message: str):
    if not session_id:
        return None

    ok = file_utils.wait_until_prepare_status(
        session_id,
        target_stage=target_stage,
        interval_sec=0.2,
    )

    if ok:
        return None

    return jsonify({"error": error_message}), 500