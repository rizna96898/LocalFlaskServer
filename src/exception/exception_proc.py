from typing import Dict, Any, Iterable
from flask import jsonify
import traceback
from logger import log

# エラー発生時。共通してログ書いたりできそうだから
# ここじゃないけど必要
def error_response(message: str, status_code: int) -> Dict:
    log.info(traceback.format_exc())
    return jsonify({
        "response": {"error": message},
        "status_code": status_code,
    })
