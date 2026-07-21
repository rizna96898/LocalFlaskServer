# memory_manager.py
"""
記憶管理モジュール
- 新規チャット時の初期 world_memory 作成
- 通常会話時の記憶更新
- world_relationships の管理
"""

from threading import Thread
from typing import Dict
from typing import Any
from pathlib import Path
import yaml
import json
from config import config
from constant import (
    Bootstrap,
    PromptsPreprocess,
    PromptsMain,
    PromptsPostprocess,
)
from memory_builders.prompt_builder import PromptBuilder
from helpers import string_utils
from helpers import file_utils
from services.llm.llm_service import ModelHandlingService
from helpers import response_checker
from memory_builders import use_memory_constant
from memory_builders import lord_init_files
from services.status import status_manager
class MemoryManager:
    def __init__(self):
        self.prompt_builder = PromptBuilder()
        self.model_handling_service = ModelHandlingService("local")
        # print("[MemoryManager] Initialized")

    # 問い合わせサービスへのクッション関数
    def send_prompt(self, send_data: Dict):
        response_text = self.model_handling_service.send_message(
            task_type=send_data.get("task_type"),
            messages=send_data.get("prompt_messages"),
            system_prompt=send_data.get("system_prompt"),
            temperature=send_data.get("temperature"),
            top_p=send_data.get("top_p"),
            stop=send_data.get("stop"),
            top_k = send_data.get("top_k"),
            repeat_penalty = send_data.get("repeat_penalty"),
            logit_bias= send_data.get("logit_bias")
        )
        return response_text

    # 初期記憶の非同期作成
    def create_initial_memory(self, session_id: str) -> str:
        print(f"[MEMORY] session_id={session_id} → 初期記憶作成を開始")

        try:
            file_utils.mark_prepare_processing(session_id, "new_chat")

            base_file_obj = lord_init_files.lord_base_world_yaml(session_id)
            # ここで必要なファイルをロードして受け渡しに使う
            system_file_path = config.SYSTEM_DIR / f"sessions_list.yaml"
            system_file_data = file_utils.load_yaml_file(system_file_path)

            # system_fileからworld_idを取得する
            sessions = base_file_obj["system_file_data"].get("sessions")

            for session in sessions:
                if session.get("session_id") == session_id:
                    world_id = session.get("world_id")
                    break
            
            # world_idで世界設定を読み込む
            world_file_path = config.SESSIONS_DIR / session_id / f"{world_id}_world.yaml"
            print("world_file_path", world_file_path)
            world_file_data = file_utils.load_yaml_file(world_file_path)

            # 記憶作成
            self._run_memory_async(session_id, "create", world_file_data)

            return world_file_data["開始メッセージ"]
        except Exception as e:
            print(f"[CREATE INITIAL MEMORY ERROR] {type(e).__name__}: {e}")

   # 上から呼ばれてる非同期処理
    def _run_memory_async(self, session_id: str, operation: str, world_file_data: Dict) -> str:
        def task():
            current_stage = "world"

            # 世界情報の作成
            try:
                print(f"[MEMORY] {operation}処理を実行中... session_id={session_id}")

                character = world_file_data["登場人物"]["世界の登場人物"]
                characters_text = json.dumps(
                    character,
                    ensure_ascii=False,
                    indent=2
                )
                story = world_file_data["シナリオ本文"]["現在"]
                characters_text = "【登場人物】\n" + characters_text
                story = "【シナリオ】\n" + story
                start_message = "【開始メッセージ】\n" + world_file_data["開始メッセージ"]

                print("character", characters_text)
                print("story", story)

                if operation == "create":
                    current_stage = "world"

                    # characterとstoryがセットで入っている？
                    # 世界の初期記憶作成
                    prompt_messages = self.prompt_builder.create_memory_prompt(characters_text, story, start_message)

                    parameters = use_memory_constant.get_world_memory_send_parameters(prompt_messages)

                    response_text = self.send_prompt(parameters)

                    response_text = string_utils.strip_code_block(response_text)

                    try:
                        parsed_yaml = yaml.safe_load(response_text) or {}
                        if not isinstance(parsed_yaml, dict):
                            parsed_yaml = {}
                        if response_checker.is_invalid_world_memory(parsed_yaml):
                            print("[WARN] world_relationships is empty. retry once.")
                            response_text = self.send_prompt(parameters)

                            response_text = string_utils.strip_code_block(response_text)
                            parsed_yaml = yaml.safe_load(response_text) or {}
                            if not isinstance(parsed_yaml, dict):
                                parsed_yaml = {}

                            print("２回目？返却yamlの内容？\n", parsed_yaml)
                    except Exception as e:
                        print(f"[WORLD ERROR] YAML parse failed: {e}")
                        print(f"[WORLD ERROR] response_text head: {response_text[:500]!r}")
                        parsed_yaml = {}
                    # 何のために必要なのか忘れた
                    player_id = "kyuya"
                    player_name = "究也"

                    # world_memoryのオブジェクトを作成
                    normalized_memory = string_utils.normalize_world_memory_data(
                        player_id,
                        player_name,
                        parsed_yaml,
                    )

                    world_relationships = (
                        normalized_memory
                        .get("世界の状態", {})
                        .get("参加者", [])
                    )

                    if not world_relationships:
                        print(f"[WORLD ERROR] response_text head: {response_text[:500]!r}")
                        print(f"[WORLD ERROR] parsed_yaml: {parsed_yaml!r}")
                        raise ValueError("world_relationships is empty")

                    world_memory_path = config.SESSIONS_DIR / session_id / "world_memory.yaml"

                    print("[DEBUG] normalized_memory.現在の状態 =", normalized_memory.get("現在の状態"))
                    print("[DEBUG] normalized_memory.世界の状態 =", normalized_memory.get("世界の状態"))
                    print("[DEBUG] world_memory_path =", world_memory_path)

                    saved = file_utils.save_yaml_file(world_memory_path, normalized_memory)
                    if not saved:
                        raise RuntimeError(f"world memory save failed: {world_memory_path}")

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

            # ここからキャラクター情報の作成
            try:
                if operation == "create":
                    current_stage = "character"
                    status_manager.mark_prepare_ready(session_id, "new_chat")

                    base_file_obj = lord_init_files.lord_base_character_yaml(session_id)

                    # キャラメモリ作成
                    # LocalLLMだとモデル性能が足りないので細かく
                    self._run_character_memory_create_sync(
                        session_id,
                        world_file_data["登場人物"]["世界の登場人物"],
                        world_file_data["シナリオ本文"],
                        world_file_data["開始メッセージ"],
                        world_file_data["シナリオパラメータ"],
                        base_file_obj,
                        normalized_memory
                    )

            except Exception as e:
                print(f"[CHARACTER LOGIC ERROR] {type(e).__name__}: {e}")
                import traceback
                print(traceback.format_exc())

                file_utils.mark_prepare_error(
                    session_id,
                    error_stage=current_stage,
                    error_message=f"{type(e).__name__}: {e}",
                    complete_stage="new_chat",
                )
        Thread(target=task, daemon=True).start()

    # 登場人物の初期記憶作成
    def _run_character_memory_create_sync(
        self,
        session_id: str,
        characters: list[dict[str, Any]] = [],
        scenario: dict = {},
        start_message: list[dict[str, Any]] = [],
        scenario_parameter: dict = {},
        base_file_obj: dict[str, Any] = {},
        world_memory_data: dict[str, Any] = {},
    ):
        print("_run_character_memory_create_sync start")
        # print(f"[CHAR MEMORY] relation_names = {relation_names}")

        session_dir = config.SESSIONS_DIR / session_id
        session_char_dir = session_dir / "character"
        # session_char_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = config.SESSIONS_DIR.parent.parent / "temp"
        done: set[str] = set()

        # キャラクター単位の初期設定ファイル作成
        for character in characters:
            
            try:

                char_id = character["参照ID"]

                # 作成対象はキャラのみ
                # 将来的にサブキャラも判定するかも
                if character["参照種別"] != "character":
                    print(f"[CHAR MEMORY] skip mob: {char_id}")
                    continue
                
                # キャラの状況一覧を問い合わせ
                print("[CHAR MEMORY MIDDLE SUMMERY] start")
                temp_file = self.proc_middle_summery(base_file_obj,
                                                     character,
                                                     char_id,
                                                     scenario,
                                                     scenario_parameter,
                                                     start_message,
                                                     temp_dir,
                                                     session_id,)
                print("[CHAR MEMORY MIDDLE SUMMERY] end")

                # 現在の状態(current_state)の作成
                # 場所(location)の特定
                print(f"[CHAR MEMORY PLACE] start: ")
                location = self.proc_middle_location(base_file_obj, temp_file,)
                print(f"[CHAR MEMORY PLACE] end: ")

                # キャラの状況一覧から、分類を判定
                print(f"[CHAR MEMORY CATEGORIZE] start: ")
                temp_file_path = self.proc_middle_categorize(temp_file,
                                                             base_file_obj,
                                                             temp_dir,
                                                             char_id,
                                                             session_id)
                print(f"[CHAR MEMORY CATEGORIZE] end: ")

                temp_file_data = file_utils.load_yaml_file(temp_file_path) or {}
                action = []
                status = []
                mood = []
                for temp_file_str in temp_file_data:
                    print('temp_file_str["要約元"]', temp_file_str["要約元"])
                    print('temp_file_str["分類"]', temp_file_str["分類"])
                    match temp_file_str["分類"]:
                        case "行動":
                            action.append(temp_file_str["要約元"])
                        case "状態":
                            status.append(temp_file_str["要約元"])
                        case "心情":
                            mood.append(temp_file_str["要約元"])

                # キャラの状況一覧から、分類を判定
                # 服装を判定
                print(f"[CHAR MEMORY  CLOTHING] start: ")
                clothing_data = self.proc_middle_clothing(                                         session_char_dir,
                                                          base_file_obj,
                                                          char_id,)
                print(f"[CHAR MEMORY CLOTHING] end: ")

                # 所持品を判定
                print(f"[CHAR MEMORY ITEMS] start: ")
                item_data = self.proc_middle_items(                                         session_char_dir,
                                                          base_file_obj,
                                                          char_id,
                                                          clothing_data,
                                                          location,
                                                          temp_file)
                print(f"[CHAR MEMORY ITEMS] end: ")

                # 意識（forcus_target）の特定（多分作成済み）
                print(f"[CHAR MEMORY TARGET] start: ")
                
                target_data = self.proc_middle_target(                                         base_file_obj,
                                                          character["表示名"],
                                                          world_memory_data,
                                                          start_message)
                target_list = []
                target_list.append(target_data["相手"])
                print(f"[CHAR MEMORY TARGET] end: ")

                # 所持金（currency）の特定
                print(f"[CHAR MEMORY CURRENCY] start: ")
                currency_data = self.proc_middle_currency(                                         session_char_dir,
                                                        base_file_obj,
                                                        char_id,
                                                        start_message,)
                print(f"[CHAR MEMORY CURRENCY] end: ")

                character_memory_obj = {}
                character_memory_obj["現在の状態"] = {}
                character_memory_obj["現在の状態"]["場所"] = location
                character_memory_obj["現在の状態"]["状態"] = status
                character_memory_obj["現在の状態"]["行動"] = action
                character_memory_obj["現在の状態"]["心情"] = mood
                character_memory_obj["現在の状態"]["服装"] = clothing_data["服装"]
                character_memory_obj["現在の状態"]["関係性"] = world_memory_data["現在の状態"]["参加者"]
                character_memory_obj["現在の状態"]["意識"] = target_list
                character_memory_obj["現在の状態"]["所持品"] = item_data["所持品"]
                character_memory_obj["現在の状態"]["金額"] = currency_data

                print("character_memory_save start");
                character_memory_path = config.SESSIONS_DIR / session_id / "character" / f"{char_id}_memory.yaml"
                saved = file_utils.save_yaml_file(character_memory_path, character_memory_obj)
                if not saved:
                    raise RuntimeError(f"character memory save failed: {character_memory_path}")
                print("character_memory_save end");
                continue
            except Exception as e:
                print(f"[CHAR MEMORY ERROR] {type(e).__name__}: {e}")
                import traceback
                print(traceback.format_exc())
                raise

        
        print("セッションキャラディレクトリ", session_char_dir);
        print("_run_character_memory_create_sync end")

    # 要約の問い合わせ
    def proc_middle_summery(self, 
                            base_file_obj: Dict[str, any] = {},
                            character: Dict[str, any] = {},
                            char_id: str = "",
                            scenario: str = "",
                            scenario_parameter: str = "",
                            start_message: str = "",
                            temp_dir: str = "",
                            session_id: str = ""):
        
        print("[CHAR MEMORY MIDDLE SUMMERY] replace start")
        result = self.replace_middle_summery(base_file_obj,
                                             character,
                                             char_id,
                                             scenario,
                                             scenario_parameter,
                                             start_message,)              
        print("[CHAR MEMORY MIDDLE SUMMERY] replace end")
        
        print("[CHAR MEMORY MIDDLE SUMMERY] send message start")
        parameters = use_memory_constant.get_character_midle_summery_send_parameters(result["system_prompt"], result["template_prompt"])
        response_text = self.send_prompt(parameters)
        response_text = string_utils.strip_code_block(response_text)
        list_input = string_utils.extract_list_items(response_text)
        print("[CHAR MEMORY MIDDLE SUMMERY] send message end")
        
        # config.SESSIONS_DIR = files/sessions 前提なら、プロジェクト直下の temp
        temp_file = temp_dir / f"{char_id}_{session_id}_middle.yaml"
        temp_dir.mkdir(parents=True, exist_ok=True)
        # 書き込み
        print(f"[CHAR MEMORY MIDDLE SUMMERY] saved: {temp_file}")
        with temp_file.open("w", encoding="utf-8") as f:
            yaml.safe_dump(list_input, f, allow_unicode=True, sort_keys=False)

        return temp_file
    
    # 要約のカテゴリ分割をと言わせ
    def proc_middle_categorize(self, 
                               temp_file: str = "",
                               base_file_obj: Dict[str, any] = {},
                               temp_dir: str = "",
                               char_id: str = "",
                               session_id: str = "",):
        temp_categorize_data = file_utils.load_yaml_file(temp_file) or {}
        system_prompt = base_file_obj["prompt_categorize_yaml"].get("system")
        # systemの中も置換しないといけないような気がする・・・
        for temp_categorize_str in temp_categorize_data:
            temp_str = base_file_obj["prompt_categorize_yaml"].get("message_header") + "\n" + temp_categorize_str + "\n" + base_file_obj["prompt_categorize_yaml"].get("tail_template")

            parameters = use_memory_constant.get_character_midle_categorize_send_parameters(system_prompt, temp_str)

            response_text = self.send_prompt(parameters)
            response_text = string_utils.strip_code_block(response_text)
        
            category = response_text.replace("分類名: ", "")
            categorized_result = []
            categorized_result.append({
                "要約元": temp_categorize_str,
                "分類": category
            })
            # config.SESSIONS_DIR = files/sessions 前提なら、プロジェクト直下の temp
            temp_file_path = temp_dir / f"{char_id}_{session_id}_middle_categorize.yaml"

            # ① 既存読み込み
            if temp_file_path.exists():
                with temp_file_path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or []
            else:
                data = []

            # ② 追加
            print("★ 書き込み前", len(data))
            data.extend(categorized_result)
            print("★ 書き込み後", len(data))

            # ③ 上書き
            with temp_file_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        
        print(f"[CHAR MEMORY CATEGORIZE] saved: {temp_file_path}")

        return temp_file_path
    
    # 場所の問い合わせ
    def proc_middle_location(self, 
                          base_file_obj: Dict[str, any] = {},
                          replace_obj: Dict[str, any] = {},):
        
        temp_place_str = file_utils.load_yaml_file(replace_obj) or {}
        temp_place_str = yaml.dump(
            temp_place_str,
            allow_unicode=True,
            sort_keys=False
        )

        system_prompt = base_file_obj["prompt_location_yaml"].get("system")
        # # systemの中も置換しないといけないような気がする・・・
        temp_str = base_file_obj["prompt_location_yaml"].get("template") + "\n" + base_file_obj["prompt_location_yaml"].get("tail_template")

        temp_str = temp_str.replace("{summary_data}", temp_place_str)

        # # ここでreplaceが必要かな？
        # # 後共通化できそう？
        parameters = use_memory_constant.get_character_midle_location_send_parameters(system_prompt, temp_str)

        response_text = self.send_prompt(parameters)
        response_text = string_utils.strip_code_block(response_text)
        print("response_text", response_text)
        return response_text

    # 服装の問い合わせ
    def proc_middle_clothing(self,
                             session_char_dir:Path = "",
                             base_file_obj: Dict[str, any] = {},
                             char_id: str = "",):
        # characterファイルの読み込み
        character_data = file_utils.load_yaml_file(session_char_dir / f"{char_id}_setting.yaml") or {}
        character_data = yaml.dump(
            character_data,
            allow_unicode=True,
            sort_keys=False
        )

        system_prompt = base_file_obj["prompt_clothing_yaml"].get("system")
        temp_str = base_file_obj["prompt_clothing_yaml"].get("template")
        tail_str = base_file_obj["prompt_clothing_yaml"].get("tail_template")

        temp_str = temp_str.replace("{character_data}", character_data)
        temp_str = temp_str + "\n" + tail_str

        parameters = use_memory_constant.get_character_midle_clothing_send_parameters(system_prompt, temp_str)

        response_text = self.send_prompt(parameters)
        response_text = string_utils.strip_code_block(response_text)
        
        print("response_text", response_text)
        return yaml.safe_load(response_text) or {}

    # 所持品の問い合わせ
    def proc_middle_items(self,
                          session_char_dir:Path = "",
                          base_file_obj: Dict[str, any] = {},
                          char_id: str = "",
                          clothing_data: list[str] = [],
                          location: str = "",
                          temp_file: str = "",):
        
        temp_categorize_data = file_utils.load_yaml_file(temp_file) or {}

        # characterファイルの読み込み
        character_data = file_utils.load_yaml_file(session_char_dir / f"{char_id}_setting.yaml") or {}
        character_data = yaml.dump(
            character_data,
            allow_unicode=True,
            sort_keys=False
        )
        clothing_str = yaml.dump(
            clothing_data["服装"],
            allow_unicode=True,
            sort_keys=False
        )
        summary_str = yaml.dump(
            temp_categorize_data,
            allow_unicode=True,
            sort_keys=False
        )

        system_prompt = base_file_obj["prompt_items_yaml"].get("system")
        temp_str = base_file_obj["prompt_items_yaml"].get("template")
        tail_str = base_file_obj["prompt_items_yaml"].get("tail_template")

        temp_str = temp_str.replace("{clothing_data}", clothing_str)
        temp_str = temp_str.replace("{character_data}", character_data)
        temp_str = temp_str.replace("{location}", location)
        temp_str = temp_str.replace("{summary}", summary_str)

        temp_str = temp_str + "\n" + tail_str

        parameters = use_memory_constant.get_character_midle_items_send_parameters(system_prompt, temp_str)

        response_text = self.send_prompt(parameters)
        response_text = string_utils.strip_code_block(response_text)
        
        print("返却前全文", response_text)
        return yaml.safe_load(response_text) or {}

    # 意識を誰に向けているか問い合わせ
    def proc_middle_target(self,
                          base_file_obj: Dict[str, any] = {},
                          character_name: str = "",
                          world_memory_data: list[str] = [],
                          first_message: str = "",):
        participants_str = yaml.dump(
            world_memory_data["現在の状態"]["参加者"],
            allow_unicode=True,
            sort_keys=False
        )

        system_prompt = base_file_obj["prompt_target_yaml"].get("system")
        temp_str = base_file_obj["prompt_target_yaml"].get("template")
        tail_str = base_file_obj["prompt_target_yaml"].get("tail_template")

        temp_str = temp_str.replace("{character_name}", character_name or "")
        temp_str = temp_str.replace("{participants_data}", participants_str or "")
        temp_str = temp_str.replace("{first_message}", first_message or "")

        temp_str = temp_str + "\n" + tail_str

        print("置換後", temp_str)
        parameters = use_memory_constant.get_character_midle_target_send_parameters(system_prompt, temp_str)

        response_text = self.send_prompt(parameters)
        response_text = string_utils.strip_code_block(response_text)
        
        print("返却前全文", response_text)
        return yaml.safe_load(response_text) or {}

    # 所持金の問い合わせ
    def proc_middle_currency(self,
                          session_char_dir:Path = "",
                          base_file_obj: Dict[str, any] = {},
                          char_id: str = "",
                          first_message: str = "",):
        
        # characterファイルの読み込み
        character_data = file_utils.load_yaml_file(session_char_dir / f"{char_id}_setting.yaml") or {}
        character_name = character_data["名前"]["表示名"]
        character_data = yaml.dump(
            character_data,
            allow_unicode=True,
            sort_keys=False
        )

        system_prompt = base_file_obj["prompt_currency_yaml"].get("system")
        temp_str = base_file_obj["prompt_currency_yaml"].get("template")
        tail_str = base_file_obj["prompt_currency_yaml"].get("tail_template")

        temp_str = temp_str.replace("{character_name}", character_name)
        temp_str = temp_str.replace("{character_data}", character_data)
        temp_str = temp_str.replace("{first_message}", first_message)

        temp_str = temp_str + "\n" + tail_str

        parameters = use_memory_constant.get_character_midle_currency_send_parameters(system_prompt, temp_str)

        response_text = self.send_prompt(parameters)
        response_text = string_utils.strip_code_block(response_text)
        
        print("返却前全文", response_text)
        return yaml.safe_load(response_text) or {}

    # TODO 変動パラメータの作成（未実装、予定）
    def convert_dynamic_params(self, data):
        result = {}

        for item in data.get("変動パラメータ", []):
            target = item.get("対象キャラクターID")
            param_list = item.get("パラメーター", [])

            if not target:
                continue

            result[target] = {}

            for p in param_list:
                name = p.get("表示名")
                value = p.get("数値")

                if name:
                    result[target][name] = value

        return {"変動パラメータ": result}

    # システムプロンプトとテンプレートプロンプトの置換
    def replace_middle_summery(self, 
                               base_file_obj: Dict[str, any] = {},
                               character: Dict[str, any] = {},
                               char_id: str = "",
                               scenario: str = "",
                               scenario_parameter: str = "",
                               start_message: str = ""):
        
        system_prompt = base_file_obj["prompt_data"].get("system", "")
        template_prompt = base_file_obj["prompt_data"].get("template", "")
        
        # 置換できるように改行有文字列にする
        
        scenario_str = json.dumps(
                        scenario,
                        ensure_ascii=False,
                        indent=2
                    )
        scenario_parameter_prompt = self.convert_dynamic_params(scenario_parameter)
        scenario_parameter_str = yaml.dump(
            scenario_parameter_prompt,
            allow_unicode=True,
            sort_keys=False
        )
        relationships = base_file_obj["world_memory_data"].get("世界の状態").get("参加者")
        relationships_str = yaml.dump(
            relationships,
            allow_unicode=True,
            sort_keys=False
        )

        # system_promptの置換
        system_prompt = system_prompt.replace("{character_name}", character["表示名"])
        # template_promptの置換
        template_prompt = template_prompt.replace("{character_name}", char_id)
        template_prompt = template_prompt.replace("{scenario}", scenario_str or "")
        template_prompt = template_prompt.replace("{mes_example}", scenario_parameter_str or "")
        template_prompt = template_prompt.replace("{first_mes}", start_message or "")
        template_prompt = template_prompt.replace("{characters}", relationships_str)

        result = {}
        result["system_prompt"] = system_prompt
        result["template_prompt"] = template_prompt
        return result

    # 次の話者確定（使ってない可能性ある）
    # def create_target_speakers(self, session_id: str, body:  Dict):
    #     print(f"[TARGET SPEAKERS] session_id={session_id} → 発言対象確定を開始")
    #     self._run_create_target_speakers(session_id, body)
    #     return ""

    # 次の話者確定（上から呼ばれる）
    # def _run_create_target_speakers(self, session_id: str, body: Dict):
    #     def task():
    #         try:
    #             # print("session_id:", session_id, type(session_id))
    #             # print("body:", body, type(body))

    #             # プレイヤーの発言が誰の物かを確認するプロンプトを投げる
    #             # yamlのロード
    #             world_memory = file_utils.load_yaml_file(
    #                 config.SESSIONS_DIR / session_id / "world_memory.yaml"
    #             ) or {}
    #             prompt_data = file_utils.load_yaml_file(
    #                 config.PREPROCESS / PromptsPreprocess.PLAYER_IDENTIFYCATION
    #             ) or {}

    #             print("prompt_path", config.BOOTSTRAP / PromptsPreprocess.PLAYER_IDENTIFYCATION)
    #             print("prompt_data", prompt_data)

    #             world_participants = string_utils.build_characters_text(world_memory["current_state"]["participants"])

    #             print("current participantsの編集後文字列", world_participants)
    #             # print("実行プロンプト原文", prompt_data)
    #             system_prompt = prompt_data["system"]
    #             template_prompt = prompt_data["template"]

    #             template_prompt = template_prompt.replace("{characters}", world_participants)
    #             template_prompt = template_prompt.replace("{player_message}", body.get("message", ""))
                
    #             print("置換後プロンプト全文", template_prompt)
    #             #どれだけ自由に出力させるか。
    #             temperature = 0.5
    #             #出力候補の「確率の合計」でカット
    #             top_p = 0.9
    #             #上位K個だけ候補にする
    #             top_k = 0
    #             #1回の応答の最大長n_ctxの1/4位
    #             max_tokens = 1024
    #             #停止文字
    #             stop=[] # これを足す

    #             result = self.model_handling_service.send_message(
    #                 messages=[
    #                     {"role": "user", "content": template_prompt}
    #                 ],
    #                 system_prompt=system_prompt,
    #                 temperature=temperature,
    #                 top_p=top_p,
    #                 max_tokens=max_tokens,
    #                 stop=stop
    #             )

    #             parsed = yaml.safe_load(string_utils.strip_code_block(result)) or {}
    #             target = parsed.get("target_speakers")

    #             print("今回の発話対象", target)

    #             name = body.get("player")
    #             player_name = name.split(": ", 1)[1].split("：", 1)[0]

    #             print("player_name", player_name)
    #             character_path = Path(config.SESSIONS_DIR / session_id / "character")

    #             player_path = file_utils.find_character_file(player_name, character_path)

    #             print("player_path", player_path)

    #             player_obj = file_utils.load_yaml_file(player_path)

    #             player_obj["last_target"] = target

    #             file_utils.save_yaml_file(player_path, player_obj)

    #             # ここは実データの持ち方に合わせて調整
    #             mob_count = 0

    #             if isinstance(target, list):
    #                 # プレイヤーとメインキャラを除いた人数をモブ数にしたいならここで調整
    #                 mob_count = len(target)

    #             elif isinstance(body.get("mob_count"), int):
    #                 mob_count = int(body.get("mob_count"))

    #             needs_mob_chat = mob_count > 0

    #             file_utils.update_prepare_status(
    #                 session_id,
    #                 status="ready",
    #                 complete_stage="prepare",
    #                 error_stage=None,
    #                 error_message=None,
    #                 needs_mob_chat=needs_mob_chat,
    #                 mob_count=mob_count,
    #             )

    #             print(f"[CREATE TARGET SPEAKERS UPDATE] ")

    #         except Exception as e:
    #             print(f"[CREATE TARGET SPEAKERS ERROR] {type(e).__name__}: {e}")

    #     Thread(target=task, daemon=True).start()
    
    # 使ってないけどキャラクターの記憶を更新
    # def _run_character_memory_update_async(
    #     self,
    #     body: Dict,
    #     session_id: str,
    #     character_name: str,
    #     last_user_content: str,
    #     last_assistant_content: str,
    # ):
    #     def task():
    #         try:
    #             print("[CHAR UPDATE] _run_character_memory_update_async start")

    #             session_char_dir = config.SESSIONS_DIR / session_id / "character"
    #             session_char_dir.mkdir(parents=True, exist_ok=True)

    #             char_name = character_name.strip()
    #             if not char_name:
    #                 print("[CHAR UPDATE] skip empty character_name")
    #                 return

    #             character_file_path = file_utils.find_character_yaml_file(char_name, session_char_dir)
    #             if not character_file_path:
    #                 print(f"[CHAR UPDATE] character file not found: {char_name}")
    #                 return
    #             memory_file_path = file_utils.find_character_memory_file(char_name, session_char_dir)
    #             if not memory_file_path:
    #                 print(f"[CHAR UPDATE] memory file not found: {char_name}")
    #                 return

    #             character_file = file_utils.load_yaml_file(character_file_path) or {}
    #             if not isinstance(character_file, dict):
    #                 character_file = {}

    #             old_memory = file_utils.load_yaml_file(memory_file_path) or {}
    #             if not isinstance(old_memory, dict):
    #                 old_memory = {}

    #             prompt_messages = self.prompt_builder.update_character_memory_prompt(
    #                 character_name=char_name,
    #                 description=character_file.get("description"),
    #                 current_state=old_memory.get("current_state"),
    #                 last_user_content=last_user_content,
    #                 last_assistant_content=last_assistant_content,
    #                 old_memory=old_memory,
    #             )

    #             response_text = self.model_handling_service.send_message(
    #                 messages=prompt_messages,
    #                 temperature=0.7,
    #                 max_tokens=1500,
    #             )
    #             response_text = string_utils.strip_code_block(response_text)

    #             try:
    #                 parsed_yaml = yaml.safe_load(response_text) or {}
    #                 if not isinstance(parsed_yaml, dict):
    #                     parsed_yaml = {}
    #             except Exception as e:
    #                 print(f"[CHAR UPDATE] YAML parse failed: {char_name}: {e}")
    #                 parsed_yaml = {}

    #             new_memory = {
    #                 "current_state": parsed_yaml.get("current_state", {}) if isinstance(parsed_yaml.get("current_state"), dict) else {},
    #                 "memory": parsed_yaml.get("memory", {}) if isinstance(parsed_yaml.get("memory"), dict) else {},
    #                 "owned_items": parsed_yaml.get("owned_items", []) if isinstance(parsed_yaml.get("owned_items"), list) else [],
    #                 "param_data": parsed_yaml.get("param_data", []) if isinstance(parsed_yaml.get("param_data"), list) else [],
    #                 "last_contact_date": parsed_yaml.get("last_contact_date"),
    #             }

    #             merged_memory = string_utils._merge_memory_data(old_memory, new_memory)
    #             file_utils.save_yaml_file(memory_file_path, merged_memory)

    #             print(f"[CHAR UPDATE] saved: {memory_file_path.name}")

    #         except Exception as e:
    #             print(f"[CHAR UPDATE ERROR] {type(e).__name__}: {e}")

    #     Thread(target=task, daemon=True).start()

    # 使ってないけど更新処理
    # def update_memory(
    #     self,
    #     body: Dict,
    #     session_id: str,
    #     character_name: str,
    #     last_user_content: str,
    #     last_assistant_content: str,
    # ):
    #     print(f"[MEMORY] session_id={session_id} char={character_name} → 記憶更新を開始")
    #     self._run_memory_async(
    #         body=body,
    #         session_id=session_id,
    #         operation="update",
    #         user=last_user_content,
    #         char=last_assistant_content
    #     )

    # モブキャラを作ってる？ブラウザでほぼ確定してるから要らんのかも
    # def _sync_session_character_files(self, session_id: str, world_relation: list):
    #     try:
    #         st_char_dir = Path(config.CHARACTERS_DIR)
    #         session_char_dir = config.SESSIONS_DIR / session_id / "character"
    #         session_char_dir.mkdir(parents=True, exist_ok=True)

    #         print(f"[WORLD] === character sync start ===")
    #         print(f"[WORLD] CHAR DIR: {st_char_dir}")
    #         print(f"[WORLD] SESSION DIR: {session_char_dir}")

    #         # モブ用テンプレート
    #         mob_template_path = config.TEMPLATES_DIR / Bootstrap.SUB_CHARACTER_TEMPLATE
    #         print("[WORLD] TEMPLATE_PATH")
    #         mob_template_data = file_utils.load_yaml_file(mob_template_path) or {}
    #         if not isinstance(mob_template_data, dict):
    #             mob_template_data = {}

    #         for name in world_relation:
    #             if not isinstance(name, str):
    #                 print("[WORLD] skip: not string")
    #                 continue

    #             char_name = name.strip()
    #             if not char_name:
    #                 print("[WORLD] skip: empty name")
    #                 continue

    #             dst_file = session_char_dir / f"{char_name}.yaml"
    #             found_file = file_utils.find_character_file(char_name, st_char_dir)

    #             # --------------------------------------------------
    #             # 1. キャラカードが存在する場合
    #             #    description 内 YAML を正として保存する
    #             # --------------------------------------------------
    #             if found_file:
    #                 raw_data = file_utils._load_character_data(found_file)

    #                 yaml_data = file_utils.load_yaml_from_character_description(raw_data)

    #                 if not yaml_data:
    #                     print(f"[WORLD] description YAML not found or invalid: {char_name}")
    #                     yaml_data = {
    #                         "名前": {
    #                             "表示名": raw_data.get("name") or char_name,
    #                         }
    #                     }

    #                 file_utils.save_yaml_file(dst_file, yaml_data)
    #                 print(f"[WORLD] saved character card yaml: {dst_file}")
    #                 continue

    #             # --------------------------------------------------
    #             # 2. キャラカードが存在しない場合
    #             #    モブ用テンプレートに名前だけ入れて保存する
    #             # --------------------------------------------------
    #             print(f"[WORLD] {char_name} no match → create mob character yaml")

    #             if dst_file.exists():
    #                 print(f"[MOB] skip existing yaml: {dst_file}")
    #                 continue

    #             # テンプレートを破壊しないように deepcopy
    #             import copy
    #             data = copy.deepcopy(mob_template_data)

    #             if not isinstance(data, dict):
    #                 data = {}

    #             if "名前" not in data or not isinstance(data.get("名前"), dict):
    #                 data["名前"] = {}

    #             data["名前"]["表示名"] = char_name

    #             file_utils.save_yaml_file(dst_file, data)
    #             print(f"[MOB] saved character yaml: {dst_file}")

    #         print(f"[WORLD] === character sync end ===")

    #     except Exception as e:
    #         print(f"[WORLD ERROR] {e}")

    # 登場人物の初期記憶作成
    # def _run_character_memory_create_async(
    #     self,
    #     session_id: str,
    #     relation_names: list[str],
    #     description: str = "",
    #     scenario: str = "",
    #     first_mes: str = "",
    #     mes_example: str = "",
    # ):
    #     def task():
    #         self._run_character_memory_create_sync(
    #             session_id=session_id,
    #             relation_names=relation_names,
    #             description=description,
    #             scenario=scenario,
    #             first_mes=first_mes,
    #             mes_example=mes_example,
    #         )

    #     Thread(target=task, daemon=True).start()


    # 要約を作っている？
    # def _create_character_summary_sync(
    #     self,
    #     session_id: str,
    #     char_name: str,
    #     memory_file: Path,
    # ):
    #     session_char_dir = config.SESSIONS_DIR / session_id / "character"

    #     memory_data = file_utils.load_yaml_file(memory_file) or {}
    #     memory_block = memory_data.get("memory", {})
    #     if not isinstance(memory_block, dict):
    #         memory_block = {}

    #     summary = {
    #         "history": [],
    #         "progress": [],
    #         "worries": [],
    #     }

    #     for key in ("history", "progress", "worries"):
    #         value = memory_block.get(key, [])
    #         if not value:
    #             continue

    #         prompt_messages = self.prompt_builder.create_edit_summary_prompt(
    #             memory_key=key,
    #             memory_value=value,
    #         )

    #         response_text = self.model_handling_service.send_message(
    #             messages=prompt_messages,
    #             temperature=0.3,
    #             max_tokens=1000,
    #         )

    #         response_text = string_utils.strip_code_block(response_text).strip()

    #         if response_text:
    #             summary[key] = [response_text]

    #     summary_file = session_char_dir / f"{char_name}_summary.yaml"
    #     saved = file_utils.save_yaml_file(summary_file, summary)

    #     if not saved:
    #         raise RuntimeError(f"character summary save failed: {summary_file}")

    #     print(f"[CHAR SUMMARY] saved: {summary_file.name}")


    # def extract_character_parameters_from_mes_example(self, mes_example: str, char_name: str) -> list[dict]:
    #     """
    #     mes_example 内の dynamic_params から、
    #     target == char_name（スペース無視）に一致する param_data を返す。
    #     一致しなければ [] を返す。
    #     """
    #     if not isinstance(mes_example, str) or not mes_example.strip():
    #         return []

    #     try:
    #         parsed = yaml.safe_load(mes_example) or {}
    #     except Exception as e:
    #         print(f"[PARAM WARN] mes_example parse failed: {e}")
    #         return []

    #     if not isinstance(parsed, dict):
    #         return []

    #     dynamic_params = parsed.get("dynamic_params")
    #     if not isinstance(dynamic_params, list):
    #         return []

    #     target_norm = "".join(str(char_name).split())

    #     for item in dynamic_params:
    #         if not isinstance(item, dict):
    #             continue

    #         target = item.get("target")
    #         param_data = item.get("param_data")

    #         if not isinstance(target, str) or not isinstance(param_data, list):
    #             continue

    #         item_target_norm = "".join(target.split())

    #         if item_target_norm == target_norm:
    #             result = []
    #             for param in param_data:
    #                 if not isinstance(param, dict):
    #                     continue

    #                 display_name = param.get("display_name")
    #                 if not display_name:
    #                     continue

    #                 result.append({
    #                     "display_name": display_name,
    #                     "count": param.get("count", 0),
    #                 })
    #             return result

    #     return []

