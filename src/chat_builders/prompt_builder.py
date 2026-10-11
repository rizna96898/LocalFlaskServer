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
        user_content = string_utils._join_sections(
            prompt_data.get("header", ""),
            *user_parts,
            prompt_data.get("template", ""),
            prompt_data.get("tail_template", ""),
        )

        return [
            {"role": "system", "content": prompt_data.get("system", "")},
            {"role": "user", "content": user_content},
        ]

    def create_discrimination_prompt(self, session_id, message: str = "") -> List[Dict]:
        """誰向けの発言か特定するための プロンプト"""
        prompt_data = file_utils.load_yaml_file(config.MAIN / PromptsMain.CHARACTER_IDENTIFICATION)

        log.info("キャラデータ", prompt_data)
        
        prompt_message = prompt_data.get("template")
        prompt_message = prompt_message.replace("{characters}", """shirai_yui
        shirai_keita""")
        prompt_message = prompt_message.replace("{player_message}", """（カッコウ医院の待合室で、隣に座る夫の手を握りながら、緊張と不安で心臓が高鳴っている。
        クリニックの清潔な雰囲気と、先生にこんな悩みを打ち明ける事の不安や恐れ。
        それでも、子供が欲しいという強い願いが胸を占めている。
        先生はどんな人なんだろう…と、ポニーテールの先を無意識にいじりながら）""")
        prompt_message = prompt_message.replace("{player_answer}", message)
        prompt_data["system"] = prompt_message

        user_parts = []

        return self._build_messages(
            prompt_data,
            user_parts
        )
    
    def create_chat_prompt(self, session_id, message: str = "") -> List[Dict]:
        """新規 world_memory 作成用のプロンプト"""
        prompt_data = file_utils.load_yaml_file(config.MAIN / PromptsMain.CHAT)
        character_dir = config.SESSIONS_DIR / session_id / "character"
        character_yaml = "shirai_yui" "_setting.yaml"
        character_data = file_utils.load_yaml_file(character_dir / character_yaml)

        log.info("キャラデータ", character_data)
        
        prompt_message = prompt_data.get("system")
        prompt_message = prompt_message.replace("{character_name}", "白井　結")
        prompt_message = prompt_message.replace("{character_info}", "あなたは元気な女の子です。")
        prompt_data["system"] = prompt_message

        user_parts = [
            message,
        ]

        return self._build_messages(
            prompt_data,
            user_parts
        )

    def create_edit_summary_prompt(
        self,
        memory_key: str,
        memory_value,
    ) -> list[dict]:
        prompt_data = self._load(config.BOOTSTRAP, Bootstrap.EDIT_SUMMARY)

        memory_yaml = yaml.safe_dump(
            memory_value or [],
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).strip()

        user_parts = [
            f"対象: {memory_key}",
            f"情報:\n{memory_yaml}",
        ]
        return self._build_messages(
            prompt_data,
            user_parts
        )