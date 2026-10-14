# データの仕様

<a id="top"></a>

<!-- toc:start -->
**目次**

- [全体像](#s1)
- [元データ（LLM_CHAT_CONSOLE 配下）](#s2)
  - [世界設定（`{世界ID}_world.yaml`）](#s2-1)
  - [キャラクター設定・プレイヤー設定（`{ID}_setting.yaml`）](#s2-2)
- [実行時データ（LocalFlaskServer の `files/`）](#s3)
  - [セッションフォルダ（`files/sessions/{セッションID}/`）](#s3-1)
  - [セッション一覧（`files/systems/sessions_list.yaml`）](#s3-2)
  - [サーバーの設定（`files/settings/system_settings.yaml`）](#s3-3)
  - [秘密の値（`files/settings/secrets.yaml`）](#s3-4)
  - [生成の設定（`files/settings/generation.yaml`）](#s3-5)
  - [記録と途中結果](#s3-6)
- [要確認の一覧（この文書の分）](#s4)
<!-- toc:end -->

ファイルとフォルダの置き場所、設定YAMLの形。データベースは使わず、すべてファイルで持つ。

**この文書の位置づけ**: 2026-10-12 時点のコードと、テンプレートYAMLに書かれたコメントから書き起こした下書き。
判断がつかなかった所には **【要確認 Q番号】** を付けている（番号は [`api.md`](api.md) からの通し）。
作りかけ・未実装は [`../status.md`](../status.md) に書く。

<a id="s1"></a>

## 全体像

<div align="right"><a href="#top">▲ 目次へ</a></div>

データは2か所に分かれる。

| 場所 | 中身 | 性質 |
|---|---|---|
| LLM_CHAT_CONSOLE 配下 | 世界・キャラクター・プレイヤーの設定と画像 | **元データ**。画面から編集する。Git管理 |
| LocalFlaskServer の `files/sessions/` | セッション（1回分のチャット）ごとのフォルダ | **実行時データ**。チャットを始めるたびに増える。Git管理外 |

新規チャット時に、元データをセッションフォルダへ**コピー**する。
以後そのセッションは、コピーした側だけを使う。元データを後から変えても、進行中のセッションには影響しない。

サーバーは LLM_CHAT_CONSOLE の場所を自分では知らない。画面がリクエストのたびに `base_chat_path` として送る。

<a id="s2"></a>

## 元データ（LLM_CHAT_CONSOLE 配下）

<div align="right"><a href="#top">▲ 目次へ</a></div>

```
LLM_CHAT_CONSOLE/
├─ worlds/
│  ├─ settings/{世界ID}_world.yaml          世界設定
│  ├─ template/                             世界画面の入力欄の初期値（3ファイル）
│  └─ icons/                                パラメーター表示用の画像
├─ characters/
│  ├─ settings/{キャラクターID}_setting.yaml
│  ├─ icon/{ID}/{ID}.png
│  ├─ standing/{ID}/{ID}_standing.png
│  └─ template/character_setting_template.yaml
└─ players/
   ├─ settings/{プレイヤーID}_setting.yaml
   ├─ icon/{ID}/{ID}.png
   ├─ standing/{ID}/{ID}_standing.png
   └─ template/player_setting_template.yaml
```

ファイル名の規則（`_world.yaml`、`_setting.yaml`、`_standing.png`）は、サーバーのコードが前提にしている。

<a id="s2-1"></a>

### 世界設定（`{世界ID}_world.yaml`）

<div align="right"><a href="#top">▲ 目次へ</a></div>

| キー | 中身 |
|---|---|
| `世界ID` | ファイル名と同じID |
| `世界名` | 表示名。セッションの表示名（`{世界名}-{連番}`）にも使う |
| `登場人物` | 下の「登場人物」 |
| `シナリオの目標` | 下の「シナリオの目標」 |
| `シナリオ本文` | `過去`、`現在`、`未来` の3つ |
| `シナリオパラメータ` | 下の「シナリオパラメータ」 |
| `目的`、`補足` | |
| `開始メッセージ` | チャット開始時に最初に表示するメッセージ |

初期記憶の生成に使うのは、`登場人物`、`シナリオ本文` の `現在`、`開始メッセージ`、`シナリオパラメータ`。

#### 登場人物

```yaml
世界の登場人物:
  - 参照種別: player        # player / character / inline / null
    参照ID: kyuya
    表示名: null
    役割: player            # player / main / sub / mob
    職業: カッコウ医院の先生
```

| `参照種別` | 意味 | `参照ID` | `表示名` |
|---|---|---|---|
| `player` | 操作する本人。**1人だけ** | プレイヤーID | 書かない。保存時にプレイヤー設定から入る |
| `character` | キャラクター画面で作ったキャラクター | キャラクターID | 書かない。保存時にキャラクター設定から入る |
| `inline` | その世界だけのサブ・モブ。設定を別に持たない | キャラクターID（その世界の中で決める） | ここに書いた名前を使う |
| `null` | 一覧に入れない | | |

- `役割` は `player`、`main`、`sub`、`mob`。テンプレートのコメントでは「mob は、チャット時にキャラクターカード等を作らない」。
- ここは世界の**初期設定**。テンプレートのコメントでは「チャット中にキャラクターを召喚しても、ここは更新しない」。
- `参照ID` は、`null` 以外の全員に必須（半角英数字と `_`）。新規チャット時にファイル名に使う
  （`character/{参照ID}_setting.yaml`）。`player` と `character` は、そのIDが実在するかも確かめる（世界画面の
  「隣のyaml内容を反映」）。`inline` は実在の確認はしない。保存（`/settings/save_world_setting`）でも、空や文字種違いは弾く。
- **【要確認 Q23】** `役割` による動きの違い（`mob` はカードを作らない、など）は、今のコードには無い。`参照種別` だけで分岐している。
- `player` は必ず1人。世界画面の「隣のyaml内容を反映」と、保存（`/settings/save_world_setting`）の両方で確かめ、
  0人や2人以上なら弾く。

#### シナリオの目標

```yaml
ゴール設定:
  - ゴールID: scenario1
    ゴール名: シナリオ
    使用フラグ: false          # true で有効
    チェックポイント:
      - 種別: 成功              # 成功 / 失敗
        表示名: 成功条件1        # チャット中に表示される
        達成状況: false
```

- 保存と読み込みはできるが、チャット中に使う処理はまだ無い（[`../status.md`](../status.md)）。

#### シナリオパラメータ

```yaml
変動パラメータ:
  - 対象キャラクターID: shirai_yui
    パラメーター:
      - 表示名: playerへの好感度
        数値: 0
        増減幅: 10              # この範囲内で、モデルの判断により変動する
        負数許可: true
        画像: null              # worlds/icons/ に置いた画像のファイル名
```

- テンプレートのコメントから読み取れる決まり:
  - `対象キャラクターID` は、登場人物に入っているキャラクターのID。
  - 表示名の中の `player` という語は書き換えない（処理で実際の名前に置き換える）。
  - `増減幅` は「毎回その値だけ増える」のではなく、「その範囲内でモデルが決める」。
  - 上限・下限は設けない。`負数許可` が `false` なら0未満にしない。
- 新規チャット時に読み込んで記憶生成へ渡しているが、チャット中の変動はまだ無い（[`../status.md`](../status.md)）。

<a id="s2-2"></a>

### キャラクター設定・プレイヤー設定（`{ID}_setting.yaml`）

<div align="right"><a href="#top">▲ 目次へ</a></div>

2つは同じ形。

```yaml
名前:
  表示名: 白井　結        # 画面の「キャラクター名」で上書きされる
  ふりがな: しらい　ゆい
  識別子: shirai_yui     # 画面の「キャラクターID」で上書きされる
基本情報:
  性別: / 年齢: / 職業: / 身長:
外見:
  髪:    色: / 長さ: / 髪型:
  体型:  ...
服装:
  通学時: [...]
  私服:   [...]
好み:
性格:
  基本: [...] / 会話傾向: [...] / 対人傾向: [...]
会話:
  一人称:
```

- **`名前` 以外は自由に書き換えてよい**（テンプレートのコメント）。項目を足しても減らしてもよい。
  サーバーは `名前` → `表示名` と `識別子` だけを決まった場所として読み、それ以外は設定全体をそのままモデルに渡す。
- `名前` の `表示名` と `識別子` は、保存のたびに画面の入力で上書きする。
- 画面の入力欄では、簡易的なチェック（1行に `:` は1つまで、タブ不可）をしてから送る。

<a id="s3"></a>

## 実行時データ（LocalFlaskServer の `files/`）

<div align="right"><a href="#top">▲ 目次へ</a></div>

```
LocalFlaskServer/
├─ files/
│  ├─ prompts/                     プロンプトYAML（→ prompts.md）。Git管理
│  ├─ templates/sub_character.yaml
│  ├─ settings/
│  │  ├─ system_settings.yaml   サーバーの設定。Git管理
│  │  ├─ generation.yaml        生成の設定（温度、最大トークン数）。Git管理
│  │  ├─ secrets.yaml           秘密の値（APIキー）。**Git管理外**
│  │  └─ secrets.example.yaml   secrets.yaml の書き方の見本。Git管理
│  ├─ systems/sessions_list.yaml      全セッションの一覧。Git管理外
│  └─ sessions/{セッションID}/         セッションごとのフォルダ。Git管理外
├─ logs/                           モデルへ送ったプロンプトとパラメーターの記録。Git管理外
├─ temp/                           記憶生成の途中結果。Git管理外
└─ models/                         モデルファイル(.gguf)。Git管理外
```

<a id="s3-1"></a>

### セッションフォルダ（`files/sessions/{セッションID}/`）

<div align="right"><a href="#top">▲ 目次へ</a></div>

| ファイル | 中身 | 作られる時 |
|---|---|---|
| `{世界ID}_world.yaml` | 世界設定のコピー | `/chat_startup` |
| `character/{ID}_setting.yaml` | プレイヤー・キャラクター設定のコピー | `/chat_startup` |
| `character/{参照ID}_setting.yaml` | `inline` の人物。テンプレートから作る（名前の規則は他の人物と同じ） | `/chat_startup` |
| `picture/icon/{ID}.png` | キャラクター・プレイヤーのアイコンのコピー（元に無ければ作らない） | `/chat_startup` |
| `picture/standing/{ID}_standing.png` | キャラクター・プレイヤーの立ち絵のコピー（元に無ければ作らない） | `/chat_startup` |
| `prepare_status.yaml` | 進行状態（→ [`chat-flow.md`](chat-flow.md)） | `/new_chat` |
| `history.json` | 発言の履歴（→ [`api.md`](api.md) の「履歴のファイル」） | `/new_chat` 以降、発言のたびに追記 |
| `world_memory.yaml` | 世界の記憶 | `/new_chat` の裏の処理 |
| `character/{ID}_memory.yaml` | キャラクターの記憶 | `/new_chat` の裏の処理 |

元データと違い、セッション側の画像はIDごとのフォルダに分けず、`picture/icon/` の直下に並べる。

#### 世界の記憶（`world_memory.yaml`）

```yaml
プレイヤーID:
プレイヤー名:
現在の状態:
  日付:
  参加者:            # 今その場にいる人。名前と役割の一覧
  パーティー一覧:     # メンバー一覧を持つ
世界の状態:
  参加者:            # 世界に登場する人すべて。名前と役割の一覧
```

#### キャラクターの記憶（`character/{ID}_memory.yaml`）

```yaml
現在の状態:
  場所:
  状態: [...]
  行動: [...]
  心情: [...]
  服装: [...]
  関係性:            # 世界の記憶の「現在の状態 → 参加者」と同じもの
  意識: [...]        # 今、意識を向けている相手
  所持品: [...]
  金額:
```

作られるのは `参照種別` が `character` の人物だけ。プレイヤーと `inline` の人物には作らない。

- `inline` の人物（サブ・モブ）には、記憶を作らない。

<a id="s3-2"></a>

### セッション一覧（`files/systems/sessions_list.yaml`）

<div align="right"><a href="#top">▲ 目次へ</a></div>

```yaml
sessions:
  - session_id: ...
    display_name: カッコウ医院編-1
    world_id: kakko_clinic
    world_name: カッコウ医院編
    created_at: 2026年10月12日 10:00
    updated_at: 2026年10月12日 10:00
```

ファイルやフォルダが無い状態から始めても動く（最初のセッションを作るときに作られる）。

<a id="s3-3"></a>

### サーバーの設定（`files/settings/system_settings.yaml`）

<div align="right"><a href="#top">▲ 目次へ</a></div>

| 項目 | 中身 | 未設定のとき |
|---|---|---|
| `port` | APサーバーのポート | 5000 |
| `local_model_use_flag` | ローカルモデルを使うか | |
| `local_model_path` | モデルファイルのあるフォルダ | モデルサーバーが起動時に止まる |
| `local_mode_name` | モデルファイルの名前 | 同上 |
| `local_model_server_port` | モデルサーバーのポート | 5001 |
| `local_model_prompt_format` | ローカルモデルへ送る会話の形式。`chatml`／`alpaca`（→ [`prompts.md`](prompts.md)） | `chatml` |
| `local_model_no_think` | `true` なら、返事の出だしに空の思考ブロックを置いて、思考を書かせない（`chatml` のときだけ効く） | `true` |
| `local_mode_max_tokens` | | |
| `open_router_use_flag`、`openrouter_site_url`、`openrouter_site_name`、`openrouter_max_tokens` | OpenRouter を使う場合の設定（APIキーは `secrets.yaml`） | |
| `default_model`、`temperature`、`max_tokens` | 既定のモデル名と生成の設定 | `grok-4`、0.85、2048 |
| `characters_dir` | | |
| `log_level`、`enable_image_generation` | | |

- Git で管理する。リポジトリは公開なので、**秘密の値は書かない**（下の「秘密の値」）。
- 読み込むのは起動時。`src/config.py` の `config` がまとめて持つ。
- 生成の設定（温度、最大トークン数）は、今は用途ごとにコードで決めている（→ [`prompts.md`](prompts.md)）。
  設定ファイルの `temperature`、`max_tokens`、`default_model` が効くのは、OpenRouter を使う場合だけ。
- `log_level`、`enable_image_generation`、`characters_dir`、`openrouter_max_tokens`、`local_mode_max_tokens` は、
  設定にはあるが、コードのどこからも読まれていない。OpenRouter は使わない方向に寄せる予定だが、
  今はローカルモデルの作り込みを優先するので、これらはそのまま置いておく。

<a id="s3-4"></a>

### 秘密の値（`files/settings/secrets.yaml`）

<div align="right"><a href="#top">▲ 目次へ</a></div>

APIキーなど、人に見せてはいけない値だけを書くファイル。`files/settings/` の中で、これだけが Git 管理外。

| 項目 | 中身 |
|---|---|
| `openrouter_api_key` | OpenRouter のAPIキー。OpenRouter を使うとき（`open_router_use_flag` が `true`）だけ必要 |

- 無くても起動する（ローカルモデルだけ使うなら不要）。新しく用意するときは、`secrets.example.yaml` をコピーして名前を変える。
- 鍵が `system_settings.yaml` に書いてあっても読めるが、起動時に「`secrets.yaml` に移してください」と警告を出す。
  `system_settings.yaml` は公開されるので、警告が出たらすぐ移す。
- 鍵の値は、ログにも画面にも出さない。

<a id="s3-5"></a>

### 生成の設定（`files/settings/generation.yaml`）

<div align="right"><a href="#top">▲ 目次へ</a></div>

モデルに文章を作らせるときの、温度や最大トークン数。用途（`memory`、`judge`、`chat`）ごとに値を持つ。
形と優先順位は [`prompts.md`](prompts.md) の「生成の設定」。

- `files/settings/` の中で、このファイルだけ Git で管理している（`.gitignore` で例外にしている）。秘密の値は書かない。
- 書き換えると、サーバーを再起動しなくても、次にモデルへ送るときから反映される。

<a id="s3-6"></a>

### 記録と途中結果

<div align="right"><a href="#top">▲ 目次へ</a></div>

| 場所 | 中身 |
|---|---|
| `logs/{時刻}_prompt.txt` | ローカルモデルへ送ったプロンプトの全文。送るたびに1つ |
| `logs/{時刻}_params.json` | そのときの生成の設定（温度など） |
| `temp/{キャラクターID}_{セッションID}_middle.yaml` | キャラクター記憶の生成の途中結果（要約） |
| `temp/{キャラクターID}_{セッションID}_middle_categorize.yaml` | 同（分類） |

どれも消しても動作に影響しない。プロンプトの中身を確かめたいときは `logs/` を見る。

- `temp/` の途中結果は、セッションを削除したときに一緒に消える（ファイル名にセッションIDが入っているもの）。
- `logs/` は自動では消さない。不要になったら手で消してよい。

<a id="s4"></a>

## 要確認の一覧（この文書の分）

<div align="right"><a href="#top">▲ 目次へ</a></div>

答えが決まっていても、コードに反映するまでは表に残す。反映したら、本文を仕様として書き直し、表から外す。

| 番号 | 対象 | 確認したいこと | 回答・状況 |
|---|---|---|---|
| Q23 | 登場人物の `役割` | `役割`（main / sub / mob）で動きを変えるか | 回答: どう変えるかが決まっていないので、今は答えられない |
