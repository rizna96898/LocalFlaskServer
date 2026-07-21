
from helpers import file_utils
from config import config
from pathlib import Path
from typing import Any

# ステータスのパスを返却
def get_prepare_status_path(session_id: str) -> Path:
    return config.SESSIONS_DIR / session_id / "prepare_status.yaml"

# ステータスを読み込んで返却
def load_prepare_status(session_id: str) -> dict[str, Any]:
    path = get_prepare_status_path(session_id)
    data = file_utils.load_yaml_file(path) or {}
    return data if isinstance(data, dict) else {}

# 待機判定確認
# 該当ステージのステータスがreadyなら続行可
def is_prepare_status_ready(session_id: str, *expected_stages: str) -> bool:
    data = load_prepare_status(session_id)
    if not isinstance(data, dict):
        return False

    return (
        data.get("status") == "ready"
        and data.get("complete_stage") in expected_stages
    )

# 実行ステータスの更新
def update_prepare_status(
    session_id: str,
    *,
    status: str | None = None,
    complete_stage: str | None = None,
    error_stage: str | None = None,
    error_message: str | None = None,
    needs_mob_chat: bool | None = None,
    mob_count: int | None = None,
    next_speakers: list | None = None,   # ← 追加
) -> bool:
    path = get_prepare_status_path(session_id)
    data = file_utils.load_yaml_file(path) or {}

    if not isinstance(data, dict):
        data = {}

    if status is not None:
        data["status"] = status

    if complete_stage is not None:
        data["complete_stage"] = complete_stage

    if error_stage is not None:
        data["error_stage"] = error_stage

    if error_message is not None:
        data["error_message"] = error_message

    if needs_mob_chat is not None:
        data["needs_mob_chat"] = needs_mob_chat

    if mob_count is not None:
        data["mob_count"] = mob_count

    if next_speakers is not None:
        # 念のため安全に文字列化＆空要素除去
        data["next_speakers"] = [
            str(x).strip()
            for x in next_speakers
            if x
        ]

    return file_utils.save_yaml_file(path, data)

# 処理開始時、実行ステータスの初期生成
def create_prepare_status(session_id: str) -> bool:
    return update_prepare_status (
            session_id = session_id,
            status = "processing",
            # new_chat / prepare / main_chat / mob_chat / after
            complete_stage = "new_chat",   
            error_stage = None,
            error_message = None,
            needs_mob_chat = False,
            mob_count = 0,
            next_speakers = [],
    )

# 処理完了時、実行ステータスの更新
def mark_prepare_ready(session_id: str, complete_stage: str) -> bool:
    return update_prepare_status(
        session_id,
        status="ready",
        complete_stage=complete_stage,
        error_stage=None,
        error_message=None,
    )

# エラー発生時、実行ステータスの更新
def mark_prepare_error(
    session_id: str,
    *,
    complete_stage: str,
    error_stage: str,
    error_message: str,
) -> bool:
    return update_prepare_status(
        session_id,
        status="error",
        complete_stage=complete_stage,
        error_stage=error_stage,
        error_message=error_message,
    )

# 前処理、ステータス確認
def can_start_prepare(session_id: str) -> bool:
    data = load_prepare_status(session_id)
    if not isinstance(data, dict):
        return False

    if data.get("status") == "ready":
        return is_prepare_status_ready(session_id, "new_chat", "after")
    else:
        return False

# メインチャット時、ステータス確認
def can_start_main_chat(session_id: str) -> bool:
    return is_prepare_status_ready(session_id, "prepare")

# 後処理、ステータス確認
def can_start_after(session_id: str) -> bool:
    return is_prepare_status_ready(session_id, "main_chat")

