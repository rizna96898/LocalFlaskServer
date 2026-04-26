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

class PromptBuilder:

    def _load(self, filePath: Path, filename: str) -> Dict[str, Any]:
        """promptsフォルダからYAMLを読み込む"""
        path = filePath / filename
        if not path.exists():
            print(f"[WARN] Prompt file not found: {path}")
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[ERROR] Failed to load prompt {filename}: {e}")
            return {}

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
    def create_memory_prompt(self, charactor: str, story: str = "") -> List[Dict]:
        """新規 world_memory 作成用のプロンプト"""
        prompt_data = self._load(config.BOOTSTRAP, Bootstrap.WORLD_MEMORY)

        return self._build_messages(
            prompt_data,
            charactor,
            story,
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
    def generate_dynamic_params_prompt(self, scenario: str, charactor: str = "") -> List[Dict]:
        """シナリオに基づいて、最初に必要な動的パラメータを提案させる"""
        base = self._load(config.BOOTSTRAP, Bootstrap.CHARACTER_ITEMS)

        user_content = self._join_sections(
            base.get("header", ""),
            f"シナリオ:\n{scenario}",
            f"キャラクター情報:\n{charactor if charactor else '（キャラクターの基本情報）'}",
            base.get("template", ""),
        )

        return [
            {"role": "system", "content": base.get("system", "")},
            {"role": "user",   "content": user_content}
        ]

    # ======================
    # 将来的に使用する補助メソッド
    # ======================
    def build_memory_context(self, summary_data: Dict) -> List[Dict]:
        """記憶情報をシステムプロンプトに組み込む（将来的に使用）"""
        current_state = summary_data.get("current_state", {})
        memory = summary_data.get("memory", {})

        context = f"""現在の状況:
- 場所: {current_state.get('location', '不明')}
- 状況: {current_state.get('status', '不明')}
- 行動: {current_state.get('action', '不明')}
- 時間: {current_state.get('time', '不明')}
- 服装: {current_state.get('outfit', '不明')}
- 気分: {current_state.get('mood', '不明')}
- 登場人物: {current_state.get('participants', '不明')}
- 意識対象: {current_state.get('focus_targets', '不明')}
"""

        memory_text = f"""これまでの記憶:
- 思い出: {memory.get('history', [])}
- 進展: {memory.get('progress', [])}
- 悩み: {memory.get('worries', [])}
- 関係性: {memory.get('relationships', [])}
"""

        return [
            {"role": "system", "content": context},
            {"role": "system", "content": memory_text}
        ]

    def create_character_memory_prompt(
        self,
        character_data: Dict[str, Any],
        description: str = "",
        scenario: str = "",
        first_mes: str = "",
    ) -> List[Dict]:
        """キャラクター個別 memory 作成用のプロンプト"""
        prompt_data = self._load(config.BOOTSTRAP, Bootstrap.CHARACTER_MEMORY)

        name_text = f"名前: {character_data.get('name', '')}" if character_data.get("name") else ""

        description_text = (
            "説明:\n" + str(character_data.get("description", "")).strip()
            if character_data.get("description")
            else ""
        )

        scenario_description_text = (
            "登場人物:\n" + str(description).strip()
            if description
            else ""
        )

        scenario_text = (
            "シナリオ:\n" + str(scenario).strip()
            if scenario
            else ""
        )

        first_mes_text = (
            "開始文:\n" + str(first_mes).strip()
            if first_mes
            else ""
        )

        return self._build_messages(
            prompt_data,
            name_text,
            description_text,
            scenario_description_text,
            scenario_text,
            first_mes_text,
        )
    
    def update_character_memory_prompt(
        self,
        character_name: str,
        description: str,
        current_state: dict,
        last_user_content: str,
        last_assistant_content: str,
        old_memory: dict,
    ):
        prompt_data = self._load(config.POSTPROCESS, PromptsPostprocess.CHARACTER_MEMORY)

        current_state_yaml = yaml.safe_dump(
            current_state or {},
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).strip()

        old_memory_yaml = yaml.safe_dump(
            old_memory or {},
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).strip()

        user_parts = [
            f"対象キャラクター:\n{character_name}",
            "キャラ設定 description:\n" + description if description else "",
            "現在状態 current_state:\n" + current_state_yaml if current_state_yaml else "",
            "既存記憶 old_memory:\n" + (old_memory_yaml if old_memory_yaml else "{}"),
            "今回のユーザー発話:\n" + (last_user_content or ""),
            "今回のキャラクター発話:\n" + (last_assistant_content or ""),
        ]

        return self._build_messages(
            prompt_data,
            *user_parts,
        )

    def _build_messages(
        self,
        prompt_data: Dict[str, Any],
        *user_parts: str,
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

        return self._build_messages(
            prompt_data,
            f"対象: {memory_key}",
            f"情報:\n{memory_yaml}",
        )