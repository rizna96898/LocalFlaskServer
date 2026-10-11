# prompt_builder.py
"""
プロンプト構築クラス
- すべての固定プロンプトは files/prompts/ 以下のYAMLから読み込む
"""

from pathlib import Path
from typing import List, Dict, Any

import yaml

from config import config
from constant import (
    Bootstrap,
    PromptsPreprocess,
    PromptsMain,
    PromptsPostprocess,
)
from helpers.string_utils import normalize_newlines
from helpers import file_utils
from logger import log

class MemoryPromptBuilder:

    def _join_sections(self, *parts: str) -> str:
        """空文字を除外しつつ、改行の崩れを抑えて連結する"""
        cleaned: list[str] = []
        for part in parts:
            if part is None:
                continue
            text = normalize_newlines(str(part)).strip()
            if text:
                cleaned.append(text)
        return "\n\n".join(cleaned)

    # ======================
    # 記憶関連プロンプト
    # ======================
    def create_memory_prompt(self, charactor: str, story: str = "", start_message: str = "") -> List[Dict]:
        """新規 world_memory 作成用のプロンプト"""
        file_path = config.BOOTSTRAP / Bootstrap.WORLD_MEMORY
        prompt_data = file_utils.load_yaml_file(file_path)

        user_parts = [
            charactor,
            story,
            start_message,
        ]

        return self._build_messages(
            prompt_data,
            user_parts
        )

    # def update_memory_prompt(
    #     self,
    #     body: Dict,
    #     last_user_content: str,
    #     last_assistant_content: str,
    #     old_world_memory: Dict,
    # ) -> List[Dict]:
    #     """world_memory 更新用のプロンプト"""

    #     base = self._load("memory_system.yaml")
    #     update = self._load("memory_update.yaml")

    #     current_state = old_world_memory.get("current_state", {}) or {}
    #     world = old_world_memory.get("world", {}) or {}

    #     previous_world = "\n".join([
    #         "〖前回の world_memory〗",
    #         f"time: {current_state.get('time', '不明')}",
    #         f"participants: {current_state.get('participants', '不明')}",
    #         f"world_relationships: {world.get('world_relationships', '不明')}",
    #     ])

    #     conversation = "\n\n".join([
    #         "〖ユーザ発言〗\n" + (last_user_content or ""),
    #         "〖アシスタント発言〗\n" + (last_assistant_content or ""),
    #     ])

    #     optional_context = self._join_sections(
    #         f"名前: {body.get('name', '')}" if body.get("name") else "",
    #         "説明:\n" + str(body.get("description", "")).strip() if body.get("description") else "",
    #         "シナリオ:\n" + str(body.get("scenario", "")).strip() if body.get("scenario") else "",
    #         "開始文:\n" + str(body.get("first_mes", "")).strip() if body.get("first_mes") else "",
    #     )

    #     user_content = self._join_sections(
    #         update.get("world_header", ""),
    #         optional_context,
    #         previous_world,
    #         conversation,
    #         update.get("world_template", ""),
    #         update.get("tail_template", ""),
    #     )

    #     return [
    #         {"role": "system", "content": base.get("system", "")},
    #         {"role": "user", "content": user_content},
    #     ]

    # ======================
    # 動的パラメータ生成プロンプト（新規追加）
    # ======================

    # ======================
    # 将来的に使用する補助メソッド
    # ======================

    def _build_messages(
        self,
        prompt_data: Dict[str, Any],
        user_parts: list[str],
    ) -> List[Dict]:
        user_content = self._join_sections(
            prompt_data.get("header", ""),
            *user_parts,
            prompt_data.get("template", ""),
            prompt_data.get("tail_template", ""),
        )

        return [
            {"role": "system", "content": prompt_data.get("system", "")},
            {"role": "user", "content": user_content},
        ]
