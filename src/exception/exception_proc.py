from typing import Dict, Any, Iterable
from helpers import response_checker
import traceback
from logger import log

# エラー発生時。共通してログ書いたりできそうだから
# ここじゃないけど必要
def error_response(message: str, status_code: int) -> Dict:
    log.info(traceback.format_exc())
    return response_checker.response_error(message, status_code)
