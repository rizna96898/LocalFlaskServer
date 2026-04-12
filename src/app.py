# src/app.py
"""
Flaskサーバーのエントリーポイント
ルーティングと簡単なエラーハンドリングのみを担当
"""
# src/app.py の一番上（他のimportより前に追加）
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# 以下を追加
sys.path.insert(0, str(ROOT_DIR / "src"))

print(f"[DEBUG] Root: {ROOT_DIR}")

from flask import Flask, request, jsonify, Response, make_response, stream_with_context
from flask_cors import CORS
# importを以下に変更
from config import config                    # src/config.py
from core.orchestrator import ChatOrchestrator
import time

app = Flask(__name__)

# これを一番上に書く
CORS(app)

# Orchestratorの初期化
orchestrator = ChatOrchestrator()

@app.after_request
def after_request(response):
    """すべてのレスポンスにCORSヘッダーを手動で付与（強制）"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Allow-Image,X-Debug-Source,X-CSRF-Token,x-csrf-token,x-requested-with')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.post("/v1/chat/completions")
def chat_completions():
    if request.method == "OPTIONS":   # 念のためここにも
        return "", 200
    # 以降は既存の処理...

    """SillyTavernからのメインのチャットリクエスト（安定版）"""
    try:
        body = request.get_json(force=True)
        allow_image = request.headers.get("X-Allow-Image", "false").lower() == "true"

        # デバッグログ（必要に応じて残す）
        print("=== Request Headers ===")
        for key, value in request.headers.items():
            print(f"{key}: {value}")
        print("=====================")
        print("body全量:", body)

        result = orchestrator.handle_chat_completion(body, allow_image)

        # Silly Tavernが期待する形式で返す（シンプルで安定）
        return jsonify(result["response"]), result.get("status_code", 200)

    except Exception as e:
        print(f"[ERROR] /v1/chat/completions: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500

@app.post("/new_chat")
def new_chat():
    """SillyTavernのNew Chat時に呼ばれる初期化処理"""
    if request.method == "OPTIONS":
        return "", 200

    try:
        body = request.get_json(force=True)
        session_id = orchestrator.create_new_session(body)
        
        print("body全量", body)
        return jsonify({
            "status": "ok",
            "session_id": session_id
        }), 200

    except Exception as e:
        print(f"[ERROR] /new_chat: {e}")
        return jsonify({"error": str(e)}), 500


@app.get("/v1/models")
def list_models():
    """SillyTavernのモデル一覧要求へのダミー応答"""
    return jsonify({
        "object": "list",
        "data": [
            {"id": config.DEFAULT_MODEL, "object": "model", "owned_by": "local-proxy"}
        ]
    })

@app.route("/v1/chat/check_stability", methods=["GET", "POST", "OPTIONS"])
def check_stability():
    """Stability Matrixの起動確認（Silly Tavern改造対応）"""
    # OPTIONSプリフライト対応（重要）
    if request.method == "OPTIONS":
        return "", 200

    try:
        result = True
        message = "起動してます。OK"

#        if generateImage.test_communication_confirmation():
#            message = "起動してます。OK"
#        else:
        result = False
        message = "起動してないよ。"

        return jsonify({
            "ok": result,
            "message": message
        }), 200

    except Exception as e:
        print(f"[ERROR] check_stability: {e}")
        return jsonify({
            "ok": False,
            "message": f"チェック中にエラー: {str(e)}"
        }), 500
    
if __name__ == "__main__":
    print(f"Starting RP Backend on http://127.0.0.1:{config.PORT}")
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY が設定されていません。.env ファイルを確認してください。")
    
    #app.run(host="127.0.0.1", port=config.PORT, debug=False)
    app.run(host="127.0.0.1", port=5000, debug=True)