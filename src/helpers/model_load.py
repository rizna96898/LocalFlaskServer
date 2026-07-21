import os
from llama_cpp import Llama
from helpers import file_utils

current_model_path = None
llm_instance = None
last_mtime = 0

SETTINGS_PATH = "system_settings.yaml"

def get_llm():
    global current_model_path, llm_instance, last_mtime

    # yamlの更新時刻チェック
    mtime = os.path.getmtime(SETTINGS_PATH)

    if mtime != last_mtime:
        settings = file_utils.load_yaml()  # 既存の関数でOK
        new_path = settings["model"]["path"]

        if new_path != current_model_path:
            print(f"モデル切替: {current_model_path} → {new_path}")
            llm_instance = None  # 古いモデル解放
            llm_instance = Llama(model_path=new_path)
            current_model_path = new_path

        last_mtime = mtime

    return llm_instance