# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリの位置づけ

ローカルLLMを使ったロールプレイチャットのサーバー側AP（Flask）。画面は別リポジトリ `LLM_CHAT_CONSOLE`（`z:\LLM_CHAT_CONSOLE`、ビルドなしの静的HTML/JS）が担当し、HTTPでこのサーバーを呼ぶ。

**LLM_CHAT_CONSOLE を扱う場合は、先に `z:\LLM_CHAT_CONSOLE\CLAUDE.md` を読み直すこと。** 作業は普段このリポジトリを開いて行い、Web側は追加フォルダとして扱うが、追加フォルダの `CLAUDE.md` は自動では読み込まれない。画面の構成、JSの読み込み順、`localStorage` の使い方、コミット時の注意など、Web側の決まりごとはそちらにしか書いていない。

2つのリポジトリは次の点で結合しているので、片方を変えるときはもう片方も確認する。

- **APIパス**: `src/app.py` のルートと、Web側 `js/constant.js` の `API_PATHS` が1対1で対応する。追加・改名は両方に入れる。
- **設定ファイルの実体はWeb側にある**: 世界・キャラクター・プレイヤーのYAMLと画像は `LLM_CHAT_CONSOLE` 配下（`worlds/`、`characters/`、`players/`）に保存される。サーバーはリクエストで受け取る `base_chat_path`（Web側の置き場所）を使ってそこを直接読み書きする。`base_path` は LocalFlaskServer 自身の置き場所で、設定画面のAPIだけが使う。
- **YAMLのキーは日本語**: `登場人物` → `世界の登場人物`、`参照ID`、`参照種別`（`player` / `character` / `inline`）、`世界名`、`開始メッセージ`、`シナリオ本文` → `現在` など。Web側のテンプレートYAMLとサーバー側の読み取りコードでキー名を揃える。
- **画像の置き場所**: `{base_chat_path}/characters|players/icon/{id}/{id}.png` と `.../standing/{id}/{id}_standing.png`。`/settings/save_image`（フォーム送信）と `/settings/load_image` は `owner_type`（`character` / `player`、省略時は `character`）で保存先を切り替える。場所の決定とIDの文字種チェックは `ChatOrchestrator._resolve_image_path` にまとめてある。

## 実行

テスト、リンター、`requirements.txt` は存在しない。代わりに、検証用のスキルを `.claude/skills/` に置いている。

- `verify-api`: 両リポジトリのコピーと専用の venv を一時フォルダに作り、本物のデータやモデルに触れずにAPIを実際に呼ぶ。`src/` を変更したら、PRの前に `static_check.py --base main` と `api_smoke.py` を通す。APIを足した・形を変えたときは `api_smoke.py` にも確認を足す。
- `verify-ui`: Web側のJSの検査と、Edge を画面なしで起動してのスクリーンショット。

スキルで確かめられないこと（本物のモデルの応答、サブPCでの起動、連続した画面操作）は、PRの説明に「未確認」と書いて、ユーザーに実機での確認を頼む。

```
python src/app.py        # APサーバー（ポート5000、0.0.0.0）
python src/server.py     # モデルサーバー（ポート5001、127.0.0.1）
```

- 2プロセス構成。`src/server.py` が llama-cpp でGGUFモデルを読み込み `/generate` を公開し、`src/app.py` 側の `LocalModelService` がそこへHTTPで投げる。チャットや記憶生成を動かすには両方の起動が必要。
- `start_flask.bat` はサブPC上での起動用で、`E:\LocalFlaskServer` と `E:\python\python.exe` を前提にしている。`z:` はサブPCの共有フォルダなので、編集はここで行い、実行はサブPC側になる。
- 必要パッケージ: `flask`、`flask_cors`、`pyyaml`、`requests`、`llama_cpp`、`Pillow`。リポジトリ内の `venv/` には入っておらず、起動には使われていない。
- `src/app.py` が `src/` を `sys.path` に追加するので、importは `from helpers import file_utils` のように `src` 直下からの絶対指定で書く（`src.` は付けない）。

## 設定

`files/settings/system_settings.yaml`（gitignore対象、APIキーを含む）を `src/config.py` の `config` シングルトンが読む。`files/sessions/`、`files/settings/`、`temp/`、`logs/`、`files/prompts/backups/`、`files/systems/sessions_list.yaml`、`*.txt`、`*.log`、`*.gguf` もgitignore対象。

- 生成の設定（温度、最大トークン数）は `files/settings/generation.yaml`。`files/settings/` は丸ごと gitignore 対象だが、このファイルだけ例外として Git で管理している。**`system_settings.yaml` は絶対にコミットしない**（APIキーが入っている）。
- モデルの切り替えは `open_router_use_flag` / `local_model_use_flag` と、`ModelHandlingService("local" | "openrouter")` の引数で決まる。現在の呼び出し側はすべて `"local"` 固定。
- APサーバーのポートは `port`（未設定なら5000）。Web側の接続先の既定値は `http://127.0.0.1:5000` なので、変える場合は画面の「接続環境設定」も合わせる。
- モデルサーバーが読み込むモデルは `local_model_path`（フォルダ）と `local_mode_name`（ファイル名）で決まる。未設定やファイルが無い場合、`src/server.py` は起動時にエラーで止まる。
- モデルサーバーのポートは `local_model_server_port`（未設定なら5001）。`src/server.py` の待ち受けと、APサーバーからの送信先（`config.LOCALMODEL_SERVER_URL`）の両方がこれを使う。モデルサーバーはAPサーバーと同じPCで動かす前提（`127.0.0.1` 固定）。

## 構成

リクエストは次の層を順に通る。

`src/app.py`（ルート定義のみ） → `core/orchestrator.py`（`ChatOrchestrator`、振り分けのみ） → `usecases/chat_execute.py`（`ChatExecute`、チャット系の本体）または `services/*`

- `services/world/world_settings.py`: 世界・キャラクター・プレイヤー設定の保存と読み込み（Web側フォルダを操作）
- `services/memory/memory_manager.py`: 世界記憶・キャラクター記憶の生成。LLMを何段も呼ぶ
- `services/chat/chat_manager.py`: 本番チャットの応答生成
- `services/llm/llm_service.py`: `ModelHandlingService` が `LocalModelService` / `OpenRouterService` を切り替える。`task_type`（`chat` / `memory` / `judge`）で `max_tokens` が決まる
- `services/status/status_manager.py`: セッションごとの進行状態
- `services/llm/generation_params.py`: モデルへ送る内容（メッセージと生成の設定）を組み立てる `build_send_parameters`。温度や最大トークン数は、コードに書かず `files/settings/generation.yaml` から読む（書き換えは再起動なしで反映）
- `memory_builders/`、`chat_builders/`: プロンプト組み立て（`prompt_builder.py`）

### プロンプト

固定プロンプトはすべて `files/prompts/` のYAMLで、コードには書かない。

- `bootstrap/`: 新規チャット時の初期記憶生成
- `chat/01_preprocess/`、`chat/02_main/`、`chat/03_postprocess/`: 発言ごとの前処理・本処理・後処理
- ファイル名は `src/constant.py` の `Bootstrap` / `PromptsPreprocess` / `PromptsMain` / `PromptsPostprocess` に定数として持つ。YAMLを追加・改名したらここも直す。
- YAMLのキーは `system`、`header`、`template`、`tail_template`。`_build_messages` が `header` + 動的部分 + `template` + `tail_template` をuserメッセージに連結する。
- ローカルモデルへは `messages_to_prompt` が1本の文字列に変換して送る。形式は設定 `local_model_prompt_format` で決まり、既定は `chatml`（`<|im_start|>` で区切る形。返事の出だしに空の思考ブロックを置く）。**形式はモデルに合わせる。`<think>` を `logit_bias` で禁止しない**（空の返事の原因になる。経緯は `docs/spec/prompts.md`）。
- `files/prompts/backups/` は使っていない古いプロンプトの置き場で、Git管理外。

### セッションのデータ

`files/sessions/{session_id}/` が1セッション。`files/systems/sessions_list.yaml` が全セッションの一覧。

新規チャットは2段階で始まる。

1. `/chat_startup`: `session_id` を採番し、Web側フォルダから世界YAML・登場人物のYAML・画像をセッションフォルダへコピーして、`sessions_list.yaml` に追記する。`参照種別` が `inline` の人物はテンプレートから新規作成する。
   退避した画像は `files/sessions/{session_id}/picture/icon/{id}.png` と `picture/standing/{id}_standing.png` に入り、チャット画面は `/session_image/{session_id}/{icon|standing}/{id}` でこれを読む（Web側フォルダの最新の画像は読まない）。プレイヤーの画像は退避していない。
2. `/new_chat`: `prepare_status.yaml` を作り、初期記憶の生成を別スレッドで開始して、世界YAMLの `開始メッセージ` を返す。

`prepare_status.yaml` の `status`（`processing` / `ready` / `error`）と `complete_stage`（`new_chat` → `prepare` → `main_chat` → `mob_chat` → `after`）が、非同期処理の進行と次に進めるかどうかの判定に使われる。

### ログ

`logger/log.py` の `log.info(...)` を使う（`print` は使わない。コンソールがcp932のため文字化け対策が入っている）。ローカルモデルへ送るたびに `log.debug_dump_all` が `logs/{ミリ秒}_prompt.txt` と `_params.json` を書き出すので、プロンプトの確認はここを見る。

## 作業の進め方

- **区切りごとにPRにする**: `main` から作業ブランチを切り、コミット → push → `gh pr create`。PRの説明には、変えたこと・確認したこと・確認できていないことを書く。マージはユーザーの動作確認のあと（`gh pr merge` は許可済みだが、確認を待たずにマージしない）。
- **進め方や範囲は先に確認する**: 何をどこまでやるかを示して、了承を得てから着手する。作業中に見つけた別の不具合は、勝手に直さずに報告し、別のPRにするか相談する。
- **サーバーとWebにまたがる変更は、同名のブランチでPRを2本作る**: 片方だけ新しい状態で使うと動かないので、その旨をPRに書く。
- **コミットに入れるファイルは名前で指定する**: `git add -A` でまとめて入れない。動作確認でユーザーが保存した画像やYAML（Web側の `characters/` など）が作業ツリーに混ざっていることがある。
- **ローカルの `main` を進めるときは `git fetch origin && git branch -f main origin/main && git switch main`**: 先に古い `main` へ切り替えてから `pull` すると、Git管理から外したファイル（`logs/`、`files/prompts/backups/`、`sessions_list.yaml`）が「削除されたファイル」として扱われ、ディスクからも消える。作業ブランチにいる状態から上の手順で進めれば消えない。
- **このファイルもPRごとに直す**: 仕様や構成を変えたら、同じPRで `CLAUDE.md` の該当箇所を更新する。
- コメントアウトされたコードと覚書のコメントは、ユーザーの備忘なので消さない。

## 仕様と現状の文書

このファイルは入口で、仕様の詳細と現状は `docs/` に分けてある。`docs/` は自動では読み込まれないので、下の表に当てはまる作業の前に読むこと。

| 文書 | 中身 | 読む場面 |
|---|---|---|
| `docs/spec/api.md` | APIの一覧、リクエストの項目、レスポンスの形、画像やセッションの決まり | APIを足す・変える前、画面からの呼び出しを変える前 |
| `docs/spec/data.md` | ファイルとフォルダの置き場所、設定YAMLの形、セッションフォルダの中身、サーバーの設定項目 | ファイルの読み書きや、設定YAMLのキーを扱う前 |
| `docs/spec/chat-flow.md` | 世界の選択から発言までの流れ、初期記憶の生成、進行状態 | 新規チャット・発言・記憶の処理を触る前 |
| `docs/spec/prompts.md` | プロンプトYAMLの形、組み立て方、生成の設定、一覧 | プロンプトや、モデルへの送り方を触る前 |
| `docs/status.md` | 仮の実装、未実装、既知の不具合（画面側の分も含む） | チャットの返答・記憶・話者まわりなど、作りかけの箇所を触る前 |
| `z:\LLM_CHAT_CONSOLE\docs\spec\screens.md` | 画面の構成、ブラウザに保存するもの、各画面の操作 | 画面を触る前 |

- **仕様と現状を混ぜない**: 「こう動くべき」は `docs/spec/`、「今はまだこうなっている」は `docs/status.md` に書く。仮の実装を見て、それを仕様だと受け取らない。
- **`docs/spec/` の【要確認】は、ユーザーの意図がまだ確かめられていない所**。コードの動きをそのまま書いただけなので、そこを前提に作り込む前に、ユーザーに意図を聞く。
- **コードが仕様と違っていたら、黙って合わせずに報告する**。仕様のほうが古い・間違っている場合もある。
- 仕様を変えるPRでは `docs/spec/` を、作りかけを直した・残したPRでは `docs/status.md` を、同じPRで更新する。
- **`docs/` の文書を直したら、`py -3 docs/tools/add_toc.py` で目次を作り直す**。各文書の先頭の目次と、見出しの下の「▲ 目次へ」は、このスクリプトが付けている（`<!-- toc:start -->` から `<!-- toc:end -->` の間と、`<a id="s...">`、`<div align="right">` の行）。手では書き換えない。LLM_CHAT_CONSOLE 側の `docs/` も一緒に処理される。
