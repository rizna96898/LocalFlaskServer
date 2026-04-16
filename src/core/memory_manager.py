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
from core.prompt_builder import PromptBuilder
from helpers import string_utils
from helpers import file_utils
from services.openrouter_service import OpenRouterService
import traceback

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
            if not isinstance(item, str):
                continue

            text = item.strip()
            if not text:
                continue

            if "：" in text:
                name = text.split("：", 1)[0].strip()
            elif ":" in text:
                name = text.split(":", 1)[0].strip()
            else:
                name = text

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
                    config.PROMPTS_DIR / "character_identification.yaml"
                ) or {}

                world_participants = string_utils.build_characters_text(world_memory["current_state"]["participants"])

                print("current participantsの編集後文字列", world_participants)
                print("実行プロンプト原文", prompt_data)
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

                player_path = file_utils._find_character_file(player_name, character_path)

                print("player_path", player_path)

                player_obj = file_utils.load_yaml_file(player_path)

                player_obj["last_target"] = target

                file_utils.save_yaml_file(player_path, player_obj)

                print(f"[CREATE TARGET SPEAKERS UPDATE] ")

            except Exception as e:
                print(f"[CREATE TARGET SPEAKERS ERROR] {type(e).__name__}: {e}")

        Thread(target=task, daemon=True).start()
    
    def _run_world_memory_update_async(
        self,
        body: Dict,
        session_id: str,
        last_user_content: str,
        last_assistant_content: str,
    ):
        def task():
            try:
                world_memory_path = config.SESSIONS_DIR / session_id / "world_memory.yaml"
                old_world_memory = file_utils.load_yaml_file(world_memory_path) or {}
                if not isinstance(old_world_memory, dict):
                    old_world_memory = {}

                prompt_messages = self.prompt_builder.update_memory_prompt(
                    body=body,
                    last_user_content=last_user_content,
                    last_assistant_content=last_assistant_content,
                    old_world_memory=old_world_memory,
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
                    print(f"[WORLD UPDATE] YAML parse failed: {e}")
                    parsed_yaml = {}

                new_world_data = {
                    "file_status": {"status": "ready"},
                    "current_state": parsed_yaml.get("current_state", {}) if isinstance(parsed_yaml.get("current_state"), dict) else {},
                    "world": parsed_yaml.get("world", {}) if isinstance(parsed_yaml.get("world"), dict) else {},
                }

                normalized_new_world = string_utils.normalize_summary_data(new_world_data)
                merged_world = self._merge_memory_data(old_world_memory, normalized_new_world)

                world_block = merged_world.get("world", {})
                if isinstance(world_block, dict):
                    raw_relationships = world_block.get("world_relationships", [])
                    normalized_relationships: list[str] = []

                    if isinstance(raw_relationships, list):
                        for item in raw_relationships:
                            if isinstance(item, str) and item.strip():
                                normalized_relationships.append(
                                    string_utils.normalize_relationship_item(item)
                                )

                    world_block["world_relationships"] = string_utils._dedupe_list(normalized_relationships)
                    merged_world["world"] = world_block

                file_utils.save_yaml_file(world_memory_path, merged_world)
                print(f"[WORLD UPDATE] saved: {world_memory_path}")

            except Exception as e:
                print(f"[WORLD UPDATE ERROR] {type(e).__name__}: {e}")

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
                    "file_status": {"status": "ready"},
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
            try:
                print(f"[MEMORY] {operation}処理を実行中... session_id={session_id}")

                if operation == "create":
                    prompt_messages = self.prompt_builder.create_memory_prompt(body)
                elif operation == "update":
                    world_memory = file_utils.load_yaml_file(
                        config.SESSIONS_DIR / session_id / "world_memory.yaml"
                    ) or {}
                    prompt_messages = self.prompt_builder.update_memory_prompt(
                        body, user, char, world_memory
                    )
                else:
                    raise ValueError(f"Unknown operation: {operation}")

                response_text = self.openrouter.send_message(
                    messages=prompt_messages,
                    temperature=0.7,
                    max_tokens=1500,
                )

                response_text = string_utils.strip_code_block(response_text)

                import datetime
                temp_dir = Path("temp")
                temp_dir.mkdir(exist_ok=True)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_file = temp_dir / f"memory_raw_{operation}_{session_id}_{timestamp}.txt"

                with open(temp_file, "w", encoding="utf-8") as f:
                    f.write(response_text)

                with open(temp_file, "r", encoding="utf-8") as f:
                    raw_text = f.read()

                try:
                    parsed_yaml = yaml.safe_load(raw_text) or {}
                    if not isinstance(parsed_yaml, dict):
                        parsed_yaml = {}
                except Exception as e:
                    print(f"[MEMORY] YAML parse failed: {e}")
                    parsed_yaml = {}

                world_data = parsed_yaml.get("world", {}) if isinstance(parsed_yaml.get("world"), dict) else {}
                world_relationships_raw = world_data.get("world_relationships", [])

                if world_relationships_raw is None:
                    world_relationships = []
                elif isinstance(world_relationships_raw, list):
                    world_relationships = []
                    for item in world_relationships_raw:
                        if isinstance(item, str) and item.strip():
                            world_relationships.append(string_utils.normalize_relationship_item(item))
                elif isinstance(world_relationships_raw, str):
                    world_relationships = []
                    for line in world_relationships_raw.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("-"):
                            line = line.lstrip("-").strip()
                        if line:
                            world_relationships.append(string_utils.normalize_relationship_item(line))
                else:
                    world_relationships = []

                res_memory = {
                    "file_status": {"status": "ready"},
                    "current_state": parsed_yaml.get("current_state", {}),
                    "world": {
                        "world_relationships": world_relationships
                    }
                }

                world_memory_path = config.SESSIONS_DIR / session_id / "world_memory.yaml"
                normalized_memory = string_utils.normalize_summary_data(res_memory)
                file_utils.save_yaml_file(world_memory_path, normalized_memory)

                relation_names = self._extract_relationship_names(world_relationships)
                self._sync_session_character_files(session_id, relation_names)

                if operation == "create":
                    self._run_character_memory_create_async(
                        session_id,
                        relation_names,
                        body.get("description", ""),
                        body.get("scenario", ""),
                        body.get("first_mes", ""),
                        body.get("mes_example", "")
                    )
                elif operation == "update":
                    self._run_character_memory_update_async(
                        body,
                        session_id,
                        relation_names[0],
                        user,
                        char
                    )
                else:
                    raise ValueError(...)

            except Exception as e:
                print(f"[MEMORY LOGIC ERROR] {type(e).__name__}: {e}")
                traceback.print_exc()

                error_memory = {
                    "file_status": {"status": "error"},
                    "current_state": {"time": None, "participants": []},
                    "world": {"world_relationships": []},
                }
                file_utils.save_yaml_file(
                    config.SESSIONS_DIR / session_id / "world_memory.yaml",
                    error_memory
                )

        Thread(target=task, daemon=True).start()

    def _run_world_memory_create_async(self, body: Dict, session_id: str):
        # print(f"[WORLD MEMORY CREATE] start session_id={session_id}")

        char_info = body.copy()
        prompt_messages = self.prompt_builder.create_memory_prompt(char_info)

        result_text = self.openrouter.send_message(prompt_messages)
        response_text = string_utils.strip_code_block(result_text)

        memory_file = config.SESSIONS_DIR / session_id / "world_memory.yaml"
        success = file_utils.save_yaml_file(memory_file, response_text)

        if not success:
            raise RuntimeError(f"world_memory.yaml の保存に失敗しました: {memory_file}")

        print(f"[WORLD MEMORY CREATE] saved: {memory_file}")

        self._sync_related_characters_from_memory(session_id)

        # 必要ならここで関連キャラの初期memory生成
        # self._run_character_memory_create_async(...)
        
    def _sync_session_character_files(self, session_id: str, world_relation: list):
        try:
            st_char_dir = Path(config.CHARACTERS_DIR)
            session_char_dir = config.SESSIONS_DIR / session_id / "character"
            session_char_dir.mkdir(parents=True, exist_ok=True)

            #print(f"[WORLD] === character sync start ===")
            print(f"[WORLD] CHAR DIR: {st_char_dir}")
            print(f"[WORLD] SESSION DIR: {session_char_dir}")
            #print(f"[WORLD] world_relation: {world_relation}")

            if st_char_dir.exists():
                 print(f"[WORLD] found {len(list(st_char_dir.iterdir()))} files")
                #for f in st_char_dir.iterdir():
                    #print(f"  - {f.name}")
            else:
                print("[ERROR] ST character dir not found")

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

                found_file = file_utils._find_character_file(char_name, st_char_dir)

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
                            "file_status": {
                                "status": "ready"
                            },
                            "last_target": None
                        }

                        file_utils.save_yaml_file(dst_file, data)

            #print(f"[WORLD] === character sync end ===")

        except Exception as e:
            print(f"[WORLD ERROR] {e}")

    def _has_source_character_card(self, char_name: str) -> bool:
        st_char_dir = Path(config.CHARACTERS_DIR)
        if not st_char_dir.exists():
            return False
        return file_utils._find_character_file(char_name, st_char_dir) is not None
    
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
            session_char_dir = config.SESSIONS_DIR / session_id / "character"
            session_char_dir.mkdir(parents=True, exist_ok=True)

            done: set[str] = set()

            for name in relation_names:
                try:
                    if not isinstance(name, str):
                        continue

                    char_name = name.strip()
                    if not char_name or char_name in done:
                        continue
                    done.add(char_name)

                    if not self._has_source_character_card(char_name):
                        print(f"[CHAR MEMORY] skip mob: {char_name}")
                        continue

                    char_file = session_char_dir / f"{char_name}.yaml"
                    if not char_file.exists():
                        print(f"[CHAR MEMORY] skip missing session yaml: {char_file}")
                        continue

                    memory_file = session_char_dir / f"{char_name}_memory.yaml"
                    if memory_file.exists():
                        print(f"[CHAR MEMORY] skip exists: {memory_file.name}")
                        continue

                    char_data = file_utils.load_yaml_file(char_file) or {}
                    if not isinstance(char_data, dict):
                        print(f"[CHAR MEMORY] skip invalid yaml: {char_file.name}")
                        continue

                    if not char_data.get("name") and not char_data.get("description"):
                        print(f"[CHAR MEMORY] skip empty card: {char_file.name}")
                        continue

                    prompt_messages = self.prompt_builder.create_character_memory_prompt(char_data, description, scenario, first_mes)

                    response_text = self.openrouter.send_message(
                        messages=prompt_messages,
                        temperature=0.7,
                        max_tokens=1500
                    )

                    # print(f"[CHAR MEMORY RAW] {char_name}")
                    # print(response_text)

                    response_text = string_utils.strip_code_block(response_text)

                    import datetime
                    temp_dir = Path("temp")
                    temp_dir.mkdir(exist_ok=True)
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    temp_file = temp_dir / f"character_memory_raw_{session_id}_{char_name}_{timestamp}.txt"

                    with open(temp_file, "w", encoding="utf-8") as f:
                        f.write(response_text)

                    try:
                        parsed_yaml = yaml.safe_load(response_text) or {}
                        if not isinstance(parsed_yaml, dict):
                            parsed_yaml = {}
                    except Exception as e:
                        print(f"[CHAR MEMORY] YAML parse failed: {char_name}: {e}")
                        parsed_yaml = {}

                    result = {
                        "file_status": {"status": "ready"},
                        "current_state": parsed_yaml.get("current_state", {}) if isinstance(parsed_yaml.get("current_state"), dict) else {},
                        "memory": parsed_yaml.get("memory", {}) if isinstance(parsed_yaml.get("memory"), dict) else {},
                        "owned_items": parsed_yaml.get("owned_items", []) if isinstance(parsed_yaml.get("owned_items"), list) else [],
                    }

                    file_utils.save_yaml_file(memory_file, result)

                    dynamic_list = string_utils.extract_dynamic_params_from_mes_example(mes_example)
                    
                    dynamic_list = [
                        d for d in dynamic_list
                        if isinstance(d, dict) and d.get("target")
                    ]

                    if dynamic_list:
                        file_utils.apply_dynamic_params_to_characters(session_id, dynamic_list)
                    
                    print(f"[CHAR MEMORY] saved directory: {session_char_dir}")
                    print(f"[CHAR MEMORY] saved: {memory_file.name}")
                

                except Exception as e:
                    print(f"[CHAR MEMORY ERROR] {type(e).__name__}: {e}")

        Thread(target=task, daemon=True).start()