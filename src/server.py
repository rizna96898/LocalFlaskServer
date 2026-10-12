from pathlib import Path

from flask import Flask, jsonify
from llama_cpp import Llama
from flask import request
from config import config
from logger import log

app = Flask(__name__)


# 読み込むモデルは system_settings.yaml の local_model_path / local_mode_name で決める
if not config.LOCALMODEL_PATH or not config.LOCALMODEL_NAME:
    raise RuntimeError(
        "local_model_path / local_mode_name が未設定です。"
        "files/settings/system_settings.yaml を確認してください。"
    )

MODEL_PATH = Path(config.LOCALMODEL_PATH) / config.LOCALMODEL_NAME

if not MODEL_PATH.is_file():
    raise RuntimeError(f"モデルファイルが見つかりません: {MODEL_PATH}")


log.info(f"[MODEL_SERVER] モデル読み込み開始: {MODEL_PATH}")

llm = Llama(
    model_path=str(MODEL_PATH),
    n_ctx=4096,
    n_gpu_layers=-1,
    verbose=False,
    reasoning=False,
)

log.info("[MODEL_SERVER] モデル読み込み完了")


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": True,
    })


@app.post("/generate")
def generate():

    data = request.get_json()

    prompt = data.get("prompt")
    temperature = data.get("temperature")
    top_p = data.get("top_p")
    top_k = data.get("top_k")
    repeat_penalty = data.get("repeat_penalty")
    max_tokens = data.get("max_tokens")
    stop = data.get("stop")
    logit_bias = data.get("logit_bias")

    llm.reset()

    response = llm(
        prompt=prompt,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        repeat_penalty=repeat_penalty,
        max_tokens=max_tokens,
        stop=stop,
        logit_bias=logit_bias,
    )

    return jsonify(response)

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=config.LOCALMODEL_SERVER_PORT,
        debug=False,
        use_reloader=False,
    )