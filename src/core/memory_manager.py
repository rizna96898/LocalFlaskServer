# memory_manager.py
"""
記憶管理モジュール
- 新規チャット時の初期 world_memory 作成
- 通常会話時の記憶更新
- world_relationships の管理
"""

from threading import Thread
from typing import Dict
from pathlib import Path
import yaml
from config import config
from constant import (
    Bootstrap,
    PromptsPreprocess,
    PromptsMain,
    PromptsPostprocess,
)
from core.prompt_builder import PromptBuilder
from helpers import string_utils
from helpers import file_utils
from services.openrouter_service import OpenRouterService
import traceback
import asyncio

class MemoryManager:
    def __init__(self):
        self.prompt_builder = PromptBuilder()
        self.openrouter = OpenRouterService()
        # print("[MemoryManager] Initialized")

    def create_target_speakers(self, session_id: str, body:  Dict):
        print(f"[TARGET SPEAKERS] session_id={session_id} → 発言対象確定を開始")
        self._run_create_target_spealers(session_id, body)
        return ""

    def create_initial_memory(self, body: Dict, session_id: str):
        print(f"[MEMORY] session_id={session_id} → 初期記憶作成を開始")

        file_utils.mark_prepare_processing(session_id, "new_chat")

        self._run_memory_async(body, session_id, "create", "", "")

    def update_memory(
        self,
        body: Dict,
        session_id: str,
        character_name: str,
        last_user_content: str,
        last_assistant_content: str,
    ):
        print(f"[MEMORY] session_id={session_id} char={character_name} → 記憶更新を開始")
        self._run_memory_async(
            body=body,
            session_id=session_id,
            operation="update",
            user=last_user_content,
            char=last_assistant_content
        )

    def _extract_character_context(self, body: Dict) -> Dict:
        return {
            "name": body.get("name", ""),
            "description": body.get("description", ""),
            "personality": body.get("personality", ""),
            "scenario": body.get("scenario", ""),
            "first_mes": body.get("first_mes", ""),
            "mes_example": body.get("mes_example", ""),
        }

    def _extract_relationship_names(self, world_relationships):
        names = []

        for item in world_relationships:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
            elif isinstance(item, str):
                text = item.strip()
                if "：" in text:
                    name = text.split("：", 1)[0].strip()
                elif ":" in text:
                    name = text.split(":", 1)[0].strip()
                else:
                    name = text
            else:
                continue

            if name and name not in names:
                names.append(name)

        return names

    def _run_create_target_spealers(self, session_id: str, body: Dict):
        def task():
            try:
                # print("session_id:", session_id, type(session_id))
                # print("body:", body, type(body))

                # プレイヤーの発言が誰の物かを確認するプロンプトを投げる
                # yamlのロード
                world_memory = file_utils.load_yaml_file(
                    config.SESSIONS_DIR / session_id / "world_memory.yaml"
                ) or {}
                prompt_data = file_utils.load_yaml_file(
                    config.PREPROCESS / PromptsPreprocess.PLAYER_IDENTIFYCATION
                ) or {}

                print("prompt_path", config.BOOTSTRAP / PromptsPreprocess.PLAYER_IDENTIFYCATION)
                print("prompt_data", prompt_data)

                world_participants = string_utils.build_characters_text(world_memory["current_state"]["participants"])

                print("current participantsの編集後文字列", world_participants)
                # print("実行プロンプト原文", prompt_data)
                system_prompt = prompt_data["system"]
                template_prompt = prompt_data["template"]

                template_prompt = template_prompt.replace("{characters}", world_participants)
                template_prompt = template_prompt.replace("{player_message}", body.get("message", ""))
                
                print("置換後プロンプト全文", template_prompt)

                service = OpenRouterService()
                
                result = service.send_message(
                    messages=[
                        {"role": "user", "content": template_prompt}
                    ],
                    system_prompt=system_prompt
                )

                parsed = yaml.safe_load(string_utils.strip_code_block(result)) or {}
                target = parsed.get("target_speakers")

                print("今回の発話対象", target)

                name = body.get("player")
                player_name = name.split(": ", 1)[1].split("：", 1)[0]

                print("player_name", player_name)
                character_path = Path(config.SESSIONS_DIR / session_id / "character")

                player_path = file_utils.find_character_file(player_name, character_path)

                print("player_path", player_path)

                player_obj = file_utils.load_yaml_file(player_path)

                player_obj["last_target"] = target

                file_utils.save_yaml_file(player_path, player_obj)

                # ここは実データの持ち方に合わせて調整
                mob_count = 0

                if isinstance(target, list):
                    # プレイヤーとメインキャラを除いた人数をモブ数にしたいならここで調整
                    mob_count = len(target)

                elif isinstance(body.get("mob_count"), int):
                    mob_count = int(body.get("mob_count"))

                needs_mob_chat = mob_count > 0

                file_utils.update_prepare_status(
                    session_id,
                    status="ready",
                    complete_stage="prepare",
                    error_stage=None,
                    error_message=None,
                    needs_mob_chat=needs_mob_chat,
                    mob_count=mob_count,
                )

                print(f"[CREATE TARGET SPEAKERS UPDATE] ")

            except Exception as e:
                print(f"[CREATE TARGET SPEAKERS ERROR] {type(e).__name__}: {e}")

        Thread(target=task, daemon=True).start()
    
    def _run_character_memory_update_async(
        self,
        body: Dict,
        session_id: str,
        character_name: str,
        last_user_content: str,
        last_assistant_content: str,
    ):
        def task():
            try:
                # print("[CHAR UPDATE] _run_character_memory_update_async start")

                session_char_dir = config.SESSIONS_DIR / session_id / "character"
                session_char_dir.mkdir(parents=True, exist_ok=True)

                char_name = character_name.strip()
                if not char_name:
                    print("[CHAR UPDATE] skip empty character_name")
                    return

                character_file_path = file_utils.find_character_yaml_file(char_name, session_char_dir)
                if not character_file_path:
                    print(f"[CHAR UPDATE] character file not found: {char_name}")
                    return
                memory_file_path = file_utils.find_character_memory_file(char_name, session_char_dir)
                if not memory_file_path:
                    print(f"[CHAR UPDATE] memory file not found: {char_name}")
                    return

                character_file = file_utils.load_yaml_file(character_file_path) or {}
                if not isinstance(character_file, dict):
                    character_file = {}

                old_memory = file_utils.load_yaml_file(memory_file_path) or {}
                if not isinstance(old_memory, dict):
                    old_memory = {}

                prompt_messages = self.prompt_builder.update_character_memory_prompt(
                    character_name=char_name,
                    description=character_file.get("description"),
                    current_state=old_memory.get("current_state"),
                    last_user_content=last_user_content,
                    last_assistant_content=last_assistant_content,
                    old_memory=old_memory,
                )

                response_text = self.openrouter.send_message(
                    messages=prompt_messages,
                    temperature=0.7,
                    max_tokens=1500,
                )
                response_text = string_utils.strip_code_block(response_text)

                try:
                    parsed_yaml = yaml.safe_load(response_text) or {}
                    if not isinstance(parsed_yaml, dict):
                        parsed_yaml = {}
                except Exception as e:
                    print(f"[CHAR UPDATE] YAML parse failed: {char_name}: {e}")
                    parsed_yaml = {}

                new_memory = {
                    "current_state": parsed_yaml.get("current_state", {}) if isinstance(parsed_yaml.get("current_state"), dict) else {},
                    "memory": parsed_yaml.get("memory", {}) if isinstance(parsed_yaml.get("memory"), dict) else {},
                    "owned_items": parsed_yaml.get("owned_items", []) if isinstance(parsed_yaml.get("owned_items"), list) else [],
                    "param_data": parsed_yaml.get("param_data", []) if isinstance(parsed_yaml.get("param_data"), list) else [],
                    "last_contact_date": parsed_yaml.get("last_contact_date"),
                }

                merged_memory = string_utils._merge_memory_data(old_memory, new_memory)
                file_utils.save_yaml_file(memory_file_path, merged_memory)

                print(f"[CHAR UPDATE] saved: {memory_file_path.name}")

            except Exception as e:
                print(f"[CHAR UPDATE ERROR] {type(e).__name__}: {e}")

        Thread(target=task, daemon=True).start()
        
    def _run_memory_async(self, body: Dict, session_id: str, operation: str, user: str, char: str):
        def task():
            current_stage = "world"

            try:
                print(f"[MEMORY] {operation}処理を実行中... session_id={session_id}")

                if operation == "create":
                    current_stage = "world"

                    prompt_messages = self.prompt_builder.create_memory_prompt(body)

                    response_text = self.openrouter.send_message(
                        messages=prompt_messages,
                        temperature=0.7,
                        max_tokens=1500,
                    )

                    response_text = string_utils.strip_code_block(response_text)

                    try:
                        parsed_yaml = yaml.safe_load(response_text) or {}
                        if not isinstance(parsed_yaml, dict):
                            parsed_yaml = {}
                    except Exception as e:
                        print(f"[WORLD ERROR] YAML parse failed: {e}")
                        print(f"[WORLD ERROR] response_text head: {response_text[:500]!r}")
                        parsed_yaml = {}

                    player_name = string_utils.get_player_name(body.get("description"))

                    normalized_memory = string_utils.normalize_world_memory_data(
                        player_name,
                        parsed_yaml,
                    )

                    world_relationships = (
                        normalized_memory
                        .get("world", {})
                        .get("world_relationships", [])
                    )

                    if not world_relationships:
                        print(f"[WORLD ERROR] response_text head: {response_text[:500]!r}")
                        print(f"[WORLD ERROR] parsed_yaml: {parsed_yaml!r}")
                        raise ValueError("world_relationships is empty")

                    world_memory_path = config.SESSIONS_DIR / session_id / "world_memory.yaml"

                    print("[DEBUG] parsed_yaml.current_state =", parsed_yaml.get("current_state"))
                    print("[DEBUG] normalized_memory.current_state =", normalized_memory.get("current_state"))
                    print("[DEBUG] normalized_memory.world =", normalized_memory.get("world"))
                    print("[DEBUG] world_memory_path =", world_memory_path)

                    saved = file_utils.save_yaml_file(world_memory_path, normalized_memory)
                    if not saved:
                        raise RuntimeError(f"world memory save failed: {world_memory_path}")

                    relation_names = self._extract_relationship_names(world_relationships)

                    self._sync_session_character_files(
                        session_id=session_id,
                        world_relation=relation_names,
                        world_memory_path=world_memory_path,
                    )

                    current_stage = "character"

                    self._run_character_memory_create_sync(
                        session_id,
                        relation_names,
                        body.get("description", ""),
                        body.get("scenario", ""),
                        body.get("first_mes", ""),
                        body.get("mes_example", ""),
                    )

                    file_utils.mark_prepare_ready(session_id, "new_chat")

                elif operation == "update":
                    # 既存update処理
                    pass

            except Exception as e:
                print(f"[MEMORY LOGIC ERROR] {type(e).__name__}: {e}")
                import traceback
                print(traceback.format_exc())

                file_utils.mark_prepare_error(
                    session_id,
                    error_stage=current_stage,
                    error_message=f"{type(e).__name__}: {e}",
                    complete_stage="new_chat",
                )

        Thread(target=task, daemon=True).start()

    def _sync_session_character_files(self, session_id: str, world_relation: list, world_memory_path: Path):
        try:
            st_char_dir = Path(config.CHARACTERS_DIR)
            session_char_dir = config.SESSIONS_DIR / session_id / "character"
            session_char_dir.mkdir(parents=True, exist_ok=True)

            print(f"[WORLD] === character sync start ===")
            print(f"[WORLD] CHAR DIR: {st_char_dir}")
            print(f"[WORLD] SESSION DIR: {session_char_dir}")
            #print(f"[WORLD] world_relation: {world_relation}")

            for name in world_relation:
                #print(f"\n[WORLD] ---- processing: {name} ----")

                if not isinstance(name, str):
                    print("[WORLD] skip: not string")
                    continue

                char_name = name.strip()
                if not char_name:
                    print("[WORLD] skip: empty name")
                    continue

                dst_file = session_char_dir / f"{char_name}.yaml"

                found_file = file_utils.find_character_file(char_name, st_char_dir)

                #print(f"[WORLD] search result: {found_file}")

                if found_file:
                    #print(f"[WORLD] found file: {found_file}")

                    raw_data = file_utils._load_character_data(found_file)
                    #print(f"[WORLD] raw_data keys: {list(raw_data.keys()) if raw_data else 'EMPTY'}")

                    yaml_data = string_utils._convert_to_yaml_format(raw_data)
                    #print(f"[WORLD] yaml_data: {yaml_data}")

                    file_utils.save_yaml_file(dst_file, yaml_data)
                    print(f"[WORLD] saved yaml: {dst_file}")

                else:
                    print(f"[WORLD] {char_name} no match → create empty")

                    if not dst_file.exists():
                        data = {
                            "last_target": None
                        }

                        file_utils.save_yaml_file(dst_file, data)
            # --- ここから sub の詳細生成 ---
            world_memory = file_utils.load_yaml_file(world_memory_path) or {}
            current_state = world_memory.get("current_state", {}) if isinstance(world_memory, dict) else {}
            participants = current_state.get("participants", []) if isinstance(current_state, dict) else []
            world_block = world_memory.get("world", {}) if isinstance(world_memory, dict) else {}
            world_relationships = world_block.get("world_relationships", []) if isinstance(world_block, dict) else []

            prompt_data = file_utils.load_yaml_file(
                config.BOOTSTRAP / Bootstrap.SUB_CHARACTER_MEMORY
            ) or {}

            sub_template = prompt_data.get("sub_template", "")
            tail_template = prompt_data.get("tail_template", "")

            for participant in participants:
                if not isinstance(participant, dict):
                    continue

                sub_name = str(participant.get("name", "")).strip()
                role = str(participant.get("role", "")).strip()

                if not sub_name:
                    continue

                if role != "sub":
                    continue

                character_file = session_char_dir / f"{sub_name}.yaml"
                if not character_file.exists():
                    print(f"[SUB] skip missing shell: {character_file}")
                    continue

                base_data = file_utils.load_yaml_file(character_file) or {}
                if not isinstance(base_data, dict):
                    base_data = {}

                prompt_text = sub_template.format(
                    name=sub_name,
                    world_scenario=world_memory.get("scenario", ""),
                    world_relationships=string_utils.build_characters_text(world_relationships),
                )
                if tail_template:
                    prompt_text = prompt_text + "\n" + tail_template

                result_text = self.openrouter.send_message(
                    messages=[{"role": "user", "content": prompt_text}],
                    temperature=0.7,
                    max_tokens=1500,
                )

                response_text = string_utils.strip_code_block(result_text)

                try:
                    parsed_yaml = yaml.safe_load(response_text) or {}
                    if not isinstance(parsed_yaml, dict):
                        parsed_yaml = {}
                except Exception as e:
                    print(f"[SUB] YAML parse failed: {sub_name}: {e}")
                    parsed_yaml = {}

                base_profile = parsed_yaml.get("base_profile", {}) if isinstance(parsed_yaml.get("base_profile"), dict) else {}
                personality = parsed_yaml.get("personality", {}) if isinstance(parsed_yaml.get("personality"), dict) else {}
                attitude = parsed_yaml.get("attitude", {}) if isinstance(parsed_yaml.get("attitude"), dict) else {}
                current_state_data = parsed_yaml.get("current_state", {}) if isinstance(parsed_yaml.get("current_state"), dict) else {}

                if "base_profile" not in base_data or not isinstance(base_data.get("base_profile"), dict):
                    base_data["base_profile"] = {"name": sub_name}
                if "personality" not in base_data or not isinstance(base_data.get("personality"), dict):
                    base_data["personality"] = {}
                if "attitude" not in base_data or not isinstance(base_data.get("attitude"), dict):
                    base_data["attitude"] = {}
                if "current_state" not in base_data or not isinstance(base_data.get("current_state"), dict):
                    base_data["current_state"] = {}

                base_data["base_profile"]["name"] = sub_name
                base_data["base_profile"]["role"] = base_profile.get("role")
                base_data["base_profile"]["relation_to_main"] = base_profile.get("relation_to_main")

                base_data["personality"]["base_traits"] = personality.get("base_traits", []) if isinstance(personality.get("base_traits"), list) else []
                base_data["personality"]["speech_style"] = personality.get("speech_style")

                base_data["attitude"]["to_main"] = attitude.get("to_main")
                base_data["attitude"]["to_player"] = attitude.get("to_player")

                base_data["current_state"]["emotion"] = current_state_data.get("emotion")
                if "last_target" not in base_data["current_state"]:
                    base_data["current_state"]["last_target"] = None

                file_utils.save_yaml_file(character_file, base_data)
                print(f"[SUB] saved yaml: {character_file}")

            print(f"[WORLD] === character sync end ===")

        except Exception as e:
            print(f"[WORLD ERROR] {e}")

    def _has_source_character_card(self, char_name: str) -> bool:
        st_char_dir = Path(config.CHARACTERS_DIR)
        if not st_char_dir.exists():
            return False
        return file_utils.find_character_file(char_name, st_char_dir) is not None
    
    def _run_character_memory_create_async(
        self,
        session_id: str,
        relation_names: list[str],
        description: str = "",
        scenario: str = "",
        first_mes: str = "",
        mes_example: str = "",
    ):
        def task():
            self._run_character_memory_create_sync(
                session_id=session_id,
                relation_names=relation_names,
                description=description,
                scenario=scenario,
                first_mes=first_mes,
                mes_example=mes_example,
            )

        Thread(target=task, daemon=True).start()

    def _run_character_memory_create_sync(
        self,
        session_id: str,
        relation_names: list[str],
        description: str = "",
        scenario: str = "",
        first_mes: str = "",
        mes_example: str = "",
    ):
        print("_run_character_memory_create_sync start")
        # print(f"[CHAR MEMORY] relation_names = {relation_names}")

        session_char_dir = config.SESSIONS_DIR / session_id / "character"
        session_char_dir.mkdir(parents=True, exist_ok=True)

        done: set[str] = set()

        for name in relation_names:
            # print(f"[CHAR MEMORY] loop start: {name!r}")
            try:
                if not isinstance(name, str):
                    print(f"[CHAR MEMORY] skip not str: {name!r}")
                    continue

                char_name = name.strip()
                # print(f"[CHAR MEMORY] normalized: {char_name!r}")

                if not char_name:
                    print("[CHAR MEMORY] skip empty")
                    continue

                if char_name in done:
                    # print(f"[CHAR MEMORY] skip duplicate: {char_name}")
                    continue

                done.add(char_name)

                if not self._has_source_character_card(char_name):
                    print(f"[CHAR MEMORY] skip mob: {char_name}")
                    continue

                # print(f"[CHAR MEMORY] card exists: {char_name}")

                char_file = session_char_dir / f"{char_name}.yaml"
                # print(f"[CHAR MEMORY] char_file: {char_file}")

                if not char_file.exists():
                    print(f"[CHAR MEMORY] skip missing session yaml: {char_file}")
                    continue

                memory_file = session_char_dir / f"{char_name}_memory.yaml"
                # print(f"[CHAR MEMORY] memory_file: {memory_file}")

                if memory_file.exists():
                    print(f"[CHAR MEMORY] skip exists: {memory_file.name}")
                    continue

                # print(f"[CHAR MEMORY] load yaml start: {char_name}")
                char_data = file_utils.load_yaml_file(char_file) or {}
                # print(f"[CHAR MEMORY] load yaml end: {char_name}")

                # print(f"[CHAR MEMORY] prompt build start: {char_name}")
                prompt_messages = self.prompt_builder.create_character_memory_prompt(
                    char_data,
                    description,
                    scenario,
                    first_mes,
                )
                # print(f"[CHAR MEMORY] prompt build end: {char_name}")

                print(f"[CHAR MEMORY] ここで投げようとして結果落ちてるっぽい")
                response_text = self.openrouter.send_message(
                    messages=prompt_messages,
                    temperature=0.7,
                    max_tokens=1500
                )

                # print(f"[CHAR MEMORY] parse start: {char_name}")
                response_text = string_utils.strip_code_block(response_text)
                parsed_yaml = yaml.safe_load(response_text) or {}
                # print(f"[CHAR MEMORY] parse end: {char_name}")

                result = {
                    "current_state": parsed_yaml.get("current_state", {}) if isinstance(parsed_yaml.get("current_state"), dict) else {},
                    "memory": parsed_yaml.get("memory", {}) if isinstance(parsed_yaml.get("memory"), dict) else {},
                    "owned_items": parsed_yaml.get("owned_items", []) if isinstance(parsed_yaml.get("owned_items"), list) else [],
                }

                parameter_data = extract_character_parameters_from_mes_example(mes_example, char_name)
                if parameter_data:
                    result["parameter"] = parameter_data
                    
                # print(f"[CHAR MEMORY] save start: {memory_file}")
                saved = file_utils.save_yaml_file(memory_file, result)
                # print(f"[CHAR MEMORY] save result: {saved}")

                if not saved:
                    raise RuntimeError(f"character memory save failed: {memory_file}")

                self._create_character_summary_sync(
                    session_id=session_id,
                    char_name=char_name,
                    memory_file=memory_file,
                )
                # print(f"[CHAR MEMORY] saved: {memory_file.name}")
                # print(f"[CHAR MEMORY] exists after save: {memory_file.exists()}")

                # print(f"[CHAR MEMORY] send_message end: {char_name}")
            except Exception as e:
                print(f"[CHAR MEMORY ERROR] {type(e).__name__}: {e}")
                import traceback
                print(traceback.format_exc())
                raise

        print("セッションキャラディレクトリ", session_char_dir);
        print("_run_character_memory_create_sync end")

def extract_character_parameters_from_mes_example(mes_example: str, char_name: str) -> list[dict]:
    """
    mes_example 内の dynamic_params から、
    target == char_name（スペース無視）に一致する param_data を返す。
    一致しなければ [] を返す。
    """
    if not isinstance(mes_example, str) or not mes_example.strip():
        return []

    try:
        parsed = yaml.safe_load(mes_example) or {}
    except Exception as e:
        print(f"[PARAM WARN] mes_example parse failed: {e}")
        return []

    if not isinstance(parsed, dict):
        return []

    dynamic_params = parsed.get("dynamic_params")
    if not isinstance(dynamic_params, list):
        return []

    target_norm = "".join(str(char_name).split())

    for item in dynamic_params:
        if not isinstance(item, dict):
            continue

        target = item.get("target")
        param_data = item.get("param_data")

        if not isinstance(target, str) or not isinstance(param_data, list):
            continue

        item_target_norm = "".join(target.split())

        if item_target_norm == target_norm:
            result = []
            for param in param_data:
                if not isinstance(param, dict):
                    continue

                display_name = param.get("display_name")
                if not display_name:
                    continue

                result.append({
                    "display_name": display_name,
                    "count": param.get("count", 0),
                })
            return result

    return []

    def _create_character_summary_sync(
        self,
        session_id: str,
        char_name: str,
        memory_file: Path,
    ):
        session_char_dir = config.SESSIONS_DIR / session_id / "character"

        memory_data = file_utils.load_yaml_file(memory_file) or {}
        memory_block = memory_data.get("memory", {})
        if not isinstance(memory_block, dict):
            memory_block = {}

        summary = {
            "history": [],
            "progress": [],
            "worries": [],
        }

        for key in ("history", "progress", "worries"):
            value = memory_block.get(key, [])
            if not value:
                continue

            prompt_messages = self.prompt_builder.create_edit_summary_prompt(
                memory_key=key,
                memory_value=value,
            )

            response_text = self.openrouter.send_message(
                messages=prompt_messages,
                temperature=0.3,
                max_tokens=1000,
            )

            response_text = string_utils.strip_code_block(response_text).strip()

            if response_text:
                summary[key] = [response_text]

        summary_file = session_char_dir / f"{char_name}_summary.yaml"
        saved = file_utils.save_yaml_file(summary_file, summary)

        if not saved:
            raise RuntimeError(f"character summary save failed: {summary_file}")

        print(f"[CHAR SUMMARY] saved: {summary_file.name}")