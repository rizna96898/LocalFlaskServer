# src/app.py
"""
Flaskサーバーのエントリーポイント
ルーティングと簡単なエラーハンドリングのみを担当
"""
from pathlib import Path
import sys
# src/app.py の一番上（他のimportより前に追加）
# 基準を設定
ROOT_DIR = Path(__file__).resolve().parent.parent
# sys.path.insert(0, str(ROOT_DIR))

# 以下を追加
sys.path.insert(0, str(ROOT_DIR / "src"))

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from config import config
from helpers import response_checker
from core.orchestrator import ChatOrchestrator
from logger import log

# flaskの開始
app = Flask(__name__)

# access許可
CORS(app)

# Orchestratorの初期化
orchestrator = ChatOrchestrator()

############################################################################
# ここからメイン画面処理
############################################################################

# server起動確認
@app.get("/health")
def health():
    return response_checker.response_ok(status="ok")

# folder選択ウィンドウを表示（したかったけど今は使えない）
@app.post("/settings/select_base_path")
def select_base_path():
    return orchestrator.select_base_path(request.get_json())

# folder選択ウィンドウを表示（したかったけど今は使えない）
@app.post("/settings/open_system_yaml")
def open_system_yaml():
    return orchestrator.open_system_yaml(request.get_json())

# 世界の登場人物設定ファイルテンプレートを読み込んで返却
@app.post("/settings/get_template_world_include_player_yaml")
def get_template_world_include_player_yaml():
    return orchestrator.get_template_world_include_player_yaml(request.get_json())

# 世界のクリア条件設定ファイルテンプレートを読み込んで返却
@app.post("/settings/get_template_world_goal_setting_yaml")
def get_template_world_goal_setting_yaml():
    return orchestrator.get_template_world_goal_setting_yaml(request.get_json())

# 世界設定の設定ファイルテンプレートを読み込んで返却
@app.post("/settings/get_template_world_parameter_setting_yaml")
def get_template_world_parameter_setting_yaml():
    return orchestrator.get_template_world_parameter_setting_yaml(request.get_json())

# playerの設定ファイルテンプレートを読み込んで返却
@app.post("/settings/get_template_player_yaml")
def get_template_player_yaml():
    return orchestrator.get_template_player_yaml(request.get_json())

# キャラクターの設定ファイルテンプレートを読み込んで返却
@app.post("/settings/get_template_character_yaml")
def get_template_character_yaml():
    return orchestrator.get_template_character_yaml(request.get_json())

# 世界設定を保存
@app.post("/settings/save_world_setting")
def save_world_setting():
    return orchestrator.save_world_setting(request.get_json())

# 世界設定を読み込んで返却
@app.post("/settings/load_world_settings")
def load_world_settings():
    return orchestrator.load_world_settings(request.get_json())

# プレイヤー設定を保存
@app.post("/settings/save_player_setting")
def save_player_setting():
    return orchestrator.save_player_setting(request.get_json())

# キャラクター設定を保存
@app.post("/settings/save_character_setting")
def save_character_setting():
    return orchestrator.save_character_setting(request.get_json())

# キャラクター設定を読み込んで返却
@app.post("/settings/load_character_settings")
def load_character_settings():
    return orchestrator.load_character_settings(request.get_json())

# キャラクター画像を読み込んで返却
@app.get("/settings/load_image/<image_type>/<character_id>")
def load_image(image_type, character_id):
    return orchestrator.load_image(request.args.get("base_chat_path"),
                                   image_type, 
                                   character_id)

# キャラクター画像を保存
@app.post("/settings/save_image") 
def save_image():
    return orchestrator.save_image(request.args.get("base_chat_path"),
                                   request.form.get("image_type"), 
                                   request.form.get("character_id"),
                                   request.files.get("file"))

# モデルのロードを行う
@app.post("/settings/load_model")
def load_model():
    return orchestrator.load_model(request.get_json())

# セッションリスト一覧を取得して返却
@app.post("/load_session_list")
def load_session_list():
    return orchestrator.load_session_list(request.get_json())

# 世界選択
# 世界の名前、idと、該当世界の保持セッションID・セッション名一覧を返却
# セッションIDの新規作成はここでは行わない
@app.post("/world_start")
def world_start():
    return orchestrator.world_start(request.get_json())

# セッションの削除
@app.post("/delete_session")
def delete_session():
    return orchestrator.delete_session(request.get_json())

# セッションリストから選択した際に、会話履歴を読み込んで返却する
@app.post("/selected_session")
def selected_session():
    return orchestrator.selected_session(request.get_json())

# メッセージをクリックした時のページネーション部分を展開して返却
@app.post("/selected_message")
def selected_message():
    return orchestrator.selected_message(request.get_json())

#新しいチャットを開始する為の事前準備ファイルをLLM_CHAT_CONSOLEから持ってくる
@app.post("/chat_startup")
def chat_startup():
    return orchestrator.chat_startup(request.get_json())


# 新しいチャット
@app.post("/new_chat")
def new_chat():
    if request.method == "OPTIONS":
        return "", 200

    return orchestrator.new_chat(request.get_json())

# 発言
@app.post("/chat")
def chat():
    if request.method == "OPTIONS":
        return "", 200

    return orchestrator.chat(request.get_json())

# 再送。チャット欄の最終発言を送信し直す
@app.post("/re_chat")
def re_chat():
    if request.method == "OPTIONS":
        return "", 200
    return orchestrator.re_chat(request.get_json())

# StabilityMatrix起動確認受け口
@app.route("/v1/chat/check_stability", methods=["GET", "POST", "OPTIONS"])
def check_stability():
    return orchestrator.check_stability(request.get_json())

if __name__ == "__main__":
    log.info(f"Starting RP Backend on http://0.0.0.0:{config.PORT}")

    app.run(host="0.0.0.0", port=5000, debug=False)