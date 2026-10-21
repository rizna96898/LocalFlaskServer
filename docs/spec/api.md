# API仕様

<a id="top"></a>

<!-- toc:start -->
**目次**

- [共通ルール](#s1)
  - [呼び出し方](#s1-1)
  - [レスポンスの形](#s1-2)
  - [場所を表す2つの項目](#s1-3)
  - [ID](#s1-4)
- [一覧](#s2)
- [接続・設定画面](#s3)
  - [`GET /health`](#s3-1)
  - [`POST /settings/select_base_path`](#s3-2)
  - [`POST /settings/open_system_yaml`](#s3-3)
  - [`POST /settings/load_model`](#s3-4)
- [テンプレート](#s4)
  - [`POST /settings/get_template_{名前}_yaml`](#s4-1)
- [世界設定](#s5)
  - [`POST /settings/save_world_setting`](#s5-1)
  - [`POST /settings/load_world_settings`](#s5-2)
- [キャラクター設定・プレイヤー設定](#s6)
  - [`POST /settings/save_character_setting`](#s6-1)
  - [`POST /settings/load_character_settings`](#s6-2)
  - [`POST /settings/save_player_setting`](#s6-3)
  - [`POST /settings/load_player_settings`](#s6-4)
  - [一覧と削除について](#s6-5)
- [画像](#s7)
  - [`POST /settings/save_image`](#s7-1)
  - [`GET /settings/load_image/{image_type}/{owner_id}`](#s7-2)
  - [`GET /session_image/{session_id}/{image_type}/{character_id}`](#s7-3)
- [セッション](#s8)
  - [`POST /world_start`](#s8-1)
  - [`POST /load_session_list`](#s8-2)
  - [`POST /chat_startup`](#s8-3)
  - [`POST /new_chat`](#s8-4)
  - [`POST /chat`](#s8-5)
  - [`POST /selected_session`](#s8-6)
  - [`POST /session_status`](#s8-7)
  - [`POST /selected_message`](#s8-8)
  - [`POST /delete_session`](#s8-9)
  - [履歴のファイル](#s8-10)
- [その他](#s9)
  - [`/v1/chat/check_stability`（GET / POST）](#s9-1)
- [要確認の一覧](#s10)
<!-- toc:end -->

サーバー（LocalFlaskServer）が公開し、画面（LLM_CHAT_CONSOLE）が呼ぶAPIの仕様。

**この文書の位置づけ**: 2026-10-12 時点のコードから書き起こした下書き。「コードが今こう動いている」という事実をまとめたもので、
「本来こう動かすつもりだった」という意図とは違う所があるかもしれない。
判断がつかなかった所には **【要確認 Q番号】** を付け、末尾に一覧にしている。
確認が済んだら印を外し、意図と違った所は仕様のほうを正として直す。

作りかけ・未実装・既知の不具合は、この文書ではなく [`../status.md`](../status.md) に書く。

<a id="s1"></a>

## 共通ルール

<div align="right"><a href="#top">▲ 目次へ</a></div>

<a id="s1-1"></a>

### 呼び出し方

<div align="right"><a href="#top">▲ 目次へ</a></div>

- 接続先は画面の「接続環境設定」で決める（未設定なら `http://127.0.0.1:5000`）。
- 特に断りがなければ `POST`、本文は JSON（`Content-Type: application/json`）。
- 画像の保存だけはフォーム送信（`multipart/form-data`）。

<a id="s1-2"></a>

### レスポンスの形

<div align="right"><a href="#top">▲ 目次へ</a></div>

| | 本文 | HTTPステータス |
|---|---|---|
| 成功 | `{"ok": true, ...}` | 200 |
| 失敗 | `{"ok": false, "message": "理由"}` | 400（入力の誤り）／404（対象が無い）／500（サーバー側の失敗） |

- 失敗時の `message` は、そのまま画面に表示できる文にする。
- 入力のYAMLが読めなかった場合などは、`detail` に詳細が入ることがある。
- 画像を返すAPIは、成功時はJSONではなく画像そのもの（`image/png`）を返す。失敗時は上の形のJSON。
- サーバー側では、必ず `helpers/response_checker.py` の `response_ok` / `response_error` を通して返す（`jsonify` をその場で書かない）。
  形を変えるときに、1か所の修正で済むようにするため。

<a id="s1-3"></a>

### 場所を表す2つの項目

<div align="right"><a href="#top">▲ 目次へ</a></div>

| 項目 | 指すもの | 使うAPI |
|---|---|---|
| `base_chat_path` | LLM_CHAT_CONSOLE の置き場所（世界・キャラクター・プレイヤーのYAMLと画像がある） | 設定の保存と読み込み、テンプレート、画像、`/chat_startup` |
| `base_path` | LocalFlaskServer 自身の置き場所 | `/settings/open_system_yaml`、`/settings/load_model` |

どちらも **サーバーを動かしているPCから見たパス** を送る。画面の「接続環境設定」に保存した値を使う。

<a id="s1-4"></a>

### ID

<div align="right"><a href="#top">▲ 目次へ</a></div>

世界ID・キャラクターID・プレイヤーIDは、半角英数字と `_` だけ。そのままファイル名やフォルダ名になる。

<a id="s2"></a>

## 一覧

<div align="right"><a href="#top">▲ 目次へ</a></div>

| パス | 概要 | 呼ぶ画面 |
|---|---|---|
| `GET /health` | サーバーの起動確認 | メイン、設定 |
| `POST /settings/select_base_path` | フォルダ選択ダイアログを開く | 設定 |
| `POST /settings/open_system_yaml` | 設定YAMLをエディタで開く | 設定 |
| `POST /settings/load_model` | モデルの読み込み | 設定 |
| `POST /settings/get_template_*_yaml`（5種） | 入力欄の初期値になるテンプレートを返す | 世界、キャラクター、プレイヤー |
| `POST /settings/save_world_setting` | 世界設定を保存 | 世界 |
| `POST /settings/load_world_settings` | 世界設定を読み込む | 世界 |
| `POST /settings/save_character_setting` | キャラクター設定を保存 | キャラクター |
| `POST /settings/load_character_settings` | キャラクター設定を読み込む | キャラクター |
| `POST /settings/save_player_setting` | プレイヤー設定を保存 | プレイヤー |
| `POST /settings/load_player_settings` | プレイヤー設定を読み込む | プレイヤー |
| `POST /settings/list_settings` | 世界・キャラクター・プレイヤーの一覧を、フォルダから作って返す | 世界、キャラクター、プレイヤー、メイン |
| `POST /settings/delete_setting` | 世界・キャラクター・プレイヤーを、ファイルごと削除する | 世界、キャラクター、プレイヤー |
| `POST /settings/save_image` | アイコン・立ち絵を保存 | キャラクター、プレイヤー |
| `GET /settings/load_image/{種別}/{ID}` | アイコン・立ち絵を返す（編集画面用） | キャラクター、プレイヤー |
| `POST /world_start` | 世界を選ぶ | メイン |
| `POST /load_session_list` | 世界に属するセッションの一覧 | メイン |
| `POST /chat_startup` | セッションを新しく作る | メイン |
| `POST /new_chat` | チャットを開始する | メイン |
| `POST /chat` | 発言する | メイン |
| `POST /selected_session` | セッションを開く（履歴を返す） | メイン |
| `POST /session_status` | セッションの進行状態（初期記憶の進み具合）を返す | メイン |
| `POST /selected_message` | 畳まれた過去の履歴を展開する | メイン |
| `POST /delete_session` | セッションを削除する | メイン |
| `GET /session_image/{セッションID}/{種別}/{キャラクターID}` | チャット画面用のアイコン・立ち絵を返す | メイン |
| `/v1/chat/check_stability` | 画像生成（Stability Matrix）の起動確認 | （呼ばれていない） |

パスは `src/app.py` のルートと、画面側 `js/constant.js` の `API_PATHS` で1対1に対応させる。

---

<a id="s3"></a>

## 接続・設定画面

<div align="right"><a href="#top">▲ 目次へ</a></div>

<a id="s3-1"></a>

### `GET /health`

<div align="right"><a href="#top">▲ 目次へ</a></div>

サーバーが動いているかを確かめる。

動くのに最低限必要なもの（設定ファイル、プロンプトのフォルダ、セッションのフォルダ）が揃っているかを確かめる。

| 状態 | 返却 | HTTP |
|---|---|---|
| 正常 | `{"ok": true, "status": "ok", "model_server": "ok", "model_loaded": true, "model_name": "モデルのファイル名"}` | 200 |
| 起動しているが異常あり | `{"ok": false, "status": "ng", "message": "理由"}` | 503 |
| サーバーが止まっている | 応答なし | — |

- 画面は、この3つを「●接続中」「▲異常」「×未接続」に出し分ける。`status` は、この判別に使うので消さない。
- 正常のときは、モデルサーバー（`src/server.py`）の `/health` にも問い合わせ、読み込み中のモデルを返す。画面は「使用モデル」に出す。
  - `model_server`: モデルサーバーが応答すれば `ok`、応答が無ければ `ng`（2秒で諦める）。モデルサーバーが止まっていても、APサーバーは正常として返す。
  - `model_loaded`: モデルを読み込んでいるか。モデルロードに失敗した直後などは `false`。
  - `model_name`: 読み込み中のモデルのファイル名。分からなければ空。

<a id="s3-2"></a>

### `POST /settings/select_base_path`

<div align="right"><a href="#top">▲ 目次へ</a></div>

**サーバーを動かしているPCの画面に**、フォルダ選択ダイアログを開く。選ばれたパスを返す。

| 項目 | 必須 | 内容 |
|---|---|---|
| `current_path` | 任意 | ダイアログを最初に開く場所。無い・存在しない場合は `C:/` |

- 返却: `{"ok": true, "base_path": "選ばれたパス"}`。キャンセルした場合は空文字。
- 設定画面の「ベースパス」「ベースチャットパス」の両方の「エクスプローラー」ボタンが、このAPIを使う。

<a id="s3-3"></a>

### `POST /settings/open_system_yaml`

<div align="right"><a href="#top">▲ 目次へ</a></div>

`system_settings.yaml` を、**サーバーを動かしているPCで**、関連付けられたエディタで開く。

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_path` | 必須 | LocalFlaskServer の置き場所 |

- 返却: `{"ok": true, "full_path": "開いたファイルのパス"}`
- 失敗: `base_path` が無い（400）、ファイルが無い（404）

<a id="s3-4"></a>

### `POST /settings/load_model`

<div align="right"><a href="#top">▲ 目次へ</a></div>

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_path` | 必須 | LocalFlaskServer の置き場所 |

モデルを替えたとき、モデルサーバーを再起動せずに読み直す。APサーバーは、モデルサーバーの `POST /reload` に読み直しを頼む。

1. モデルサーバーが `system_settings.yaml` を読み直し、`local_model_path` / `local_model_name` のファイルがあるかを確かめる。
   無ければ断る（**今のモデルのまま**）。
2. 今のモデルを**先に捨ててから**、新しいモデルを読み込む（VRAM に2つ載せる余裕が無いため）。
3. 読み込みに失敗したら、モデルが無い状態になる。そのあいだの発言は失敗する（モデルサーバーの `/generate` は 503）。
   もう一度「モデルロード」をするか、モデルサーバーを再起動する。

- 発言の途中なら、その返事ができるまで待ってから入れ替える。
- 大きいモデルは読み込みに数分かかる。APサーバーは最大15分待つ。
- 返却: `{"ok": true, "message": "ロード完了: モデルのファイル名", "model_name": ..., "full_path": "設定YAMLのパス"}`
- 失敗: `base_path` が無い（400）、設定YAMLが無い（404）、モデルの名前が未設定（400）、モデルのファイルが無い（404）、
  読み込みに失敗（500）、モデルサーバーに接続できない（503）、読み込みが時間内に終わらない（504）
- モデルサーバーの待ち受けポート（`local_model_server_port`）を変えたときは、読み直しでは足りない。両方のサーバーを再起動する。

---

<a id="s4"></a>

## テンプレート

<div align="right"><a href="#top">▲ 目次へ</a></div>

<a id="s4-1"></a>

### `POST /settings/get_template_{名前}_yaml`

<div align="right"><a href="#top">▲ 目次へ</a></div>

入力欄の初期値にするテンプレートYAMLの中身を、文字列で返す。

| `{名前}` | 読むファイル（`base_chat_path` からの相対） |
|---|---|
| `world_include_player` | `worlds/template/include_player_template.yaml` |
| `world_goal_setting` | `worlds/template/scenario_goal_setting_template.yaml` |
| `world_parameter_setting` | `worlds/template/scenario_parameter_setting_template.yaml` |
| `player` | `players/template/player_setting_template.yaml` |
| `character` | `characters/template/character_setting_template.yaml` |

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_chat_path` | 必須 | LLM_CHAT_CONSOLE の置き場所 |

- 返却: `{"ok": true, "content": "YAMLの中身"}`。コメント行も含めてそのまま返す。
- 失敗: `base_chat_path` が無い（400）、ファイルが無い（404）

---

<a id="s5"></a>

## 世界設定

<div align="right"><a href="#top">▲ 目次へ</a></div>

<a id="s5-1"></a>

### `POST /settings/save_world_setting`

<div align="right"><a href="#top">▲ 目次へ</a></div>

世界設定を `worlds/settings/{world_id}_world.yaml` に保存する。同じIDがあれば上書きする。

| 項目 | 必須 | 内容 | 保存先のキー |
|---|---|---|---|
| `base_chat_path` | 必須 | | |
| `world_id` | 必須 | 半角英数字と `_` | `世界ID` |
| `world_name` | 必須 | | `世界名` |
| `include_data` | 必須 | 登場人物（YAMLの文字列） | `登場人物` |
| `goal_data` | 必須 | シナリオの目標（YAMLの文字列） | `シナリオの目標` |
| `parameter_data` | 必須 | シナリオパラメータ（YAMLの文字列） | `シナリオパラメータ` |
| `past` / `current` / `future` | 任意 | シナリオ本文 | `シナリオ本文` の `過去` / `現在` / `未来` |
| `purpose` | 任意 | | `目的` |
| `supplement` | 任意 | | `補足` |
| `start_message` | 任意 | チャット開始時に最初に出るメッセージ | `開始メッセージ` |

- 返却: `{"ok": true, "message": "世界設定を保存しました", "path": "保存先"}`
- 失敗（400）: 必須項目が無い・空、IDの文字種が違う、YAMLとして読めない、`player` が1人でない、
  登場人物（`参照種別` が `null` 以外）の `参照ID` が空か文字種が違う（半角英数字と `_`。`inline` も必須）
- **登場人物の表示名の自動補完**: `世界の登場人物` の各人物について、`表示名` が空なら、`参照種別` と `参照ID` から
  プレイヤーまたはキャラクターの設定YAMLを読み、その `名前` → `表示名` を入れて保存する。
- 登場人物が実在するかは、保存時には確かめない。世界画面の「隣のyaml内容を反映」が、`player` と `character` の参照IDを
  画面の一覧と照らし合わせて確かめる。

<a id="s5-2"></a>

### `POST /settings/load_world_settings`

<div align="right"><a href="#top">▲ 目次へ</a></div>

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_chat_path` | 必須 | |
| `world_id` | 必須 | |

- 返却:

  | 項目 | 内容 |
  |---|---|
  | `world_id`、`world_name` | |
  | `include_data` | 登場人物（YAMLの文字列） |
  | `goal_data` | シナリオの目標（YAMLの文字列） |
  | `parameter_data` | シナリオパラメータ（YAMLの文字列） |
  | `past`、`current`、`future` | シナリオ本文 |
  | `purpose`、`supplement`、`start_message` | |

- 項目名は、保存（`/settings/save_world_setting`）で渡す名前と同じ。読み込んだものを、そのまま保存に渡せる。
- 世界YAMLが無い場合は404（`ok: false`）。

---

<a id="s6"></a>

## キャラクター設定・プレイヤー設定

<div align="right"><a href="#top">▲ 目次へ</a></div>

<a id="s6-1"></a>

### `POST /settings/save_character_setting`

<div align="right"><a href="#top">▲ 目次へ</a></div>

キャラクター設定を `characters/settings/{character_id}_setting.yaml` に保存する。

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_chat_path` | 必須 | |
| `character_id` | 必須 | 半角英数字と `_` |
| `character_name` | 必須 | |
| `content` | 必須 | 設定の本文（YAMLの文字列。最上位は「項目: 内容」の形） |

- 返却: `{"ok": true, "message": "キャラクター設定を保存しました", "path": "保存先"}`
- 失敗（400）: 必須項目が無い・空、IDの文字種が違う、YAMLとして読めない、最上位がオブジェクトでない
- **名前欄は画面の入力で上書きする**: `content` に `名前` が書いてあっても、`名前` → `表示名` は `character_name`、
  `名前` → `識別子` は `character_id` で置き換える。`ふりがな` は、無ければ空として足す。

<a id="s6-2"></a>

### `POST /settings/load_character_settings`

<div align="right"><a href="#top">▲ 目次へ</a></div>

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_chat_path` | 必須 | |
| `character_id` | 必須 | |

- 返却: `{"ok": true, "character_id": ..., "character_name": ..., "character_info": "設定YAML全体の文字列"}`
- 設定YAMLが無い場合は404（`ok: false`）。

<a id="s6-3"></a>

### `POST /settings/save_player_setting`

<div align="right"><a href="#top">▲ 目次へ</a></div>

プレイヤー設定を `players/settings/{player_id}_setting.yaml` に保存する。
項目は `player_id`、`player_name`、`content`、`base_chat_path`。動きはキャラクター設定の保存と同じ。

<a id="s6-4"></a>

### `POST /settings/load_player_settings`

<div align="right"><a href="#top">▲ 目次へ</a></div>

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_chat_path` | 必須 | |
| `player_id` | 必須 | 半角英数字と `_` |

- 返却: `{"ok": true, "player_id": ..., "player_name": ..., "player_info": "設定YAML全体の文字列"}`（キャラクターの読み込みと同じ形）
- 失敗: `base_chat_path` が無い・IDの文字種が違う（400）、設定YAMLが無い（404）

<a id="s6-5"></a>

### 一覧と削除について

<div align="right"><a href="#top">▲ 目次へ</a></div>

#### `POST /settings/list_settings`

世界・キャラクター・プレイヤーの一覧を、フォルダのYAMLから作って返す。画面は、一覧を出すたびにこれを呼ぶ。

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_chat_path` | 必須 | |
| `kind` | 必須 | `world` / `character` / `player` |

| `kind` | 読むファイル | `name` に入るもの |
|---|---|---|
| `world` | `worlds/settings/{ID}_world.yaml` | `世界名` |
| `character` | `characters/settings/{ID}_setting.yaml` | `名前` → `表示名` |
| `player` | `players/settings/{ID}_setting.yaml` | `名前` → `表示名` |

- 返却: `{"ok": true, "kind": ..., "items": [{"id": ..., "name": ...}]}`。IDの順に並ぶ。
- IDはファイル名から取る。IDに使えない文字（半角英数字と `_` 以外）のファイルは、一覧に出さない。名前が無ければIDを入れる。
- 失敗: `base_chat_path` が無い・`kind` が違う（400）、`base_chat_path` のフォルダが無い（404）。
  `settings` フォルダが無いだけなら、空の一覧を返す。
- 画面は、受け取った一覧をブラウザ（`world_list`、`char_list`、`player_list`）にも書き、他の処理はそこから読む。

#### `POST /settings/delete_setting`

世界・キャラクター・プレイヤーを、ファイルごと削除する。元に戻せないので、画面は確認のダイアログを出してから呼ぶ。

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_chat_path` | 必須 | |
| `kind` | 必須 | `world` / `character` / `player` |
| `id` | 必須 | 半角英数字と `_` |

| `kind` | 消すもの | 消さないもの |
|---|---|---|
| `world` | `worlds/settings/{ID}_world.yaml` | その世界のセッション（セッション側に世界のコピーがあるので、続きを遊べる） |
| `character` | `characters/settings/{ID}_setting.yaml`、`characters/icon/{ID}/`、`characters/standing/{ID}/` | 進行中のセッション（設定と画像はコピー済み） |
| `player` | `players/settings/{ID}_setting.yaml`、`players/icon/{ID}/`、`players/standing/{ID}/` | 同上 |

- 返却: `{"ok": true, "message": "削除しました", "kind": ..., "id": ...}`
- **世界で使われているキャラクター・プレイヤーは消さない**: 世界の `登場人物` に、同じ `参照種別` と `参照ID` の人物がいれば、
  409 で断る。`message` は「これらの世界で使われているので削除できません: 世界名A、世界名B」で、
  `worlds` に `[{id, name}]` が入る。画面は `message` をそのまま通知に出す。
- 失敗: `base_chat_path` が無い・`kind` が違う・IDの文字種が違う（400）、設定YAMLが無い（404）、
  使っている世界がある（409）、ファイルを消せなかった（500）

---

<a id="s7"></a>

## 画像

<div align="right"><a href="#top">▲ 目次へ</a></div>

画像の置き場所は2系統ある。

| | 場所 | 使う場面 |
|---|---|---|
| 元の画像 | `{base_chat_path}/characters｜players/icon/{ID}/{ID}.png`<br>`{base_chat_path}/characters｜players/standing/{ID}/{ID}_standing.png` | キャラクター画面・プレイヤー画面での編集 |
| セッションに退避した画像 | `files/sessions/{セッションID}/picture/icon/{ID}.png`<br>`files/sessions/{セッションID}/picture/standing/{ID}_standing.png` | チャット画面での表示 |

新規チャット時（`/chat_startup`）に、元の画像をセッションへコピーする。
**チャット画面は退避した画像だけを使う**ので、後からキャラクター画面で画像を変えても、進行中のチャットの見た目は変わらない。
変更後の画像は、次に作るセッションから使われる。

<a id="s7-1"></a>

### `POST /settings/save_image`

<div align="right"><a href="#top">▲ 目次へ</a></div>

フォーム送信（`multipart/form-data`）。

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_chat_path` | 必須 | |
| `owner_type` | 任意 | `character`（省略時）／`player` |
| `owner_id` | 必須 | 半角英数字と `_` |
| `image_type` | 必須 | `icon`／`standing` |
| `file` | 必須 | 画像ファイル |

- 返却: `{"ok": true, "message": "画像を保存しました", "path": "保存先"}`
- 失敗（400）: 項目の欠落、`owner_type`・`image_type`・IDが不正
- 拡張子に関わらず、`.png` という名前で保存する（中身の変換はしない）。
- キャラクターのアイコンは、画面側で正方形（512×512）に切り抜いてから送る。プレイヤーのアイコンと立ち絵は、選んだ画像をそのまま送る。

<a id="s7-2"></a>

### `GET /settings/load_image/{image_type}/{owner_id}`

<div align="right"><a href="#top">▲ 目次へ</a></div>

| 指定 | 必須 | 内容 |
|---|---|---|
| `{image_type}` | 必須 | `icon`／`standing` |
| `{owner_id}` | 必須 | |
| `?base_chat_path=` | 必須 | |
| `?owner_type=` | 任意 | `character`（省略時）／`player` |

- 返却: 画像そのもの
- 失敗: 指定が不正（400）、画像が無い（404）
- 画面側は、保存直後に古い画像が表示されないよう、URLの末尾に毎回違う値（`&v=時刻`）を付けて呼ぶ。

<a id="s7-3"></a>

### `GET /session_image/{session_id}/{image_type}/{character_id}`

<div align="right"><a href="#top">▲ 目次へ</a></div>

チャット画面のアイコンと立ち絵。セッションに退避した画像を返す。

- 返却: 画像そのもの
- 失敗: 指定が不正（400）、画像が無い（404）
- 画像が無い場合、画面は名前の頭文字を表示する。プレイヤーとシステムのメッセージは、画面側で最初から問い合わせない。

---

<a id="s8"></a>

## セッション

<div align="right"><a href="#top">▲ 目次へ</a></div>

セッションは、1つの世界で始めた1回分のチャット。実体は `files/sessions/{セッションID}/` のフォルダで、
全セッションの一覧は `files/systems/sessions_list.yaml` に持つ。

一覧の1件は次の形。

| 項目 | 内容 |
|---|---|
| `session_id` | 自動で振るID（UUID） |
| `display_name` | 表示名。`{世界名}-{連番}` |
| `world_id`、`world_name` | 属する世界 |
| `created_at`、`updated_at` | `2026年10月12日 10:00` の形の文字列 |

<a id="s8-1"></a>

### `POST /world_start`

<div align="right"><a href="#top">▲ 目次へ</a></div>

メイン画面で世界を選んだときに呼ぶ。

| 項目 | 必須 | 内容 |
|---|---|---|
| `world_id` | 必須 | |
| `world_name` | 必須 | |

- 返却: `{"ok": true, "world_id": ..., "world_name": ..., "sessions": [一覧]}`
- サーバー側では何も作らない・変えない。受け取った `world_id` と `world_name` をそのまま返し、その世界のセッション一覧を添えるだけ。
- `/load_session_list` とは別物。こちらは「世界を選んだときの入口」で、あちらは「セッション一覧の読み込み」（画面を開いたときなど）。
  今は返すセッション一覧が同じだが、世界を選んだときにサーバーで準備することができたら、こちらに入れる。
  一覧を作る処理は2つで共通（`ChatExecute._world_sessions`）。

<a id="s8-2"></a>

### `POST /load_session_list`

<div align="right"><a href="#top">▲ 目次へ</a></div>

| 項目 | 必須 | 内容 |
|---|---|---|
| `world_id` | 必須 | |

- 返却: `{"ok": true, "sessions": [その世界のセッション一覧]}`。一覧ファイルが無ければ空の配列。

<a id="s8-3"></a>

### `POST /chat_startup`

<div align="right"><a href="#top">▲ 目次へ</a></div>

セッションを新しく作る。新規チャットの**1段階目**。

| 項目 | 必須 | 内容 |
|---|---|---|
| `world_id` | 必須 | |
| `base_chat_path` | 必須 | |

やること:

1. セッションIDを振り、`files/sessions/{セッションID}/` を作る。
2. 世界YAML（`worlds/settings/{world_id}_world.yaml`）をセッションフォルダへコピーする。
3. 世界YAMLの `登場人物` → `世界の登場人物` を1人ずつ見て、`参照種別` に応じて設定をコピーする。

   | `参照種別` | やること |
   |---|---|
   | `player` | プレイヤー設定YAMLを `character/` へ、アイコンと立ち絵を（あれば）`picture/` へコピー |
   | `character` | キャラクター設定YAMLを `character/` へ、アイコンと立ち絵を（あれば）`picture/` へコピー |
   | `inline` | キャラクターのテンプレートから `character/{参照ID}_setting.yaml` を新しく作り、`表示名` と `識別子` を入れる |

4. `sessions_list.yaml` に1件足す。

- 返却: `{"ok": true, "session_id": ..., "world_id": ..., "world_name": ..., "display_name": ..., "created_at": ..., "updated_at": ...}`
  （日時は一覧ファイルに書いたものと同じ。画面は、作った直後の一覧にこの日時を出す）
- コピーした時点の内容がそのセッションの設定になる。後から元の世界・キャラクター設定を変えても、進行中のセッションには影響しない。
- `display_name` の連番は「同じ世界のセッション数 + 1」。途中のセッションを消すと、同じ名前がもう一度付くことがある。
  識別はセッションIDで行い、一覧では更新日時も並べて出すので、このままでよい。
- アイコンや立ち絵が無い人物がいても、セッションは作れる。無い画像は退避しない（チャット画面は名前の頭文字を出す）。
- プレイヤーの画像も退避し、チャット画面のプレイヤーの吹き出しに出す。
- 退避するのは、プレイヤーとキャラクター（`参照種別` が `character`）の画像だけ。サブ（`inline`）や、会話で現れた人（`guest_N`）は、画像を持たない（頭文字を出す）。
- サブ（`inline`）の人には、今はアイコンを付けない。付けるとしたら、画像生成（StabilityMatrix）の連携（Q37）のときに考える。

<a id="s8-4"></a>

### `POST /new_chat`

<div align="right"><a href="#top">▲ 目次へ</a></div>

チャットを開始する。新規チャットの**2段階目**。

| 項目 | 必須 | 内容 |
|---|---|---|
| `session_id` | 必須 | `/chat_startup` が返したID |

やること:

1. 進行状態のファイル（`prepare_status.yaml`）を作る。
2. 初期記憶の生成を**裏で**始める（世界の記憶、続いてキャラクターの記憶。モデルを何度も呼ぶので時間がかかる）。
3. 世界YAMLの `開始メッセージ` を履歴に書き、返す。裏の生成の終わりは待たない。

- 返却: `{"ok": true, "session_id": ..., "line_id": "1", "message": "開始メッセージ", "icon_data": {"character_id": ..., "character_name": ...}, "player": {"character_id": ..., "character_name": ...}}`
  - `icon_data`: 開始メッセージの発言者（最初のメインキャラクター）。`player`: このセッションのプレイヤー（発言した直後の吹き出しに使う）
- 画面は、このあと `/session_status` で初期記憶ができたかを問い合わせ、できるまで「発言」を止める。

- セッションは `/chat_startup` で作ってあるはず。そのIDのセッション（フォルダ）が無ければ、何も作らずに断る。
- 失敗: `session_id` が無い・文字種が違う（400）、セッションが無い（404）

<a id="s8-5"></a>

### `POST /chat`

<div align="right"><a href="#top">▲ 目次へ</a></div>

| 項目 | 必須 | 内容 |
|---|---|---|
| `session_id` | 必須 | |
| `message` | 必須 | プレイヤーの発言 |

- 返却: `{"ok": true, "session_id": ..., "line_id": ..., "message": "返答", "icon_data": {...}, "player_line_id": ..., "messages": [...], "updated_at": ...}`
  - `messages`: 履歴に足した発言の並び。プレイヤーへの返事と、あれば掛け合いの2行（話しかけ・相手の返事）。
    1件の形は `{"line_id": ..., "message": ..., "icon_data": {...}, "role": "main"}`。画面はこの順に吹き出しにする
  - `line_id`・`message`・`icon_data`: `messages` の1件目（プレイヤーへの返事）と同じ。`player_line_id`: プレイヤーの発言を書いた行の番号
  - `updated_at`: セッション一覧に書いた更新日時
- プレイヤーの発言・返事・掛け合いを、この順で履歴に足す。返事の生成に失敗した場合は、何も履歴に残さない。
  意識の確認や掛け合いで失敗した場合は、掛け合いを無しにして、返事までを残す。
- 返事を返したあと、裏でキャラクターの記憶を更新する（進行状態は `complete_stage` = `after`）。
  画面は `/session_status` で終わりを待ち、それまで「発言」を止める。
- 「再送」のAPIは無い。失敗したら、画面が文章を入力欄に戻すので、もう一度これを呼ぶ。
- 返答の生成そのものは作りかけ。[`../status.md`](../status.md) を参照。

<a id="s8-6"></a>

### `POST /selected_session`

<div align="right"><a href="#top">▲ 目次へ</a></div>

セッションを開く。履歴を返す。

| 項目 | 必須 | 内容 |
|---|---|---|
| `session_id` | 必須 | |

- 返却: `{"ok": true, "session_id": ..., "message_list": [...], "player": {"character_id": ..., "character_name": ...}}`
- `message_list` の1件: `{"line_id": "番号", "message": "本文", "icon_data": {"character_id": ..., "character_name": ...}, "role": ...}`
  - `role`: `player`（プレイヤーの発言）／`main`（キャラクターの発言）／`system`（畳まれた履歴の印）。画面はこれでプレイヤーの吹き出しかを見分ける。
    古い履歴は `role` が無いことがあり、そのときは `character_id` が `player`。
- **履歴は10件ごとに畳む**: 全部は返さず、最後の区切り（10件未満）だけを本文つきで返す。それより前は、10件につき1つ、
  `character_id` が `system` で `message` が区切りの番号（`"1"`、`"2"`…）の「畳まれた印」を返す。
  画面はこの印をクリックすると `/selected_message` で中身を取り寄せる。

  例: 履歴が23件 → 印 `1`（1〜10件目）、印 `2`（11〜20件目）、本文3件（21〜23件目）

- 履歴がちょうど10の倍数のときは、本文が1件も返らず、印だけになる（20件なら印 `1`、`2` のみ）。
  印を開けば見えるので、この動きでよい。

<a id="s8-7"></a>

### `POST /session_status`

<div align="right"><a href="#top">▲ 目次へ</a></div>

セッションの進行状態を返す。画面は、初期記憶を作っている間これを1秒ごとに問い合わせ、プログレスバーを出したり、
「発言」を止めたりする。

| 項目 | 必須 | 内容 |
|---|---|---|
| `session_id` | 必須 | |

- 返却: `{"ok": true, "session_id": ..., "status": ..., "complete_stage": ..., "error_stage": ..., "error_message": ..., "progress": {"done": 3, "total": 8, "label": "白井　結: 分類"}}`
- `status` などの意味は [`chat-flow.md`](chat-flow.md) の「進行状態」。初期記憶を作っている間は、`complete_stage` が `new_chat`、`status` が `processing`。
- 失敗: `session_id` が無い・文字種が違う（400）、セッションに進行状態のファイルが無い（404）

<a id="s8-8"></a>

### `POST /selected_message`

<div align="right"><a href="#top">▲ 目次へ</a></div>

畳まれた履歴の1区切り（10件）を返す。

| 項目 | 必須 | 内容 |
|---|---|---|
| `session_id` | 必須 | |
| `line_id` | 必須 | 区切りの番号（印の `message` と同じ値） |

- 返却: `{"ok": true, "session_id": ..., "message_list": [10件]}`
- 画面は、クリックされた印を、返ってきた10件で置き換える。

<a id="s8-9"></a>

### `POST /delete_session`

<div align="right"><a href="#top">▲ 目次へ</a></div>

| 項目 | 必須 | 内容 |
|---|---|---|
| `session_ids` | 必須 | 削除するセッションIDの配列 |

- 返却: `{"ok": true, "deleted_session_ids": [...], "failed_session_ids": [...]}`
- 1件ずつ、一覧から外し、セッションフォルダ・記憶生成の途中結果（`temp/`）・問い合わせの記録（`logs/{セッションID}/`）を消す。途中で失敗したものは `failed_session_ids` に入り、残りは続ける。
- 一部が失敗しても全体は `ok: true`。画面は2つの配列を見て結果を表示する。

<a id="s8-10"></a>

### 履歴のファイル

<div align="right"><a href="#top">▲ 目次へ</a></div>

`files/sessions/{セッションID}/history.json` に、発言を1件ずつ足していく。

| 項目 | 内容 |
|---|---|
| `t` | 書いた時刻 |
| `speaker` | 発言者のID（実際の人物のID。古い履歴では `player`、`shirai_yui` 固定のものがある） |
| `role` | `player`／`main` |
| `line_id` | |
| `message` | 本文 |
| `icon_data` | `{"character_id": ..., "character_name": ...}` |

- `line_id` は、発言ごとの通し番号（`"1"` から）。書き込むときに、その時点の件数＋1を振る。
  `/new_chat`、`/chat` は、書き込んだ発言の `line_id` を返す。履歴を読み出すAPIも「何件目か」で番号を振るので、両者は一致する。
  （以前に保存された履歴は、全件 `"1"` のまま。読み出しは件数で番号を振り直すので、表示には影響しない）
- セッション一覧の `updated_at` は、発言（`/chat`）が成功するたびに、その時の日時に書き換える。`/chat` も書いた日時（`updated_at`）を返し、
  画面は一覧の「更新」をその日時にする。

---

<a id="s9"></a>

## その他

<div align="right"><a href="#top">▲ 目次へ</a></div>

<a id="s9-1"></a>

### `/v1/chat/check_stability`（GET / POST）

<div align="right"><a href="#top">▲ 目次へ</a></div>

画像生成（Stability Matrix）の起動確認用。

- 返却: `{"ok": true, "message": "起動してないよ。"}`（常にこの返事）
- 画像生成の連携を作るときのために**残す**。生成の前に起動を確かめないと、余計な待ちや処理が発生するため。
- 今は仮の実装で、中身は本物ではない（[`../status.md`](../status.md)）。画面からも呼ばれていない（`API_PATHS` に無い）。
  画像生成の連携を作るときに、本物の起動確認にする。
- パスが他と違って `/v1/chat/` で始まるのは、SillyTavern を改造していた頃の名残。

---

<a id="s10"></a>

## 要確認の一覧

<div align="right"><a href="#top">▲ 目次へ</a></div>

答えが決まっていても、コードに反映するまでは表に残す。反映したら、本文を仕様として書き直し、表から外す。

| 番号 | 対象 | 確認したいこと | 回答・状況 |
|---|---|---|---|
