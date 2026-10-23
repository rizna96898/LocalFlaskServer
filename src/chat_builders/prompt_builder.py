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
from helpers import session_cast

class ChatPromptBuilder:

    def _build_messages(
        self,
        prompt_data: Dict[str, Any],
        user_parts: list[str],
    ) -> List[Dict]:
        # 組み立て方は全プロンプト共通（string_utils.build_messages）
        return string_utils.build_messages(prompt_data, user_parts)

    # 差し込み口を system・template・tail_template のすべてで埋めて、共通の形に組み立てる
    def _build_filled(self, prompt_file: str, values: Dict[str, str]) -> List[Dict]:
        prompt_data = file_utils.load_yaml_file(config.MAIN / prompt_file)
        prompt_data = string_utils.fill_template(prompt_data, values, fields=("system", "template", "tail_template"))
        return self._build_messages(prompt_data, [])

    def create_reply_prompt(self, values: Dict[str, str]) -> List[Dict]:
        """返事を作るプロンプト（02_query_chat.yaml）"""
        return self._build_filled(PromptsMain.CHAT, values)

    def create_attention_prompt(self, values: Dict[str, str]) -> List[Dict]:
        """返事のあと、意識が誰に向いているかを確かめるプロンプト（03_query_judge_attention.yaml）"""
        return self._build_filled(PromptsMain.ATTENTION, values)

    def create_cross_talk_prompt(self, values: Dict[str, str]) -> List[Dict]:
        """掛け合いの話しかけのプロンプト（04_query_cross_talk.yaml）"""
        return self._build_filled(PromptsMain.CROSS_TALK, values)

    def create_consult_check_prompt(self, values: Dict[str, str]) -> List[Dict]:
        """返事の前に、同じパーティーの人に相談するかを決めるプロンプト（05_query_judge_consult.yaml）"""
        return self._build_filled(PromptsMain.CONSULT_CHECK, values)

    def create_called_names_prompt(self, values: Dict[str, str]) -> List[Dict]:
        """プレイヤーの発言で、名前で呼ばれた相手を抜き出すプロンプト（07_query_judge_called_names.yaml）"""
        return self._build_filled(PromptsMain.CALLED_NAMES, values)

    def create_consult_prompt(self, values: Dict[str, str]) -> List[Dict]:
        """相談の話しかけのプロンプト（06_query_consult.yaml）"""
        return self._build_filled(PromptsMain.CONSULT, values)

    def create_discrimination_prompt(self, candidates: List[Dict], previous_message: str = "", message: str = "") -> List[Dict]:
        """誰向けの発言か特定するための プロンプト

        candidates: 会話対象の候補（session_cast の人物）。ID と表示名を並べて渡す
        previous_message: 直前の発言（キャラクターA）
        message: 今回の発言（キャラクターB）。この発言が誰に向けたものかを判定する
        """
        prompt_data = file_utils.load_yaml_file(config.MAIN / PromptsMain.CHARACTER_IDENTIFICATION)

        log.info("キャラデータ", prompt_data)

        # 登場人物は世界の登場人物から作る。答えは ID で返させる。職業も付けて、会話の呼び方（先生など）と結び付けられるようにする
        characters = "\n".join(session_cast.label(c) for c in candidates)

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
