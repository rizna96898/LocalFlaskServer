#lord_init_files.py
from config import config
from helpers import file_utils
from constant import Bootstrap

# 世界作成で必要なベースファイル読み込み
def lord_base_world_yaml(session_id: str):
    # ここで必要なファイルをロードして受け渡しに使う
    system_file_path = config.SYSTEM_DIR / f"sessions_list.yaml"    
    prompt_path = config.BOOTSTRAP / Bootstrap.MEMORY_MIDDLE_SUMMERY
    system_file_data = file_utils.load_yaml_file(system_file_path)
    prompt_data = file_utils.load_yaml_file(prompt_path) or {}

    base_file_data = {}
    base_file_data["system_file_data"] = system_file_data
    base_file_data["prompt_data"] = prompt_data
    return base_file_data

#キャラクター作成時に必要なベースファイル読み込みと初期ディレクトリ生成
def lord_base_character_yaml(session_id: str):
    session_dir = config.SESSIONS_DIR / session_id
    session_char_dir = session_dir / "character"
    world_memory_file = session_dir / f"world_memory.yaml"
    prompt_categorize_path = config.BOOTSTRAP / Bootstrap.MEMORY_MIDDLE_CATEGORIZE
    prompt_location_path = config.BOOTSTRAP / Bootstrap.MEMORY_MIDDLE_LOCATION
    prompt_clothing_path = config.BOOTSTRAP / Bootstrap.MEMORY_MIDDLE_CLOTHING
    prompt_items_path = config.BOOTSTRAP / Bootstrap.MEMORY_MIDDLE_ITEMS
    prompt_target_path = config.BOOTSTRAP / Bootstrap.MEMORY_MIDDLE_TARGET
    prompt_currency_path = config.BOOTSTRAP / Bootstrap.MEMORY_MIDDLE_CURRENCY

    prompt_path = config.BOOTSTRAP / Bootstrap.MEMORY_MIDDLE_SUMMERY

    world_memory_data = file_utils.load_yaml_file(world_memory_file) or {}
    prompt_categorize_yaml = file_utils.load_yaml_file(prompt_categorize_path) or {}
    prompt_location_yaml = file_utils.load_yaml_file(prompt_location_path) or {}
    prompt_clothing_yaml = file_utils.load_yaml_file(prompt_clothing_path) or {}
    prompt_items_yaml = file_utils.load_yaml_file(prompt_items_path) or {}
    prompt_target_yaml = file_utils.load_yaml_file(prompt_target_path) or {}
    prompt_currency_yaml = file_utils.load_yaml_file(prompt_currency_path) or {}

    prompt_data = file_utils.load_yaml_file(prompt_path) or {}

    base_file_data = {}
    base_file_data["world_memory_data"] = world_memory_data
    base_file_data["prompt_categorize_yaml"] = prompt_categorize_yaml
    base_file_data["prompt_location_yaml"] = prompt_location_yaml
    base_file_data["prompt_clothing_yaml"] = prompt_clothing_yaml
    base_file_data["prompt_items_yaml"] = prompt_items_yaml
    base_file_data["prompt_target_yaml"] = prompt_target_yaml
    base_file_data["prompt_currency_yaml"] = prompt_currency_yaml
    
    base_file_data["prompt_data"] = prompt_data

    session_char_dir.mkdir(parents=True, exist_ok=True)

    return base_file_data