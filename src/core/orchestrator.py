"""
チャット処理の全体を統括するオーケストレーター
- 新規チャット時の初期化
- チャット時前処理
- 応答作成
- チャット時後処理
- 画像作成
"""

from flask import jsonify, send_file
from pathlib import Path
from services import llm_service
# ヘルパー
from usecases import pc_operation
from usecases import template
from usecases import chat_settings
from usecases import chat_execute

# 記憶管理
from usecases.memory_manager import MemoryManager

# プロンプト構築
from memory_builders.prompt_builder import PromptBuilder
from usecases.chat_execute import ChatExecute
from usecases.chat_settings import ChatSettings
# app.pyから呼ばれる処理。
class ChatOrchestrator:
    def __init__(self):
        self.model_handling_service = None
        #self.memory_manager = MemoryManager()
        self.chat_execute = ChatExecute()
        self.chat_settings = ChatSettings()
        #self.chat_utils = ChatUtils()
        # print("[Orchestrator] Initialized")

    # folder選択ウィンドウを表示（したかったけど今は使えない）
    def select_base_path(self, payload):
        return pc_operation.select_base_path(payload)

    # folder選択ウィンドウを表示（したかったけど今は使えない）
    def open_system_yaml(self, payload):
        return pc_operation.open_system_yaml(payload)

    # 世界の登場人物設定ファイルテンプレートを読み込んで返却
    def get_template_world_include_player_yaml(self, payload):
        return template.get_template_world_include_player_yaml(payload)
    
    # 世界のクリア条件設定ファイルテンプレートを読み込んで返却
    def get_template_world_goal_setting_yaml(self, payload):
        return template.get_template_world_goal_setting_yaml(payload)

    # 世界設定の設定ファイルテンプレートを読み込んで返却
    def get_template_world_parameter_setting_yaml(self, payload):
        return template.get_template_world_parameter_setting_yaml(payload)
  
    # playerの設定ファイルテンプレートを読み込んで返却
    def get_template_player_yaml(self, payload):
        return template.get_template_player_yaml(payload)

    # キャラクターの設定ファイルテンプレートを読み込んで返却
    def get_template_character_yaml(self, payload):
        return template.get_template_character_yaml(payload)

    # 世界設定を保存
    def save_world_setting(self, payload):
        return self.chat_settings.save_world_setting(payload)

    # 世界設定を読み込んで返却
    def load_world_settings(self, payload):
        return self.chat_settings.load_world_settings(payload)

    # プレイヤー設定を保存
    def save_player_setting(self, payload):
        return self.chat_settings.save_player_setting(payload)

    # キャラクター設定を保存
    def save_character_setting(self, payload):
        return self.chat_settings.save_character_setting(payload)

    # キャラクター設定を読み込んで返却
    def load_character_settings(self, payload):
        return self.chat_settings.load_character_settings(payload)

    # キャラクター画像を読み込んで返却
    def load_image(self, base_chat_path, image_type, character_id):
        
        base_dir = Path(base_chat_path) / "characters"

        if image_type == "icon":
            save_dir = base_dir / "icon" / character_id
            filename = f"{character_id}.png"

        elif image_type == "standing":
            save_dir = base_dir / "standing" / character_id
            filename = f"{character_id}_standing.png"

        else:
            return jsonify({
                "ok": False,
                "message": "image_type が不正です"
            }), 400

        image_path = save_dir / filename

        print(image_path)
        
        if not image_path.exists():
            return jsonify({
                "ok": False,
                "message": "画像が存在しません"
            }), 404

        return send_file(image_path)

    # キャラクター画像を保存
    def save_image(self, base_chat_path, image_type, character_id, file):

        base_dir = Path(base_chat_path) / "characters"

        if image_type == "icon":
            save_dir = base_dir / "icon" / character_id
            filename = f"{character_id}.png"

        elif image_type == "standing":
            save_dir = base_dir / "standing" / character_id
            filename = f"{character_id}_standing.png"

        save_dir.mkdir(parents=True, exist_ok=True)

        save_path = save_dir / filename

        file.save(save_path)

        return jsonify({
            "ok": True,
            "message": "画像を保存しました",
            "path": str(save_path)
        }), 200

    # モデルのロードを行う
    def load_model(self, payload):
        return llm_service.load_model(payload)

    # StabilityMatrix起動確認受け口
    def check_stability(self, payload):
        return llm_service.check_stability(payload)
    
    # セッションリスト一覧を取得して返却
    def load_session_list(self, payload):
        return self.chat_execute.load_session_list(payload)

    # 世界選択
    # 世界の名前、idと、該当世界の保持セッションID・セッション名一覧を返却
    # セッションIDの新規作成はここでは行わない
    def world_start(self, payload):
        return self.chat_execute.world_start(payload)
    
    # セッションの削除
    def delete_session(self, payload):
        return self.chat_execute.delete_session(payload)
    
    # セッションリストから選択した際に、会話履歴を読み込んで返却する
    def selected_session(self, payload):
        return self.chat_execute.selected_session(payload)
    
    # メッセージをクリックした時のページネーション部分を展開して返却
    def selected_message(self, payload):
        return self.chat_execute.selected_message(payload)
    
    #新しいチャットを開始する為の事前準備ファイルをLLM_CHAT_CONSOLEから持ってくる
    def chat_startup(self, payload):
        return self.chat_execute.chat_startup(payload)
    
    # 新しいチャット
    def new_chat(self, payload):
        result = self.chat_execute.new_chat(payload)
        response, status = result
        print("status =", status)
        print("json   =", response.get_json())
        print("text   =", response.get_data(as_text=True))
        return result
      
    # 発言
    def chat(self, payload):
        return self.chat_execute.chat(payload)

    # 再送。チャット欄の最終発言を送信し直す
    def re_chat(self, payload):
        return self.chat_execute.re_chat(payload)

