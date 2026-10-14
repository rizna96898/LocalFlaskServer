
from helpers import file_utils
from config import config
from pathlib import Path
from typing import Any

# ステータスのパスを返却
def get_prepare_status_path(session_id: str) -> Path:
    return config.SESSIONS_DIR / session_id / "prepare_status.yaml"


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
    progress_done: int | None = None,
    progress_total: int | None = None,
    progress_label: str | None = None,
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

    # 初期記憶の進み具合（画面のプログレスバー用）
    if progress_done is not None:
        data["progress_done"] = progress_done

    if progress_total is not None:
        data["progress_total"] = progress_total

    if progress_label is not None:
        data["progress_label"] = progress_label

    return file_utils.save_yaml_file(path, data)

# 実行ステータスの更新（実行中に変更）
def mark_prepare_processing(session_id: str, complete_stage: str = "new_chat") -> bool:
    return update_prepare_status(
        session_id,
        status="processing",
        complete_stage=complete_stage,
        error_stage=None,
        error_message=None,
    )

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
            progress_done = 0,
            progress_total = 0,
            progress_label = "準備中",
    )


# 初期記憶の進み具合を記録する。done は終わった段階の数、total は全段階の数、label は今やっていること
def mark_progress(session_id: str, done: int, total: int, label: str) -> bool:
    return update_prepare_status(
        session_id,
        progress_done=done,
        progress_total=total,
        progress_label=label,
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
