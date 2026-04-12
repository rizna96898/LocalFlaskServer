"""
プロンプト構築クラス
- すべての固定プロンプトは files/prompts/ 以下のYAMLから読み込む
"""

from pathlib import Path
from typing import List, Dict, Any

import yaml

from config import config
from helpers.string_utils import normalize_newlines


class PromptBuilder:
    def __init__(self):
        self.prompts_dir: Path = config.PROMPTS_DIR

    def _load(self, filename: str) -> Dict[str, Any]:
        """promptsフォルダからYAMLを読み込む"""
        path = self.prompts_dir / filename
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
        base = self._load("memory_system.yaml")
        create = self._load("memory_create.yaml")

        # 新形式優先。旧形式 header/template にもフォールバック
        header = create.get("world_header", "")
        template = create.get("world_template", "")
        tail = create.get("tail_template", "")

        #print("[DEBUG] create keys:", create.keys())
        #print("[DEBUG] header:", repr(header[:100] if header else ""))
        #print("[DEBUG] template:", repr(template[:200] if template else ""))
        
        user_content = self._join_sections(
            header,
            charactor,
            story,
            template,
            tail,
        )

        return [
            {"role": "system", "content": base.get("system", "")},
            {"role": "user",   "content": user_content}
        ]

    def update_memory_prompt(self, charactor: str, user: str, char: str, memory: Dict) -> List[Dict]:
        """記憶更新用のプロンプト"""
        base = self._load("memory_system.yaml")
        update = self._load("memory_update.yaml")

        current_state = memory.get("current_state", {})

        previous_state = "\n".join([
            "【前回の current_state】",
            f"action: {current_state.get('action', '不明')}",
            f"focus_targets: {current_state.get('focus_targets', '不明')}",
            f"location: {current_state.get('location', '不明')}",
            f"mood: {current_state.get('mood', '不明')}",
            f"outfit: {current_state.get('outfit', '不明')}",
            f"participants: {current_state.get('participants', '不明')}",
            f"status: {current_state.get('status', '不明')}",
            f"time: {current_state.get('time', '不明')}",
        ])

        conversation = "\n\n".join([
            "【ユーザ発言】\n" + (user or ""),
            "【アシスタント発言】\n" + (char or ""),
        ])

        user_content = self._join_sections(
            update.get("header", ""),
            charactor,
            previous_state,
            conversation,
            update.get("template", ""),
            update.get("tail_template", ""),
        )

        return [
            {"role": "system", "content": base.get("system", "")},
            {"role": "user",   "content": user_content}
        ]

    # ======================
    # 基本システムプロンプト
    # ======================
    def get_system_base(self) -> str:
        """system_base.yaml から基本システムプロンプトを取得"""
        data = self._load("system_base.yaml")
        return data.get("system", "あなたは親切で自然なロールプレイキャラクターです。")

    # ======================
    # 動的パラメータ生成プロンプト（新規追加）
    # ======================
    def generate_dynamic_params_prompt(self, scenario: str, charactor: str = "") -> List[Dict]:
        """シナリオに基づいて、最初に必要な動的パラメータを提案させる"""
        base = self._load("dynamic_params.yaml")

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
        base = self._load("memory_system.yaml")
        create = self._load("memory_create.yaml")

        header = create.get("character_header", "")
        template = create.get("character_template", "")
        tail = create.get("tail_template", "")

        name_text = ""
        if character_data.get("name"):
            name_text = f"名前: {character_data.get('name', '')}"

        description_text = ""
        if character_data.get("description"):
            description_text = "説明:\n" + str(character_data.get("description", "")).strip()

        scenario_description_text = ""
        if description:
            scenario_description_text = "登場人物:\n" + str(description).strip()

        scenario_text = ""
        if scenario:
            scenario_text = "シナリオ:\n" + str(scenario).strip()

        first_mes_text = ""
        if first_mes:
            first_mes_text = "開始文:\n" + str(first_mes).strip()

        user_content = self._join_sections(
            header,
            name_text,
            description_text,
            scenario_description_text,
            scenario_text,
            first_mes_text,
            template,
            tail,
        )

        return [
            {"role": "system", "content": base.get("system", "")},
            {"role": "user",   "content": user_content},
        ]