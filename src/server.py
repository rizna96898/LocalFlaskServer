import gc
import threading
from pathlib import Path

from flask import Flask, jsonify
from llama_cpp import Llama
from flask import request
from config import config
from logger import log

app = Flask(__name__)


# 読み込むモデルは system_settings.yaml の local_model_path / local_model_name で決める
# （PCごとの設定 local_settings.yaml に書いてあれば、そちらが優先。画面でモデルを切り替えるとそこに書かれる）
# （local_model_name の古い名前 local_mode_name も、しばらくは読む）
def _model_path() -> Path:
    model_dir = config.LOCALMODEL_PATH
    model_name = config.LOCALMODEL_NAME

    if not model_dir or not model_name:
        raise RuntimeError(
            "local_model_path / local_model_name が未設定です。"
            "files/settings/system_settings.yaml を確認してください。"
        )

    return Path(model_dir) / model_name


# 読み込んだモデル。モデルロード(/reload)で入れ替えるので、使う間は _llm_lock で守る
llm = None
llm_name = ""
_llm_lock = threading.Lock()


# 作業用領域（KV キャッシュ）の形式の名前と、llama.cpp の型の番号（ggml_type。llama_cpp.GGML_TYPE_* と同じ値）
KV_CACHE_TYPES = {"f16": 1, "q8_0": 8, "q4_0": 2}


# モデルを読み込むときの、作業用領域と flash attention の指定。設定の値が間違っていたら RuntimeError
def _load_options() -> dict:
    kv_type = config.LOCALMODEL_KV_CACHE_TYPE
    if kv_type not in KV_CACHE_TYPES:
        raise RuntimeError(
            f"local_model_kv_cache_type の値が違います: {kv_type}（{' / '.join(KV_CACHE_TYPES)} のどれか）"
        )

    # f16 以外の形式は、flash attention を使わないと llama.cpp が扱えない
    flash_attn = config.LOCALMODEL_FLASH_ATTN or kv_type != "f16"
    return {
        "type_k": KV_CACHE_TYPES[kv_type],
        "type_v": KV_CACHE_TYPES[kv_type],
        "flash_attn": flash_attn,
    }


def _load(model_path: Path, options: dict):
    global llm, llm_name

    log.info(
        f"[MODEL_SERVER] モデル読み込み開始: {model_path}（n_ctx={config.LOCALMODEL_N_CTX}、"
        f"作業用領域={config.LOCALMODEL_KV_CACHE_TYPE}、flash attention={'あり' if options['flash_attn'] else 'なし'}）"
    )

    llm = Llama(
        model_path=str(model_path),
        n_ctx=config.LOCALMODEL_N_CTX,
        n_gpu_layers=-1,
        verbose=False,
        reasoning=False,
        **options,
    )
    llm_name = model_path.name

    log.info("[MODEL_SERVER] モデル読み込み完了")


# 今のモデルを捨てて、メモリ(VRAM)を空ける
def _unload():
    global llm, llm_name

    if llm is not None:
        close = getattr(llm, "close", None)
        if callable(close):
            close()

    llm = None
    llm_name = ""
    gc.collect()


MODEL_PATH = _model_path()

if not MODEL_PATH.is_file():
    raise RuntimeError(f"モデルファイルが見つかりません: {MODEL_PATH}")

_load(MODEL_PATH, _load_options())


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": llm is not None,
        "model_name": llm_name,
    })


# モデルを読み直す。system_settings.yaml を読み直し、local_model_path / local_model_name のモデルにする。
# VRAM に2つ載せる余裕が無いので、今のモデルを先に捨ててから読み込む。
# - ファイルが無いときは、捨てる前に断る（今のモデルのまま）
# - 読み込みに失敗したときは、モデルが無い状態になる（もう一度モデルロードするか、モデルサーバーを再起動する）
# 発言の途中なら、その返事ができるまで待ってから入れ替える
@app.post("/reload")
def reload_model():
    config.reload()

    # 設定の値が間違っていたら、今のモデルを捨てる前に断る
    try:
        model_path = _model_path()
        options = _load_options()
    except RuntimeError as e:
        return jsonify({"ok": False, "message": str(e)}), 400

    if not model_path.is_file():
        return jsonify({
            "ok": False,
            "message": f"モデルファイルが見つかりません（今のモデルのままです）: {model_path}",
            "model_name": llm_name,
        }), 404

    with _llm_lock:
        _unload()
        try:
            _load(model_path, options)
        except Exception as e:
            log.info(f"[MODEL_SERVER] モデル読み込み失敗: {e}")
            _unload()
            return jsonify({
                "ok": False,
                "message": f"モデルの読み込みに失敗しました。今はモデルが読み込まれていません: {e}",
            }), 500

    return jsonify({"ok": True, "message": "モデルを読み込みました", "model_name": llm_name})


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

    # モデルの読み直しと重ならないようにする
    with _llm_lock:
        if llm is None:
            return jsonify({
                "ok": False,
                "message": "モデルが読み込まれていません。設定画面の「モデルロード」をやり直してください。",
            }), 503

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