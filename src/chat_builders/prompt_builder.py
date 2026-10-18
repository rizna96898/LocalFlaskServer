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
from helpers import string_utils

class ChatPromptBuilder:

    def _build_messages(
        self,
        prompt_data: Dict[str, Any],
        user_parts: list[str],
    ) -> List[Dict]:
        # 組み立て方は全プロンプト共通（string_utils.build_messages）
        return string_utils.build_messages(prompt_data, user_parts)

    def create_discrimination_prompt(self, candidates: List[Dict], previous_message: str = "", message: str = "") -> List[Dict]:
        """誰向けの発言か特定するための プロンプト

        candidates: 会話対象の候補（session_cast の人物）。ID と表示名を並べて渡す
        previous_message: 直前の発言（キャラクターA）
        message: 今回の発言（キャラクターB）。この発言が誰に向けたものかを判定する
        """
        prompt_data = file_utils.load_yaml_file(config.MAIN / PromptsMain.CHARACTER_IDENTIFICATION)

        log.info("キャラデータ", prompt_data)

        # 登場人物は世界の登場人物から作る。答えは ID で返させる
        characters = "\n".join(f"{c['id']}（{c['name']}）" for c in candidates)

        prompt_data = string_utils.fill_template(prompt_data, {
            "characters": characters,
            "player_message": previous_message,
            "player_answer": message,
        })

        user_parts = []

        return self._build_messages(
            prompt_data,
            user_parts
        )
