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
from memory_builders.prompt_builder import MemoryPromptBuilder
from helpers import string_utils
from helpers import session_cast
from helpers import file_utils
from services.llm.llm_service import ModelHandlingService
from helpers import response_checker
from services.llm import generation_params
from memory_builders import load_init_files
from services.status import status_manager
from constant import PromptsPostprocess
from logger import log

# 初期記憶の進み具合。段階を始めるたびに step() を呼ぶと、状態ファイルに「何段目か」を書く。
# 全段階 = 世界の記憶(1) + メインキャラクター1人につき7段階（要約・場所・分類・服装・所持品・意識・所持金）
CHARACTER_STAGES = 7


class _Progress:
    def __init__(self, session_id: str, main_count: int):
        self.session_id = session_id
        self.total = 1 + CHARACTER_STAGES * main_count
        self.done = 0

    def step(self, label: str):
        """これから label の段階を始める。直前の段階は終わったものとして数える。"""
        status_manager.mark_progress(self.session_id, min(self.done, self.total), self.total, label)
        self.done += 1

    def finish(self):
        status_manager.mark_progress(self.session_id, self.total, self.total, "完了")


# 発言のあとの記憶の更新で、モデルの返事を記憶として受け取れるかを確かめる
def _is_valid_character_memory(data) -> bool:
    return isinstance(data, dict) and isinstance(data.get("現在の状態"), dict)


# 関係性をまとめる。前の関係性は全部残し、新しい関係性のうち、前に無い人（キャラクターID か 名前 で比べる）だけを足す
def _merge_relations(old, new) -> list:
    old = old if isinstance(old, list) else []
    new = new if isinstance(new, list) else []

    def key(item):
        if isinstance(item, dict):
            return str(item.get("キャラクターID") or "") or "".join(str(item.get("名前") or "").split())
        return "".join(str(item).split())

    known = {key(item) for item in old}
    merged = list(old)
    for item in new:
        k = key(item)
        if k and k not in known:
            merged.append(item)
            known.add(k)
    return merged


class MemoryManager:
    def __init__(self):
        self.prompt_builder = MemoryPromptBuilder()
        self.model_handling_service = ModelHandlingService("local")
        # log.info("[MemoryManager] Initialized")

    # 初期記憶の非同期作成
    # 発言のあと、メインキャラクターの記憶を更新する（裏で動かす）。
    # 「今の記憶 ＋ 今回の会話 → 更新した記憶」を、記憶のある人ごとに問い合わせ、character/{ID}_memory.yaml を書き換える。
    # 進行状態は complete_stage=after。画面は終わるまで「発言」を止める。失敗した人の記憶は前のまま残す
    # turn_log: 今回の会話（プレイヤーの発言から、返事・掛け合いまでの履歴の行）
    def update_after_chat(self, session_id: str, cast: Dict, turn_log: list) -> None:
        char_dir = config.SESSIONS_DIR / session_id / "character"
        targets = [
            c for c in (cast.get("characters") or [])
            if c.get("kind") == "character" and (char_dir / f"{c['id']}_memory.yaml").exists()
        ]

        # 画面が問い合わせたときに、もう「更新中」になっているよう、スレッドを起こす前に書く
        status_manager.mark_prepare_processing(session_id, "after")
        status_manager.mark_progress(session_id, 0, len(targets), "準備中")

        participants = "\n".join(
            session_cast.label(p) for p in [cast["player"]] + list(cast.get("characters") or [])
        )

        conversation = "\n".join(
            f"{(item.get('icon_data') or {}).get('character_name') or item.get('speaker', '')}: {item.get('message', '')}"
            for item in turn_log
        )

        def task():
            failed = []
            for no, person in enumerate(targets):
                status_manager.mark_progress(session_id, no, len(targets), f"{person['name']}: 記憶の更新")
                try:
                    self._update_character_memory(char_dir, person, conversation, participants)
                except Exception as e:
                    log.info(f"[MEMORY UPDATE ERROR] {person['id']}: {type(e).__name__}: {e}")
                    failed.append(f"{person['name']}: {e}")

            if failed:
                status_manager.mark_prepare_error(
                    session_id,
                    complete_stage="after",
                    error_stage="character",
                    error_message=" / ".join(failed),
                )
                return

            status_manager.mark_progress(session_id, len(targets), len(targets), "完了")
            status_manager.mark_prepare_ready(session_id, "after")

        Thread(target=task, daemon=True).start()

    # モデルに送り、返事をYAMLとして読む。読めない・形が違う（check が False）ときは、1回だけ聞き直す。
    # 2回とも読めなければ ValueError。label はログと失敗の文に使う段階の名前
    def _ask_yaml(self, parameters, label: str, check=None):
        for attempt in (1, 2):
            response_text = string_utils.strip_code_block(self.model_handling_service.send_message(parameters) or "")
            log.info(f"[{label}] 返事", response_text)
            try:
                data = yaml.safe_load(response_text)
            except yaml.YAMLError as e:
                log.info(f"[{label}] YAMLとして読めませんでした（{attempt}回目）: {e}")
                continue
            if data is not None and (check is None or check(data)):
                return data
            log.info(f"[{label}] 返事の形が違いました（{attempt}回目）")
        raise ValueError(f"{label}: 返事をYAMLとして読めませんでした（2回聞いた）")

    def _update_character_memory(self, char_dir: Path, person: Dict, conversation: str, participants: str = "") -> None:
        memory_path = char_dir / f"{person['id']}_memory.yaml"
        current = file_utils.load_yaml_file(memory_path)

        prompt_data = file_utils.load_yaml_file(config.POSTPROCESS / PromptsPostprocess.CHARACTER_MEMORY)
        prompt_data = string_utils.fill_template(prompt_data, {
            "character_name": person["name"],
            "current_memory": yaml.safe_dump(current, allow_unicode=True, sort_keys=False).strip(),
            "conversation": conversation,
            "participants": participants,
        })
        prompt_messages = string_utils.build_messages(prompt_data)
        parameters = generation_params.build_send_parameters("memory", messages=prompt_messages, prompt_data=prompt_data)

        # 読めない・「現在の状態」が無いときは、1回だけ聞き直す
        updated = self._ask_yaml(parameters, f"記憶の更新 {person['id']}", check=_is_valid_character_memory)

        # 関係性は、前からいる人を消さない。今回の会話で初めて出てきた人だけを足す
        old_state = current.get("現在の状態") if isinstance(current.get("現在の状態"), dict) else {}
        if "関係性" in old_state:
            updated["現在の状態"]["関係性"] = _merge_relations(old_state.get("関係性"), updated["現在の状態"].get("関係性"))

        file_utils.save_yaml_file(memory_path, updated)
        log.info(f"[MEMORY UPDATE] {person['id']} の記憶を更新しました")

    def create_initial_memory(self, session_id: str) -> str:
        log.info(f"[MEMORY] session_id={session_id} → 初期記憶作成を開始")

        log.info("chat entered memory_manager.py")

        try:
            status_manager.mark_prepare_processing(session_id, "new_chat")

            base_file_obj = load_init_files.load_base_world_yaml(session_id)
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
            log.info("world_file_path", world_file_path)
            world_file_data = file_utils.load_yaml_file(world_file_path)

            # 記憶作成
            self._run_memory_async(session_id, "create", world_file_data)

            return world_file_data["開始メッセージ"]
        except Exception as e:
            log.info(f"[CREATE INITIAL MEMORY ERROR] {type(e).__name__}: {e}")
    
   # 上から呼ばれてる非同期処理
    def _run_memory_async(self, session_id: str, operation: str, world_file_data: Dict) -> str:
        def task():
            current_stage = "world"

            # 世界情報の作成
            try:
                log.info(f"[MEMORY] {operation}処理を実行中... session_id={session_id}")

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

                log.info("character", characters_text)
                log.info("story", story)

                if operation == "create":
                    current_stage = "world"

                    main_count = sum(1 for c in character if isinstance(c, dict) and c.get("参照種別") == "character")
                    progress = _Progress(session_id, main_count)
                    progress.step("世界の記憶")

                    # characterとstoryがセットで入っている？
                    # 世界の初期記憶作成
                    prompt_messages = self.prompt_builder.create_memory_prompt(characters_text, story, start_message)

                    parameters = generation_params.build_send_parameters("memory", messages=prompt_messages, prompt_data=file_utils.load_yaml_file(config.BOOTSTRAP / Bootstrap.WORLD_MEMORY))

                    response_text = self.model_handling_service.send_message(parameters)

                    response_text = string_utils.strip_code_block(response_text)

                    try:
                        parsed_yaml = yaml.safe_load(response_text) or {}
                        if not isinstance(parsed_yaml, dict):
                            parsed_yaml = {}
                        if response_checker.is_invalid_world_memory(parsed_yaml):
                            log.info("[WARN] world_relationships is empty. retry once.")
                            response_text = self.model_handling_service.send_message(parameters)

                            response_text = string_utils.strip_code_block(response_text)
                            parsed_yaml = yaml.safe_load(response_text) or {}
                            if not isinstance(parsed_yaml, dict):
                                parsed_yaml = {}

                            log.info("２回目？返却yamlの内容？\n", parsed_yaml)
                    except Exception as e:
                        log.info(f"[WORLD ERROR] YAML parse failed: {e}")
                        log.info(f"[WORLD ERROR] response_text head: {response_text[:500]!r}")
                        parsed_yaml = {}
                    # 何のために必要なのか忘れた
                    # プレイヤーは、世界の登場人物の player から取る（固定の名前を書かない）
                    player = session_cast.load_cast(session_id)["player"]
                    player_id = player["id"]
                    player_name = player["name"]

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
                        log.info(f"[WORLD ERROR] response_text head: {response_text[:500]!r}")
                        log.info(f"[WORLD ERROR] parsed_yaml: {parsed_yaml!r}")
                        raise ValueError("world_relationships is empty")

                    world_memory_path = config.SESSIONS_DIR / session_id / "world_memory.yaml"

                    log.info("[DEBUG] normalized_memory.現在の状態 =", normalized_memory.get("現在の状態"))
                    log.info("[DEBUG] normalized_memory.世界の状態 =", normalized_memory.get("世界の状態"))
                    log.info("[DEBUG] world_memory_path =", world_memory_path)

                    saved = file_utils.save_yaml_file(world_memory_path, normalized_memory)
                    if not saved:
                        raise RuntimeError(f"world memory save failed: {world_memory_path}")

                elif operation == "update":
                    # 既存update処理
                    pass

            except Exception as e:
                log.info(f"[MEMORY LOGIC ERROR] {type(e).__name__}: {e}")
                import traceback
                log.info(traceback.format_exc())

                status_manager.mark_prepare_error(
                    session_id,
                    error_stage=current_stage,
                    error_message=f"{type(e).__name__}: {e}",
                    complete_stage="new_chat",
                )

                # 世界の記憶が無いとキャラクターの記憶は作れないので、ここで止める。
                # 続けると、次の段階が状態を ready で上書きしたうえで別のエラーになり、本当の原因(world)が消える
                return

            # ここからキャラクター情報の作成
            try:
                if operation == "create":
                    current_stage = "character"

                    base_file_obj = load_init_files.load_base_character_yaml(session_id)

                    # キャラメモリ作成
                    # LocalLLMだとモデル性能が足りないので細かく
                    self._run_character_memory_create_sync(
                        session_id,
                        world_file_data["登場人物"]["世界の登場人物"],
                        world_file_data["シナリオ本文"],
                        world_file_data["開始メッセージ"],
                        world_file_data["シナリオパラメータ"],
                        base_file_obj,
                        normalized_memory,
                        progress,
                    )

                    # 世界の記憶とキャラクターの記憶が全部できてから ready にする
                    # （ready = 初期記憶が完成。それまでは processing のまま）
                    progress.finish()
                    status_manager.mark_prepare_ready(session_id, "new_chat")

            except Exception as e:
                log.info(f"[CHARACTER LOGIC ERROR] {type(e).__name__}: {e}")
                import traceback
                log.info(traceback.format_exc())

                status_manager.mark_prepare_error(
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
        progress: "_Progress" = None,
    ):
        log.info("_run_character_memory_create_sync start")
        # log.info(f"[CHAR MEMORY] relation_names = {relation_names}")

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
                    log.info(f"[CHAR MEMORY] skip mob: {char_id}")
                    continue
                
                # キャラの状況一覧を問い合わせ
                log.info("[CHAR MEMORY MIDDLE SUMMARY] start")
                if progress: progress.step(f"{character.get('表示名') or char_id}: 要約")
                temp_file = self.proc_middle_summary(base_file_obj,
                                                     character,
                                                     char_id,
                                                     scenario,
                                                     scenario_parameter,
                                                     start_message,
                                                     temp_dir,
                                                     session_id,)
                log.info("[CHAR MEMORY MIDDLE SUMMARY] end")

                # 現在の状態(current_state)の作成
                # 場所(location)の特定
                log.info(f"[CHAR MEMORY PLACE] start: ")
                if progress: progress.step(f"{character.get('表示名') or char_id}: 場所")
                location = self.proc_middle_location(base_file_obj, temp_file,)
                log.info(f"[CHAR MEMORY PLACE] end: ")

                # キャラの状況一覧から、分類を判定
                log.info(f"[CHAR MEMORY CATEGORIZE] start: ")
                if progress: progress.step(f"{character.get('表示名') or char_id}: 分類")
                temp_file_path = self.proc_middle_categorize(temp_file,
                                                             base_file_obj,
                                                             temp_dir,
                                                             char_id,
                                                             session_id)
                log.info(f"[CHAR MEMORY CATEGORIZE] end: ")

                temp_file_data = file_utils.load_yaml_file(temp_file_path) or {}
                action = []
                status = []
                mood = []
                for temp_file_str in temp_file_data:
                    log.info('temp_file_str["要約元"]', temp_file_str["要約元"])
                    log.info('temp_file_str["分類"]', temp_file_str["分類"])
                    match temp_file_str["分類"]:
                        case "行動":
                            action.append(temp_file_str["要約元"])
                        case "状態":
                            status.append(temp_file_str["要約元"])
                        case "心情":
                            mood.append(temp_file_str["要約元"])

                # キャラの状況一覧から、分類を判定
                # 服装を判定
                log.info(f"[CHAR MEMORY  CLOTHING] start: ")
                if progress: progress.step(f"{character.get('表示名') or char_id}: 服装")
                clothing_data = self.proc_middle_clothing(                                         session_char_dir,
                                                          base_file_obj,
                                                          char_id,)
                log.info(f"[CHAR MEMORY CLOTHING] end: ")

                # 所持品を判定
                log.info(f"[CHAR MEMORY ITEMS] start: ")
                if progress: progress.step(f"{character.get('表示名') or char_id}: 所持品")
                item_data = self.proc_middle_items(                                         session_char_dir,
                                                          base_file_obj,
                                                          char_id,
                                                          clothing_data,
                                                          location,
                                                          temp_file)
                log.info(f"[CHAR MEMORY ITEMS] end: ")

                # 意識（forcus_target）の特定（多分作成済み）
                log.info(f"[CHAR MEMORY TARGET] start: ")
                
                if progress: progress.step(f"{character.get('表示名') or char_id}: 意識")
                target_data = self.proc_middle_target(                                         base_file_obj,
                                                          character["表示名"],
                                                          world_memory_data,
                                                          start_message)
                target_list = []
                target_list.append(target_data["相手"])
                log.info(f"[CHAR MEMORY TARGET] end: ")

                # 所持金（currency）の特定
                log.info(f"[CHAR MEMORY CURRENCY] start: ")
                if progress: progress.step(f"{character.get('表示名') or char_id}: 所持金")
                currency_data = self.proc_middle_currency(                                         session_char_dir,
                                                        base_file_obj,
                                                        char_id,
                                                        start_message,)
                log.info(f"[CHAR MEMORY CURRENCY] end: ")

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

                log.info("character_memory_save start");
                character_memory_path = config.SESSIONS_DIR / session_id / "character" / f"{char_id}_memory.yaml"
                saved = file_utils.save_yaml_file(character_memory_path, character_memory_obj)
                if not saved:
                    raise RuntimeError(f"character memory save failed: {character_memory_path}")
                log.info("character_memory_save end");
                continue
            except Exception as e:
                log.info(f"[CHAR MEMORY ERROR] {type(e).__name__}: {e}")
                import traceback
                log.info(traceback.format_exc())
                raise

        
        log.info("セッションキャラディレクトリ", session_char_dir);
        log.info("_run_character_memory_create_sync end")

    # 要約の問い合わせ
    def proc_middle_summary(self, 
                            base_file_obj: Dict[str, any] = {},
                            character: Dict[str, any] = {},
                            char_id: str = "",
                            scenario: str = "",
                            scenario_parameter: str = "",
                            start_message: str = "",
                            temp_dir: str = "",
                            session_id: str = ""):
        
        log.info("[CHAR MEMORY MIDDLE SUMMARY] replace start")
        result = self.replace_middle_summary(base_file_obj,
                                             character,
                                             char_id,
                                             scenario,
                                             scenario_parameter,
                                             start_message,)              
        log.info("[CHAR MEMORY MIDDLE SUMMARY] replace end")
        
        log.info("[CHAR MEMORY MIDDLE SUMMARY] send message start")
        # 差し込み口を埋めた system と template で、共通の形に組み立てる（tail_template も送る）
        prompt_messages = string_utils.build_messages({
            **base_file_obj["prompt_data"],
            "system": result["system_prompt"],
            "template": result["template_prompt"],
        })
        parameters = generation_params.build_send_parameters("memory", messages=prompt_messages, prompt_data=base_file_obj["prompt_data"])
        response_text = self.model_handling_service.send_message(parameters)
        response_text = string_utils.strip_code_block(response_text)
        list_input = string_utils.extract_list_items(response_text)
        log.info("[CHAR MEMORY MIDDLE SUMMARY] send message end")
        
        # config.SESSIONS_DIR = files/sessions 前提なら、プロジェクト直下の temp
        temp_file = temp_dir / f"{char_id}_{session_id}_middle.yaml"
        temp_dir.mkdir(parents=True, exist_ok=True)
        # 書き込み
        log.info(f"[CHAR MEMORY MIDDLE SUMMARY] saved: {temp_file}")
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
        # systemの中も置換しないといけないような気がする・・・
        for temp_categorize_str in temp_categorize_data:
            # header ＋ 要約の1行 ＋ tail_template
            prompt_messages = string_utils.build_messages(base_file_obj["prompt_categorize_yaml"], [temp_categorize_str])

            parameters = generation_params.build_send_parameters("memory", messages=prompt_messages, prompt_data=base_file_obj["prompt_categorize_yaml"])

            response_text = self.model_handling_service.send_message(parameters)
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
            log.info("★ 書き込み前", len(data))
            data.extend(categorized_result)
            log.info("★ 書き込み後", len(data))

            # ③ 上書き
            with temp_file_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        
        log.info(f"[CHAR MEMORY CATEGORIZE] saved: {temp_file_path}")

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

        # # systemの中も置換しないといけないような気がする・・・
        prompt_yaml = string_utils.fill_template(base_file_obj["prompt_location_yaml"], {"summary": temp_place_str})

        # # ここでreplaceが必要かな？
        # # 後共通化できそう？
        prompt_messages = string_utils.build_messages(prompt_yaml)
        parameters = generation_params.build_send_parameters("memory", messages=prompt_messages, prompt_data=base_file_obj["prompt_location_yaml"])

        response_text = self.model_handling_service.send_message(parameters)
        response_text = string_utils.strip_code_block(response_text)
        log.info("response_text", response_text)
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

        prompt_yaml = string_utils.fill_template(base_file_obj["prompt_clothing_yaml"], {"character_data": character_data})

        prompt_messages = string_utils.build_messages(prompt_yaml)
        parameters = generation_params.build_send_parameters("memory", messages=prompt_messages, prompt_data=base_file_obj["prompt_clothing_yaml"])

        # 所持品の段階で「服装」を使うので、その欄があることまで確かめる。読めなければ1回だけ聞き直す
        return self._ask_yaml(parameters, "服装", check=lambda d: isinstance(d, dict) and "服装" in d)

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

        prompt_yaml = string_utils.fill_template(base_file_obj["prompt_items_yaml"], {
            "clothing_data": clothing_str,
            "character_data": character_data,
            "location": location,
            "summary": summary_str,
        })

        prompt_messages = string_utils.build_messages(prompt_yaml)
        parameters = generation_params.build_send_parameters("memory", messages=prompt_messages, prompt_data=base_file_obj["prompt_items_yaml"])

        # 読めなければ1回だけ聞き直す
        return self._ask_yaml(parameters, "キャラクターの記憶の段階", check=lambda d: isinstance(d, dict))

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

        prompt_yaml = string_utils.fill_template(base_file_obj["prompt_target_yaml"], {
            "character_name": character_name,
            "participants_data": participants_str,
            "first_message": first_message,
        })

        prompt_messages = string_utils.build_messages(prompt_yaml)
        log.info("置換後", prompt_messages[-1]["content"])
        parameters = generation_params.build_send_parameters("memory", messages=prompt_messages, prompt_data=base_file_obj["prompt_target_yaml"])

        # 読めなければ1回だけ聞き直す
        return self._ask_yaml(parameters, "キャラクターの記憶の段階", check=lambda d: isinstance(d, dict))

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

        prompt_yaml = string_utils.fill_template(base_file_obj["prompt_currency_yaml"], {
            "character_name": character_name,
            "character_data": character_data,
            "first_message": first_message,
        })

        prompt_messages = string_utils.build_messages(prompt_yaml)
        parameters = generation_params.build_send_parameters("memory", messages=prompt_messages, prompt_data=base_file_obj["prompt_currency_yaml"])

        # 読めなければ1回だけ聞き直す
        return self._ask_yaml(parameters, "キャラクターの記憶の段階", check=lambda d: isinstance(d, dict))

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
    def replace_middle_summary(self, 
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
        template_prompt = template_prompt.replace("{scenario_parameter}", scenario_parameter_str or "")
        template_prompt = template_prompt.replace("{first_message}", start_message or "")
        template_prompt = template_prompt.replace("{characters}", relationships_str)

        result = {}
        result["system_prompt"] = system_prompt
        result["template_prompt"] = template_prompt
        return result

    # 次の話者確定（使ってない可能性ある）
    # def create_target_speakers(self, session_id: str, body:  Dict):
    #     log.info(f"[TARGET SPEAKERS] session_id={session_id} → 発言対象確定を開始")
    #     self._run_create_target_speakers(session_id, body)
    #     return ""

    # 次の話者確定（上から呼ばれる）
    # def _run_create_target_speakers(self, session_id: str, body: Dict):
    #     def task():
    #         try:
    #             # log.info("session_id:", session_id, type(session_id))
    #             # log.info("body:", body, type(body))

    #             # プレイヤーの発言が誰の物かを確認するプロンプトを投げる
    #             # yamlのロード
    #             world_memory = file_utils.load_yaml_file(
    #                 config.SESSIONS_DIR / session_id / "world_memory.yaml"
    #             ) or {}
    #             prompt_data = file_utils.load_yaml_file(
    #                 config.PREPROCESS / PromptsPreprocess.PLAYER_IDENTIFICATION
    #             ) or {}

    #             log.info("prompt_path", config.BOOTSTRAP / PromptsPreprocess.PLAYER_IDENTIFICATION)
    #             log.info("prompt_data", prompt_data)

    #             world_participants = string_utils.build_characters_text(world_memory["current_state"]["participants"])

    #             log.info("current participantsの編集後文字列", world_participants)
    #             # log.info("実行プロンプト原文", prompt_data)
    #             system_prompt = prompt_data["system"]
    #             template_prompt = prompt_data["template"]

    #             template_prompt = template_prompt.replace("{characters}", world_participants)
    #             template_prompt = template_prompt.replace("{player_message}", body.get("message", ""))
                
    #             log.info("置換後プロンプト全文", template_prompt)
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

    #             log.info("今回の発話対象", target)

    #             name = body.get("player")
    #             player_name = name.split(": ", 1)[1].split("：", 1)[0]

    #             log.info("player_name", player_name)
    #             character_path = Path(config.SESSIONS_DIR / session_id / "character")

    #             player_path = file_utils.find_character_file(player_name, character_path)

    #             log.info("player_path", player_path)

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

    #             log.info(f"[CREATE TARGET SPEAKERS UPDATE] ")

    #         except Exception as e:
    #             log.info(f"[CREATE TARGET SPEAKERS ERROR] {type(e).__name__}: {e}")

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
    #             log.info("[CHAR UPDATE] _run_character_memory_update_async start")

    #             session_char_dir = config.SESSIONS_DIR / session_id / "character"
    #             session_char_dir.mkdir(parents=True, exist_ok=True)

    #             char_name = character_name.strip()
    #             if not char_name:
    #                 log.info("[CHAR UPDATE] skip empty character_name")
    #                 return

    #             character_file_path = file_utils.find_character_yaml_file(char_name, session_char_dir)
    #             if not character_file_path:
    #                 log.info(f"[CHAR UPDATE] character file not found: {char_name}")
    #                 return
    #             memory_file_path = file_utils.find_character_memory_file(char_name, session_char_dir)
    #             if not memory_file_path:
    #                 log.info(f"[CHAR UPDATE] memory file not found: {char_name}")
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
    #                 log.info(f"[CHAR UPDATE] YAML parse failed: {char_name}: {e}")
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

    #             log.info(f"[CHAR UPDATE] saved: {memory_file_path.name}")

    #         except Exception as e:
    #             log.info(f"[CHAR UPDATE ERROR] {type(e).__name__}: {e}")

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
    #     log.info(f"[MEMORY] session_id={session_id} char={character_name} → 記憶更新を開始")
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

    #         log.info(f"[WORLD] === character sync start ===")
    #         log.info(f"[WORLD] CHAR DIR: {st_char_dir}")
    #         log.info(f"[WORLD] SESSION DIR: {session_char_dir}")

    #         # モブ用テンプレート
    #         mob_template_path = config.TEMPLATES_DIR / Bootstrap.SUB_CHARACTER_TEMPLATE
    #         log.info("[WORLD] TEMPLATE_PATH")
    #         mob_template_data = file_utils.load_yaml_file(mob_template_path) or {}
    #         if not isinstance(mob_template_data, dict):
    #             mob_template_data = {}

    #         for name in world_relation:
    #             if not isinstance(name, str):
    #                 log.info("[WORLD] skip: not string")
    #                 continue

    #             char_name = name.strip()
    #             if not char_name:
    #                 log.info("[WORLD] skip: empty name")
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
    #                     log.info(f"[WORLD] description YAML not found or invalid: {char_name}")
    #                     yaml_data = {
    #                         "名前": {
    #                             "表示名": raw_data.get("name") or char_name,
    #                         }
    #                     }

    #                 file_utils.save_yaml_file(dst_file, yaml_data)
    #                 log.info(f"[WORLD] saved character card yaml: {dst_file}")
    #                 continue

    #             # --------------------------------------------------
    #             # 2. キャラカードが存在しない場合
    #             #    モブ用テンプレートに名前だけ入れて保存する
    #             # --------------------------------------------------
    #             log.info(f"[WORLD] {char_name} no match → create mob character yaml")

    #             if dst_file.exists():
    #                 log.info(f"[MOB] skip existing yaml: {dst_file}")
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
    #             log.info(f"[MOB] saved character yaml: {dst_file}")

    #         log.info(f"[WORLD] === character sync end ===")

    #     except Exception as e:
    #         log.info(f"[WORLD ERROR] {e}")

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

    #     log.info(f"[CHAR SUMMARY] saved: {summary_file.name}")


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
    #         log.info(f"[PARAM WARN] mes_example parse failed: {e}")
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

