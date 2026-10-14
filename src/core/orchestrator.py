"""
チャット処理の全体を統括するオーケストレーター
- 新規チャット時の初期化
- チャット時前処理
- 応答作成
- チャット時後処理
- 画像作成
"""

import re
from flask import jsonify, send_file
from pathlib import Path
from config import config
from helpers import response_checker
from services.llm import llm_service
# ヘルパー
from services.systems import pc_operation
from services.template import template

# プロンプト構築
from usecases.chat_execute import ChatExecute
from services.world.world_settings import WorldSettings
from logger import log
# app.pyから呼ばれる処理。
class ChatOrchestrator:
    def __init__(self):
        self.model_handling_service = None
        self.chat_execute = ChatExecute()
        self.chat_settings = WorldSettings()

    # サーバーの起動確認。動くのに最低限必要なものが揃っているかを確かめる。
    # 正常: {"ok": true, "status": "ok"}
    # 異常: {"ok": false, "status": "ng", "message": 理由}（HTTP 503）
    # 応答が無い場合（サーバーが止まっている）は、画面側で「未接続」と判断する
    def health(self):
        try:
            problems = []

            if not config.settings:
                problems.append("設定ファイル(system_settings.yaml)を読めていません")

            if not config.PROMPTS_DIR.is_dir():
                problems.append(f"プロンプトのフォルダがありません: {config.PROMPTS_DIR}")

            config.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

            if problems:
                return self._health_ng(" / ".join(problems))

            return response_checker.response_ok(status="ok")

        except Exception as e:
            log.info(f"[ERROR] health: {type(e).__name__}: {e}")
            return self._health_ng(f"{type(e).__name__}: {e}")

    # 異常の応答。response_error は引数名 status をHTTPステータスに使うので、ここでは直接組み立てる
    def _health_ng(self, message):
        return jsonify({"ok": False, "status": "ng", "message": message}), 503

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

    # 画像ファイルの場所を決める。問題があれば (None, エラーレスポンス) を返す
    # owner_type: character(省略時) / player
    # 保存先: {base_chat_path}/characters|players/icon|standing/{owner_id}/
    def _resolve_image_path(self, base_chat_path, owner_type, image_type, owner_id):

        if not base_chat_path:
            return None, response_checker.response_error("base_chat_pathが未指定です", 400)

        owner_dirs = {"character": "characters", "player": "players"}
        owner_dir = owner_dirs.get(owner_type or "character")
        if owner_dir is None:
            return None, response_checker.response_error("owner_type が不正です", 400)

        # IDはそのままフォルダ名になるので、画面の入力チェックと同じ文字種に限る
        if not owner_id or not re.fullmatch(r"[A-Za-z0-9_]+", owner_id):
            return None, response_checker.response_error("IDは半角英数字と_のみ使用できます", 400)

        base_dir = Path(base_chat_path) / owner_dir

        if image_type == "icon":
            image_path = base_dir / "icon" / owner_id / f"{owner_id}.png"

        elif image_type == "standing":
            image_path = base_dir / "standing" / owner_id / f"{owner_id}_standing.png"

        else:
            return None, response_checker.response_error("image_type が不正です", 400)

        return image_path, None

    # キャラクター・プレイヤーの画像を読み込んで返却
    def load_image(self, base_chat_path, owner_type, image_type, owner_id):

        image_path, error = self._resolve_image_path(base_chat_path, owner_type, image_type, owner_id)
        if error:
            return error

        log.info(image_path)

        if not image_path.exists():
            return response_checker.response_error("画像が存在しません", 404)

        return send_file(image_path)

    # キャラクター・プレイヤーの画像を保存
    def save_image(self, base_chat_path, owner_type, image_type, owner_id, file):

        image_path, error = self._resolve_image_path(base_chat_path, owner_type, image_type, owner_id)
        if error:
            return error

        if file is None:
            return response_checker.response_error("画像ファイルがありません", 400)

        image_path.parent.mkdir(parents=True, exist_ok=True)

        file.save(image_path)

        return response_checker.response_ok(
            message="画像を保存しました",
            path=str(image_path),
        )

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

    # チャット画面用。新規チャット時にセッションフォルダへ退避した画像を返却
    def load_session_image(self, session_id, image_type, character_id):
        return self.chat_execute.load_session_image(session_id, image_type, character_id)
    
    #新しいチャットを開始する為の事前準備ファイルをLLM_CHAT_CONSOLEから持ってくる
    def chat_startup(self, payload):
        return self.chat_execute.chat_startup(payload)
    
    # 新しいチャット
    def new_chat(self, payload):

        result = self.chat_execute.new_chat(payload)
        response, status = result
        log.info("status =", status)
        log.info("json   =", response.get_json())
        log.info("text   =", response.get_data(as_text=True))
        return result
      
    # 発言
    def chat(self, payload):
        return self.chat_execute.chat(payload)

    # 再送。チャット欄の最終発言を送信し直す
    def re_chat(self, payload):
        return self.chat_execute.re_chat(payload)

