from llama_cpp import Llama
import os
from config import config
import sys
import llama_cpp

current_model_path = None
llm_instance = None
last_mtime = 0

SETTINGS_PATH = "system_settings.yaml"

def get_llm():
    global current_model_path, llm_instance, last_mtime

    # yamlの更新時刻チェック
    mtime = os.path.getmtime(SETTINGS_PATH)

    if mtime != last_mtime:
        config.reload()
        new_path = config.LOCALMODEL_PATH

        if new_path != current_model_path:
            print(f"モデル切替: {current_model_path} → {new_path}")
            llm_instance = None  # 古いモデル解放
            llm_instance = Llama(model_path=new_path)
            current_model_path = new_path

        last_mtime = mtime

    return llm_instance

class LocalLlamaService:
    def __init__(self):
        print("Loading model...")
        print("[PYTHON]", sys.executable)
        print("[CWD]", os.getcwd())
        print("[PID]", os.getpid())
        print("[llama_cpp]", llama_cpp.__file__)
        print("[PATH]", os.environ.get("PATH", "")[:500])

        self.llm = Llama(
            model_path="E:\\LocalFlaskServer\\models\\mythomax\\mythomax-l2-13b.Q5_K_M.gguf",
            n_ctx=4096,
            n_gpu_layers=-1,
            verbose=True,
        )
        print("Model loaded")

    def send_message(self, prompt, **kwargs):
        return self.llm(prompt, **kwargs)