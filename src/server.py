from pathlib import Path

from flask import Flask, jsonify
from llama_cpp import Llama
from flask import request
from logger import log

app = Flask(__name__)


MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "models"
    / "qween"
    / "Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf"
)


log.info("[MODEL_SERVER] モデル読み込み開始")

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
        port=5001,
        debug=False,
        use_reloader=False,
    )