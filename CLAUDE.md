# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリの位置づけ

ローカルLLMを使ったロールプレイチャットのサーバー側AP（Flask）。画面は別リポジトリ `LLM_CHAT_CONSOLE`（`z:\LLM_CHAT_CONSOLE`、ビルドなしの静的HTML/JS）が担当し、HTTPでこのサーバーを呼ぶ。

2つのリポジトリは次の点で結合しているので、片方を変えるときはもう片方も確認する。

- **APIパス**: `src/app.py` のルートと、Web側 `js/constant.js` の `API_PATHS` が1対1で対応する。追加・改名は両方に入れる。
- **設定ファイルの実体はWeb側にある**: 世界・キャラクター・プレイヤーのYAMLと画像は `LLM_CHAT_CONSOLE` 配下（`worlds/`、`characters/`、`players/`）に保存される。サーバーはリクエストで受け取る `base_chat_path` / `base_path`（Web側の置き場所）を使ってそこを直接読み書きする。
- **YAMLのキーは日本語**: `登場人物` → `世界の登場人物`、`参照ID`、`参照種別`（`player` / `character` / `inline`）、`世界名`、`開始メッセージ`、`シナリオ本文` → `現在` など。Web側のテンプレートYAMLとサーバー側の読み取りコードでキー名を揃える。

## 実行

テスト、リンター、`requirements.txt` は存在しない。動作確認は実際に起動して画面から操作する。

```
python src/app.py        # APサーバー（ポート5000、0.0.0.0）
python src/server.py     # モデルサーバー（ポート5001、127.0.0.1）
```

- 2プロセス構成。`src/server.py` が llama-cpp でGGUFモデルを読み込み `/generate` を公開し、`src/app.py` 側の `LocalModelService` がそこへHTTPで投げる。チャットや記憶生成を動かすには両方の起動が必要。
- `start_flask.bat` はサブPC上での起動用で、`E:\LocalFlaskServer` と `E:\python\python.exe` を前提にしている。`z:` はサブPCの共有フォルダなので、編集はここで行い、実行はサブPC側になる。
- 必要パッケージ: `flask`、`flask_cors`、`pyyaml`、`requests`、`llama_cpp`、`Pillow`。リポジトリ内の `venv/` には入っておらず、起動には使われていない。
- `src/app.py` が `src/` を `sys.path` に追加するので、importは `from helpers import file_utils` のように `src` 直下からの絶対指定で書く（`src.` は付けない）。

## 設定

`files/settings/system_settings.yaml`（gitignore対象、APIキーを含む）を `src/config.py` の `config` シングルトンが読む。`files/sessions/`、`files/settings/`、`temp/`、`logs/`、`*.txt`、`*.log`、`*.gguf` もgitignore対象。

- モデルの切り替えは `open_router_use_flag` / `local_model_use_flag` と、`ModelHandlingService("local" | "openrouter")` の引数で決まる。現在の呼び出し側はすべて `"local"` 固定。
- モデルサーバーのURL（`http://127.0.0.1:5001/generate`）と、`src/server.py` のモデルパスはコードに直書きされている。
- `port` を設定しても `app.run` は5000固定。

## 構成

リクエストは次の層を順に通る。

`src/app.py`（ルート定義のみ） → `core/orchestrator.py`（`ChatOrchestrator`、振り分けのみ） → `usecases/chat_execute.py`（`ChatExecute`、チャット系の本体）または `services/*`

- `services/world/world_settings.py`: 世界・キャラクター・プレイヤー設定の保存と読み込み（Web側フォルダを操作）
- `services/memory/memory_manager.py`: 世界記憶・キャラクター記憶の生成。LLMを何段も呼ぶ
- `services/chat/chat_manager.py`: 本番チャットの応答生成
- `services/llm/llm_service.py`: `ModelHandlingService` が `LocalModelService` / `OpenRouterService` を切り替える。`task_type`（`chat` / `memory` / `judge`）で `max_tokens` が決まる
- `services/status/status_manager.py`: セッションごとの進行状態
- `memory_builders/`、`chat_builders/`: プロンプト組み立て（`prompt_builder.py`）と、用途別の送信パラメーター（`use_*_constant.py`）

### プロンプト

固定プロンプトはすべて `files/prompts/` のYAMLで、コードには書かない。

- `bootstrap/`: 新規チャット時の初期記憶生成
- `chat/01_preprocess/`、`chat/02_main/`、`chat/03_postprocess/`: 発言ごとの前処理・本処理・後処理
- ファイル名は `src/constant.py` の `Bootstrap` / `PromptsPreprocess` / `PromptsMain` / `PromptsPostprocess` に定数として持つ。YAMLを追加・改名したらここも直す。
- YAMLのキーは `system`、`header`、`template`、`tail_template`。`_build_messages` が `header` + 動的部分 + `template` + `tail_template` をuserメッセージに連結する。
- ローカルモデルへは `messages_to_prompt` が `### Instruction:` / `### Response:` 形式の1本の文字列に変換して送る。
- 先頭に `一旦不要` が付くYAMLと `files/prompts/backups/` は現在使っていない。

### セッションのデータ

`files/sessions/{session_id}/` が1セッション。`files/systems/sessions_list.yaml` が全セッションの一覧。

新規チャットは2段階で始まる。

1. `/chat_startup`: `session_id` を採番し、Web側フォルダから世界YAML・登場人物のYAML・画像をセッションフォルダへコピーして、`sessions_list.yaml` に追記する。`参照種別` が `inline` の人物はテンプレートから新規作成する。
2. `/new_chat`: `prepare_status.yaml` を作り、初期記憶の生成を別スレッドで開始して、世界YAMLの `開始メッセージ` を返す。

`prepare_status.yaml` の `status`（`processing` / `ready` / `error`）と `complete_stage`（`new_chat` → `prepare` → `main_chat` → `mob_chat` → `after`）が、非同期処理の進行と次に進めるかどうかの判定に使われる。

### ログ

`logger/log.py` の `log.info(...)` を使う（`print` は使わない。コンソールがcp932のため文字化け対策が入っている）。ローカルモデルへ送るたびに `log.debug_dump_all` が `logs/{ミリ秒}_prompt.txt` と `_params.json` を書き出すので、プロンプトの確認はここを見る。

## 現状の注意点

作りかけの箇所が多い。触る前に次を把握しておく。

- `/chat` の応答は `ChatManager.main_chat` 経由で、話し相手の判定プロンプト（`create_discrimination_prompt`）を投げた結果をそのまま返している。キャラクター名や状況文は `chat_builders/prompt_builder.py` に直書き。
- `chat_execute.py` の `icon_data` や履歴の話者は `shirai_yui` / `白井　結` で固定。
- `/re_chat` はモデルを呼ばず固定文を返す。
- `chat_utils.py` の前処理・後処理（`chat_prepare`、`chat_after` など）と、`chat_execute.py` 後半の `handle_chat_completion` 以降は、どのルートからも呼ばれていない。
- `services/systems/pc_operation.py`、`services/template/template.py`、`services/image/image.py`、`llm_service.py` の `load_model` / `check_stability` はモジュール関数なのに第1引数が `self` で、orchestratorからの呼び出しと引数の数が合わない。`response_checker._json_ok` / `_json_error` も存在しない（実在するのは `response_ok` / `response_error`）。
- `memory_manager.py` に `E:\LocalFlaskServer\debug_chat.log` への直書きがある。
- レスポンスの形が統一されていない（`{"ok": true}`、`{"status": "ok"}`、`{"result": "error"}`、`{"error": ...}`）。Web側の `requestJson` は `ok === false` と `status === "error"` をエラーとして扱う。新しく書くときは `response_checker` の関数を使う。
- ルートの `構成.txt` は初期の構想で、現在のフォルダ構成とは一致しない。
