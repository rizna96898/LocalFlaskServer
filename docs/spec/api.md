# API仕様

サーバー（LocalFlaskServer）が公開し、画面（LLM_CHAT_CONSOLE）が呼ぶAPIの仕様。

**この文書の位置づけ**: 2026-10-12 時点のコードから書き起こした下書き。「コードが今こう動いている」という事実をまとめたもので、
「本来こう動かすつもりだった」という意図とは違う所があるかもしれない。
判断がつかなかった所には **【要確認 Q番号】** を付け、末尾に一覧にしている。
確認が済んだら印を外し、意図と違った所は仕様のほうを正として直す。

作りかけ・未実装・既知の不具合は、この文書ではなく [`../status.md`](../status.md) に書く。

## 共通ルール

### 呼び出し方

- 接続先は画面の「接続環境設定」で決める（未設定なら `http://127.0.0.1:5000`）。
- 特に断りがなければ `POST`、本文は JSON（`Content-Type: application/json`）。
- 画像の保存だけはフォーム送信（`multipart/form-data`）。

### レスポンスの形

| | 本文 | HTTPステータス |
|---|---|---|
| 成功 | `{"ok": true, ...}` | 200 |
| 失敗 | `{"ok": false, "message": "理由"}` | 400（入力の誤り）／404（対象が無い）／500（サーバー側の失敗） |

- 失敗時の `message` は、そのまま画面に表示できる文にする。
- 入力のYAMLが読めなかった場合などは、`detail` に詳細が入ることがある。
- 画像を返すAPIは、成功時はJSONではなく画像そのもの（`image/png`）を返す。失敗時は上の形のJSON。
- サーバー側では `helpers/response_checker.py` の `response_ok` / `response_error` で返す。

### 場所を表す2つの項目

| 項目 | 指すもの | 使うAPI |
|---|---|---|
| `base_chat_path` | LLM_CHAT_CONSOLE の置き場所（世界・キャラクター・プレイヤーのYAMLと画像がある） | 設定の保存と読み込み、テンプレート、画像、`/chat_startup` |
| `base_path` | LocalFlaskServer 自身の置き場所 | `/settings/open_system_yaml`、`/settings/load_model` |

どちらも **サーバーを動かしているPCから見たパス** を送る。画面の「接続環境設定」に保存した値を使う。

### ID

世界ID・キャラクターID・プレイヤーIDは、半角英数字と `_` だけ。そのままファイル名やフォルダ名になる。

## 一覧

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
| `POST /settings/save_image` | アイコン・立ち絵を保存 | キャラクター、プレイヤー |
| `GET /settings/load_image/{種別}/{ID}` | アイコン・立ち絵を返す（編集画面用） | キャラクター、プレイヤー |
| `POST /world_start` | 世界を選ぶ | メイン |
| `POST /load_session_list` | 世界に属するセッションの一覧 | メイン |
| `POST /chat_startup` | セッションを新しく作る | メイン |
| `POST /new_chat` | チャットを開始する | メイン |
| `POST /chat` | 発言する | メイン |
| `POST /re_chat` | 再送する | メイン |
| `POST /selected_session` | セッションを開く（履歴を返す） | メイン |
| `POST /selected_message` | 畳まれた過去の履歴を展開する | メイン |
| `POST /delete_session` | セッションを削除する | メイン |
| `GET /session_image/{セッションID}/{種別}/{キャラクターID}` | チャット画面用のアイコン・立ち絵を返す | メイン |
| `/v1/chat/check_stability` | 画像生成（Stability Matrix）の起動確認 | （呼ばれていない） |

パスは `src/app.py` のルートと、画面側 `js/constant.js` の `API_PATHS` で1対1に対応させる。

---

## 接続・設定画面

### `GET /health`

サーバーが動いているかを確かめる。

- 返却: `{"ok": true, "status": "ok"}`
- **【要確認 Q1】** `status: "ok"` は、レスポンスの形を統一する前の名残に見える。画面は `ok` しか見ていない。消してよいか。

### `POST /settings/select_base_path`

**サーバーを動かしているPCの画面に**、フォルダ選択ダイアログを開く。選ばれたパスを返す。

| 項目 | 必須 | 内容 |
|---|---|---|
| `current_path` | 任意 | ダイアログを最初に開く場所。無い・存在しない場合は `C:/` |

- 返却: `{"ok": true, "base_path": "選ばれたパス"}`。キャンセルした場合は空文字。
- 設定画面の「ベースパス」「ベースチャットパス」の両方の「エクスプローラー」ボタンが、このAPIを使う。
- **【要確認 Q2】** ダイアログの題名が、どちらのボタンから開いても「LOCAL_FLASK_SERVER のフォルダを選択」になる。ベースチャットパスを選ぶときも同じ題名でよいか。

### `POST /settings/open_system_yaml`

`system_settings.yaml` を、**サーバーを動かしているPCで**、関連付けられたエディタで開く。

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_path` | 必須 | LocalFlaskServer の置き場所 |

- 返却: `{"ok": true, "full_path": "開いたファイルのパス"}`
- 失敗: `base_path` が無い（400）、ファイルが無い（404）

### `POST /settings/load_model`

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_path` | 必須 | LocalFlaskServer の置き場所 |

- 返却: `{"ok": true, "message": "ロード完了", "full_path": "設定YAMLのパス"}`
- 失敗: `base_path` が無い（400）、設定YAMLが無い（404）
- **【要確認 Q3】** 今は設定YAMLがあることを確かめて「ロード完了」と返すだけで、モデルには何もしていない。
  モデルを読み込むのは、モデルサーバー（`src/server.py`）を起動したとき。このボタンに本来させたかったことは何か
  （モデルサーバーに読み直しを指示する、設定を読み直す、など）。

---

## テンプレート

### `POST /settings/get_template_{名前}_yaml`

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

## 世界設定

### `POST /settings/save_world_setting`

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
- 失敗（400）: 必須項目が無い・空、IDの文字種が違う、YAMLとして読めない
- **登場人物の表示名の自動補完**: `世界の登場人物` の各人物について、`表示名` が空なら、`参照種別` と `参照ID` から
  プレイヤーまたはキャラクターの設定YAMLを読み、その `名前` → `表示名` を入れて保存する。
- **【要確認 Q4】** 登場人物が指すキャラクターやプレイヤーが実在するかは、保存時に確かめていない（存在しなければ表示名が空のまま保存される）。
  実在しないと、後の `/chat_startup` で失敗する。保存時に弾くべきか。

### `POST /settings/load_world_settings`

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_chat_path` | 必須 | |
| `world_id` | 必須 | |

- 返却:

  | 項目 | 内容 |
  |---|---|
  | `world_id`、`world_name` | |
  | `characters` | 登場人物（YAMLの文字列） |
  | `goal_target` | シナリオの目標（YAMLの文字列） |
  | `scenario_parameter` | シナリオパラメータ（YAMLの文字列） |
  | `past`、`now`、`future` | シナリオ本文 |
  | `purpose`、`supplement`、`start_message` | |

- 保存時は `current`、読み込み時は `now` と、同じものの項目名が違う。
  登場人物なども、保存時は `include_data` / `goal_data` / `parameter_data`、読み込み時は `characters` / `goal_target` / `scenario_parameter`。
- **【要確認 Q5】** 保存と読み込みで項目名を揃えるか（揃えるなら画面側も直す）。
- **【要確認 Q6】** 世界YAMLが無い場合、今は入力チェックが無く、サーバー内部のエラー（500、JSONではない）になる。404で返すべきか。

---

## キャラクター設定・プレイヤー設定

### `POST /settings/save_character_setting`

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

### `POST /settings/load_character_settings`

| 項目 | 必須 | 内容 |
|---|---|---|
| `base_chat_path` | 必須 | |
| `character_id` | 必須 | |

- 返却: `{"ok": true, "character_id": ..., "character_name": ..., "character_info": "設定YAML全体の文字列"}`
- **【要確認 Q6】**（世界設定と同じ）設定YAMLが無い場合、500（JSONではない）になる。

### `POST /settings/save_player_setting`

プレイヤー設定を `players/settings/{player_id}_setting.yaml` に保存する。
項目は `player_id`、`player_name`、`content`、`base_chat_path`。動きはキャラクター設定の保存と同じ。

- **【要確認 Q7】** プレイヤー設定を**読み込む**APIが無い（キャラクターにはある）。プレイヤー画面は、ブラウザに保存した内容だけを表示している。
  意図したものか、作り忘れか。

### 一覧と削除について

- **【要確認 Q8】** 世界・キャラクター・プレイヤーの**一覧を返すAPIが無い**。各画面の一覧は、ブラウザの `localStorage`
  （`world_list`、`char_list`、`player_list`）に持っている。そのため、別のブラウザや別のPCで開くと一覧が空になり、
  フォルダにYAMLがあっても表示されない。フォルダの中身から一覧を作るべきか。
- **【要確認 Q9】** **削除するAPIも無い**。各画面の「削除」は、ブラウザの一覧から消すだけで、YAMLや画像のファイルは残る。意図したものか。

---

## 画像

画像の置き場所は2系統ある。

| | 場所 | 使う場面 |
|---|---|---|
| 元の画像 | `{base_chat_path}/characters｜players/icon/{ID}/{ID}.png`<br>`{base_chat_path}/characters｜players/standing/{ID}/{ID}_standing.png` | キャラクター画面・プレイヤー画面での編集 |
| セッションに退避した画像 | `files/sessions/{セッションID}/picture/icon/{ID}.png`<br>`files/sessions/{セッションID}/picture/standing/{ID}_standing.png` | チャット画面での表示 |

新規チャット時（`/chat_startup`）に、元の画像をセッションへコピーする。
**チャット画面は退避した画像だけを使う**ので、後からキャラクター画面で画像を変えても、進行中のチャットの見た目は変わらない。
変更後の画像は、次に作るセッションから使われる。

### `POST /settings/save_image`

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

### `GET /settings/load_image/{image_type}/{owner_id}`

| 指定 | 必須 | 内容 |
|---|---|---|
| `{image_type}` | 必須 | `icon`／`standing` |
| `{owner_id}` | 必須 | |
| `?base_chat_path=` | 必須 | |
| `?owner_type=` | 任意 | `character`（省略時）／`player` |

- 返却: 画像そのもの
- 失敗: 指定が不正（400）、画像が無い（404）
- 画面側は、保存直後に古い画像が表示されないよう、URLの末尾に毎回違う値（`&v=時刻`）を付けて呼ぶ。

### `GET /session_image/{session_id}/{image_type}/{character_id}`

チャット画面のアイコンと立ち絵。セッションに退避した画像を返す。

- 返却: 画像そのもの
- 失敗: 指定が不正（400）、画像が無い（404）
- 画像が無い場合、画面は名前の頭文字を表示する。プレイヤーとシステムのメッセージは、画面側で最初から問い合わせない。

---

## セッション

セッションは、1つの世界で始めた1回分のチャット。実体は `files/sessions/{セッションID}/` のフォルダで、
全セッションの一覧は `files/systems/sessions_list.yaml` に持つ。

一覧の1件は次の形。

| 項目 | 内容 |
|---|---|
| `session_id` | 自動で振るID（UUID） |
| `display_name` | 表示名。`{世界名}-{連番}` |
| `world_id`、`world_name` | 属する世界 |
| `created_at`、`updated_at` | `2026年10月12日 10:00` の形の文字列 |

### `POST /world_start`

メイン画面で世界を選んだときに呼ぶ。

| 項目 | 必須 | 内容 |
|---|---|---|
| `world_id` | 必須 | |
| `world_name` | 必須 | |

- 返却: `{"ok": true, "world_id": ..., "world_name": ..., "sessions": [一覧]}`
- サーバー側では何も作らない・変えない。受け取った `world_id` と `world_name` をそのまま返し、その世界のセッション一覧を添えるだけ。
- **【要確認 Q10】** `/load_session_list` と返す中身がほぼ同じで、`world_name` は必須なのにそのまま返すだけ。
  「世界を選んだ」ことをサーバーが覚える予定があったのか、1つにまとめてよいか。

### `POST /load_session_list`

| 項目 | 必須 | 内容 |
|---|---|---|
| `world_id` | 必須 | |

- 返却: `{"ok": true, "sessions": [その世界のセッション一覧]}`。一覧ファイルが無ければ空の配列。

### `POST /chat_startup`

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
   | `player` | プレイヤー設定YAMLを `character/` へコピー |
   | `character` | キャラクター設定YAMLを `character/` へ、アイコンと立ち絵を `picture/` へコピー |
   | `inline` | キャラクターのテンプレートから `character/{参照ID}.yaml` を新しく作り、`表示名` と `識別子` を入れる |

4. `sessions_list.yaml` に1件足す。

- 返却: `{"ok": true, "session_id": ..., "world_id": ..., "world_name": ..., "display_name": ...}`
- コピーした時点の内容がそのセッションの設定になる。後から元の世界・キャラクター設定を変えても、進行中のセッションには影響しない。
- **【要確認 Q11】** `display_name` の連番は「同じ世界のセッション数 + 1」。途中のセッションを消すと、同じ名前がもう一度付くことがある。
- **【要確認 Q12】** `character` の人物にアイコンか立ち絵が無いと、コピーに失敗してセッション作成全体が失敗する。画像なしでも始められるべきか。
- **【要確認 Q13】** `inline` の人物だけ、ファイル名が `{ID}.yaml` で、他（`{ID}_setting.yaml`）と違う。揃えるべきか。
- **【要確認 Q14】** プレイヤーの画像はコピーしていない（プレイヤーのアイコンをチャットに出す機能が未実装のため）。

### `POST /new_chat`

チャットを開始する。新規チャットの**2段階目**。

| 項目 | 必須 | 内容 |
|---|---|---|
| `session_id` | 必須 | `/chat_startup` が返したID |

やること:

1. 進行状態のファイル（`prepare_status.yaml`）を作る。
2. 初期記憶の生成を**裏で**始める（世界の記憶、続いてキャラクターの記憶。モデルを何度も呼ぶので時間がかかる）。
3. 世界YAMLの `開始メッセージ` を履歴に書き、返す。裏の生成の終わりは待たない。

- 返却: `{"ok": true, "session_id": ..., "line_id": "1", "message": "開始メッセージ", "icon_data": {"character_id": ..., "character_name": ...}}`
- **【要確認 Q15】** 同じセッションに2回呼ぶと、開始メッセージがもう一度履歴に足され、記憶の生成もやり直される。2回目は弾くべきか。

### `POST /chat`

| 項目 | 必須 | 内容 |
|---|---|---|
| `session_id` | 必須 | |
| `message` | 必須 | プレイヤーの発言 |

- 返却: `{"ok": true, "session_id": ..., "line_id": ..., "message": "返答", "icon_data": {...}}`
- プレイヤーの発言と返答を、この順で履歴に足す。返答の生成に失敗した場合は、どちらも履歴に残さない。
- 返答の生成そのものは作りかけ。[`../status.md`](../status.md) を参照。

### `POST /re_chat`

項目と返却の形は `/chat` と同じ。中身は作りかけ。[`../status.md`](../status.md) を参照。

- **【要確認 Q16】** 「再送」の本来の動きは何か。今は、送られた `message` をプレイヤーの発言としてもう一度履歴に足している。
  考えられるのは「最後の返答だけを作り直す（履歴の最後の返答を置き換える）」「最後の発言からやり直す」など。

### `POST /selected_session`

セッションを開く。履歴を返す。

| 項目 | 必須 | 内容 |
|---|---|---|
| `session_id` | 必須 | |

- 返却: `{"ok": true, "session_id": ..., "message_list": [...]}`
- `message_list` の1件: `{"line_id": "番号", "message": "本文", "icon_data": {"character_id": ..., "character_name": ...}}`
- **履歴は10件ごとに畳む**: 全部は返さず、最後の区切り（10件未満）だけを本文つきで返す。それより前は、10件につき1つ、
  `character_id` が `system` で `message` が区切りの番号（`"1"`、`"2"`…）の「畳まれた印」を返す。
  画面はこの印をクリックすると `/selected_message` で中身を取り寄せる。

  例: 履歴が23件 → 印 `1`（1〜10件目）、印 `2`（11〜20件目）、本文3件（21〜23件目）

- **【要確認 Q17】** 履歴がちょうど10の倍数のとき、本文が1件も返らず、印だけになる（20件なら印 `1`、`2` のみ）。
  開いた直後に直近の会話が見えない。最後の10件は本文で返すべきか。

### `POST /selected_message`

畳まれた履歴の1区切り（10件）を返す。

| 項目 | 必須 | 内容 |
|---|---|---|
| `session_id` | 必須 | |
| `line_id` | 必須 | 区切りの番号（印の `message` と同じ値） |

- 返却: `{"ok": true, "session_id": ..., "message_list": [10件]}`
- 画面は、クリックされた印を、返ってきた10件で置き換える。

### `POST /delete_session`

| 項目 | 必須 | 内容 |
|---|---|---|
| `session_ids` | 必須 | 削除するセッションIDの配列 |

- 返却: `{"ok": true, "deleted_session_ids": [...], "failed_session_ids": [...]}`
- 1件ずつ、一覧から外し、セッションフォルダを消す。途中で失敗したものは `failed_session_ids` に入り、残りは続ける。
- 一部が失敗しても全体は `ok: true`。画面は2つの配列を見て結果を表示する。
- **【要確認 Q18】** 一覧にはあるがフォルダが無いセッションは、一覧からは消えるが、`deleted_session_ids` にも `failed_session_ids` にも入らない。
  画面には「削除できた」と伝わらないので、一覧に残って見える可能性がある。

### 履歴のファイル

`files/sessions/{セッションID}/history.json` に、発言を1件ずつ足していく。

| 項目 | 内容 |
|---|---|
| `t` | 書いた時刻 |
| `speaker` | 発言者のID |
| `role` | `player`／`main` |
| `line_id` | |
| `message` | 本文 |
| `icon_data` | `{"character_id": ..., "character_name": ...}` |

- **【要確認 Q19】** `line_id` は、書き込むときは常に `"1"` で、`/chat` などが返す値も常に `"1"`。
  一方、履歴を読み出すAPIは、何件目かの番号を振り直して返す。発言ごとの通し番号にするのが本来の形か。
- **【要確認 Q20】** セッション一覧の `updated_at` は作成時に入るだけで、発言しても更新されない。画面の一覧に出る「更新」は、作成日時のままになる。

---

## その他

### `/v1/chat/check_stability`（GET / POST）

画像生成（Stability Matrix）の起動確認用。

- 返却: `{"ok": true, "message": "起動してないよ。"}`（常にこの返事）
- **【要確認 Q21】** 画面からは呼ばれておらず（`API_PATHS` に無い）、パスも他と違って `/v1/chat/` で始まる。
  SillyTavern を改造していた頃の名残に見える。画像生成の機能を作るときまで残すか、いったん消すか。

---

## 要確認の一覧

| 番号 | 対象 | 確認したいこと |
|---|---|---|
| Q1 | `/health` | `status: "ok"` を消してよいか |
| Q2 | フォルダ選択 | ベースチャットパスを選ぶときも、題名が「LOCAL_FLASK_SERVER のフォルダを選択」でよいか |
| Q3 | `/settings/load_model` | 「モデルロード」ボタンに本来させたかったこと |
| Q4 | 世界設定の保存 | 登場人物が実在するかを保存時に確かめるべきか |
| Q5 | 世界設定 | 保存と読み込みで項目名（`current` と `now` など）を揃えるか |
| Q6 | 設定の読み込み | ファイルが無いとき404で返すべきか（今は500） |
| Q7 | プレイヤー設定 | 読み込むAPIが無いのは意図したものか |
| Q8 | 一覧 | 世界・キャラクター・プレイヤーの一覧を、ブラウザではなくフォルダの中身から作るべきか |
| Q9 | 削除 | 画面の「削除」でファイルも消すべきか |
| Q10 | `/world_start` | `/load_session_list` と分けている意図。まとめてよいか |
| Q11 | セッションの表示名 | 連番が重複しうる点 |
| Q12 | `/chat_startup` | 画像の無いキャラクターでも始められるべきか |
| Q13 | `/chat_startup` | `inline` の人物のファイル名を他と揃えるか |
| Q14 | `/chat_startup` | プレイヤーの画像もセッションへ退避するか |
| Q15 | `/new_chat` | 同じセッションへの2回目の呼び出しを弾くべきか |
| Q16 | `/re_chat` | 「再送」の本来の動き |
| Q17 | 履歴の畳み方 | ちょうど10の倍数のとき、直近が見えない点 |
| Q18 | `/delete_session` | フォルダの無いセッションの扱い |
| Q19 | 履歴 | `line_id` を発言ごとの通し番号にするか |
| Q20 | セッション一覧 | `updated_at` を発言のたびに更新するか |
| Q21 | `/v1/chat/check_stability` | 残すか消すか |
