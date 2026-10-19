"""モデルサーバー(src/server.py)を、偽の llama で動かして確かめる。本物のモデルは読み込まない。

    py -3 .claude/skills/verify-api/scripts/model_server_check.py

確かめること:
- 起動時に、設定のモデルを読み込む
- モデルロード(/reload): 設定を読み直し、今のモデルを捨ててから新しいモデルを読み込む
- ファイルが無いときは、捨てる前に断る（今のモデルのまま）
- 読み込みに失敗したら、モデルが無い状態になり、発言(/generate)は 503 になる
- 発言の途中なら、読み直しはその返事ができるまで待つ
"""
import importlib
import os
import sys
import threading
import time

import _env

_env.utf8_stdout()
_env.run_in_venv(_env.default_sandbox())

import sandbox  # noqa: E402  (venv に入ってから読み込む)


def main() -> int:
    box = sandbox.prepare()
    t = sandbox.Checker()

    models = box.root / "models"
    models.mkdir(exist_ok=True)
    for name in ("a.gguf", "b.gguf", "bad.gguf"):
        (models / name).write_bytes(b"fake")

    def use_model(name, key="local_model_name", n_ctx=None):
        lines = [sandbox.DEFAULT_SETTINGS.rstrip("\n"), f"local_model_path: {models.as_posix()}"]
        if name:
            lines.append(f"{key}: {name}")
        if n_ctx:
            lines.append(f"local_model_n_ctx: {n_ctx}")
        box.settings_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    use_model("a.gguf")

    # 偽の llama: 名前に bad を含むモデルは読み込みに失敗する。捨てた(close)順を控える
    os.chdir(box.server)
    sys.path.insert(0, str(box.root / "fake_llama"))
    sys.path.insert(0, str(box.server / "src"))
    if not sandbox.VERBOSE:
        importlib.import_module("logger.log")._print_safe = lambda *args, **kwargs: None

    import llama_cpp
    events = []
    n_ctx_seen = []

    class TestLlama(llama_cpp.Llama):
        def __init__(self, model_path=None, **kwargs):
            name = os.path.basename(str(model_path))
            if "bad" in name:
                events.append(f"失敗 {name}")
                raise RuntimeError("壊れたモデル")
            super().__init__(model_path=model_path, **kwargs)
            self.name = name
            n_ctx_seen.append(kwargs.get("n_ctx"))
            events.append(f"読込 {name}")

        def close(self):
            events.append(f"破棄 {self.name}")

    llama_cpp.Llama = TestLlama
    server = importlib.import_module("server")
    client = server.app.test_client()

    def health():
        return client.get("/health").get_json() or {}

    def generate():
        return client.post("/generate", json={"prompt": "x", "max_tokens": 1}).status_code

    print("# 起動")
    t.check("起動時に設定のモデルを読み込む", health() == {"status": "ok", "model_loaded": True, "model_name": "a.gguf"}, health())
    t.check("  local_model_n_ctx が未設定なら、n_ctx は 4096", n_ctx_seen[-1:] == [4096], n_ctx_seen)
    t.check("発言できる", generate() == 200)

    print("\n# モデルロード")
    use_model("b.gguf")
    events.clear()
    r = client.post("/reload")
    t.check("別のモデルに替える → 200", r.status_code == 200 and (r.get_json() or {}).get("model_name") == "b.gguf", r.get_json())
    t.check("  今のモデルを捨ててから、新しいモデルを読み込む", events == ["破棄 a.gguf", "読込 b.gguf"], events)
    t.check("  発言できる", generate() == 200)

    use_model("c.gguf")
    events.clear()
    r = client.post("/reload")
    t.check("ファイルが無い → 404", r.status_code == 404, r.get_json())
    t.check("  捨てずに、今のモデルのまま", events == [] and health().get("model_name") == "b.gguf", (events, health()))
    t.check("  発言できる", generate() == 200)

    use_model(None)
    r = client.post("/reload")
    t.check("モデルの名前が未設定 → 400", r.status_code == 400, r.get_json())
    t.check("  今のモデルのまま", health().get("model_name") == "b.gguf", health())

    use_model("bad.gguf")
    events.clear()
    r = client.post("/reload")
    t.check("読み込みに失敗 → 500", r.status_code == 500, r.get_json())
    t.check("  今のモデルは捨てたあと", events == ["破棄 b.gguf", "失敗 bad.gguf"], events)
    t.check("  モデルが無い状態になる", health().get("model_loaded") is False, health())
    t.check("  発言は 503", generate() == 503)

    use_model("a.gguf")
    r = client.post("/reload")
    t.check("もう一度モデルロードすれば戻る", r.status_code == 200 and health().get("model_name") == "a.gguf", health())
    t.check("  発言できる", generate() == 200)

    # 一度に扱える文章の長さ（local_model_n_ctx）を設定で変えられる
    use_model("b.gguf", n_ctx=8192)
    client.post("/reload")
    t.check("local_model_n_ctx を 8192 にすると、モデルロードで n_ctx=8192 で読み込む", n_ctx_seen[-1:] == [8192], n_ctx_seen)

    # 設定項目名の古い名前（local_mode_name）でも読める
    use_model("b.gguf", key="local_mode_name")
    r = client.post("/reload")
    t.check("古い設定項目名 local_mode_name でも読み直せる", r.status_code == 200 and health().get("model_name") == "b.gguf", health())
    use_model("a.gguf")
    client.post("/reload")

    print("\n# 発言との重なり")
    use_model("b.gguf")
    done = []
    with server._llm_lock:          # 発言の途中（モデルを使っている）の代わり
        worker = threading.Thread(target=lambda: done.append(client.post("/reload").status_code))
        worker.start()
        time.sleep(0.5)
        t.check("発言の途中は、読み直しが待つ", not done and health().get("model_name") == "a.gguf", (done, health()))
    worker.join(10)
    t.check("発言が終われば、読み直す", done == [200] and health().get("model_name") == "b.gguf", (done, health()))

    return t.finish()


if __name__ == "__main__":
    sys.exit(main())
