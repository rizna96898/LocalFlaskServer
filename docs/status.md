# 現状

<a id="top"></a>

<!-- toc:start -->
**目次**

- [仮の実装（動くが、中身が本物ではない）](#s1)
  - [チャットの返答（`/chat`）](#s1-1)
  - [話者の固定](#s1-2)
  - [設定画面のボタン](#s1-3)
- [未実装](#s2)
- [既知の不具合](#s3)
- [残っている半端なもの](#s4)
<!-- toc:end -->

仕様（[`spec/`](spec/)）に対して、今のコードがまだ届いていない所の一覧。
サーバー（LocalFlaskServer）と画面（LLM_CHAT_CONSOLE）の両方をここにまとめる。

**この文書の使い方**

- 作りかけの箇所を触る前に読む。仮の実装を「仕様」と取り違えないため。
- 直したら、その項目をここから消す。新しく作りかけを残したら、ここに足す。
- 「こう動くべき」という話は書かない。それは `spec/` に書く。意図がまだ決まっていないものは、`spec/` の【要確認】に入れる。
- 各項目の（→ Q番号）は、直し方や扱いを確かめている `spec/` の【要確認】。

最終更新: 2026-10-15

<a id="s1"></a>

## 仮の実装（動くが、中身が本物ではない）

<div align="right"><a href="#top">▲ 目次へ</a></div>

<a id="s1-1"></a>

### チャットの返答（`/chat`）

<div align="right"><a href="#top">▲ 目次へ</a></div>

- 返答として返しているのは、「誰に向けた発言か」を判定するプロンプトの結果そのもの。キャラクターとしての返答は作っていない。
  流れ: `ChatExecute.chat` → `ChatUtils.chat` → `ChatManager.main_chat` → `ChatPromptBuilder.create_discrimination_prompt`（→ Q52）
- その判定プロンプトの登場人物（`shirai_yui`、`shirai_keita`）と状況文は、`chat_builders/prompt_builder.py` に直書き。（→ Q53）
- 判定プロンプトが、置換前の `{characters}`、`{player_message}`、`{player_answer}` を含んだままモデルに送られている。
  置換したものを system 側に入れたうえで、元のひな形（`template`）も user 側にそのまま連結しているため。（→ Q53）

<a id="s1-2"></a>

### 話者の固定

<div align="right"><a href="#top">▲ 目次へ</a></div>

- `/new_chat`、`/chat` が返す発言者と、履歴に書く発言者が、`shirai_yui` / `白井　結` で固定。
  世界の登場人物が誰であっても、この名前で返る。（→ Q54）
- プレイヤーの発言者IDは、実際のプレイヤーIDではなく `player` で固定。（→ Q54）
- 世界の記憶を作るとき、プレイヤーのIDと名前が `kyuya` / `究也` で固定（`memory_manager.py`）。
  世界の登場人物の `player` が誰であっても、この名前で `world_memory.yaml` に入る。（→ Q54）

<a id="s1-3"></a>

### 設定画面のボタン

<div align="right"><a href="#top">▲ 目次へ</a></div>

- `/v1/chat/check_stability`: 常に「起動してないよ。」を返す。画面からは呼ばれていない。画像生成の連携を作るときに本物にする（[`spec/api.md`](spec/api.md)）。

<a id="s2"></a>

## 未実装

<div align="right"><a href="#top">▲ 目次へ</a></div>

- **発言の前処理・後処理**: 発言ごとの世界の記憶の更新、キャラクターの記憶の更新、パラメーターの変動。
  プロンプトYAML（`files/prompts/chat/01_preprocess/`、`03_postprocess/`）はあるが、呼び出す処理が無い。
  以前の作りかけは、コミット `eca2ea0` 以前の履歴にある。（→ Q55）
- **複数キャラクターの会話**（モブ会話、返答する相手の決定）。（→ Q52）
- **プレイヤーのアイコンをチャットに出す**: 画像はセッションへ退避しているが、履歴の発言者IDが `player` 固定なので、どの画像を出すか決められない。
  画面も `player` のアイコンは問い合わせない。（→ Q63）
- **OpenRouter 経由のモデル呼び出し**: `OpenRouterService` はあるが、呼び出し側はすべてローカルモデル（`"local"`）固定。（→ Q61）
- **画像生成**: 画面に「返信生成結果画像」の欄があるが、処理は無い。（→ Q37）
- **メイン画面右の「世界・モデル設定」**: `temperature`、`max_tokens`、「画像生成」、「OpenRouter補助」の入力欄は、見た目だけで、
  値はどこにも送られていない（サーバー側は設定ファイルと、コード内の値を使う）。（→ Q64）
- **メイン画面上部の「言語選択」「ラベル ON/OFF」**: 操作しても何も起きない（処理がつながっていない）。
  「タグ」はウィンドウが開くが、中の「登録／更新」は何もしない。（→ Q65）

<a id="s3"></a>

## 既知の不具合

<div align="right"><a href="#top">▲ 目次へ</a></div>

- **`config.reload()` が設定の値を更新しない**: `system_settings.yaml` を読み直すが、`config.LOCALMODEL_PATH` などの値は起動時のまま。
  モデルサーバーの読み直し（`/reload`）は、読み直した設定の中身から直接モデルの場所を取るので、影響を受けない。（→ Q59）
- **プレイヤー画面のアイコンに切り抜きが無い**: キャラクター画面は正方形に切り抜いてから保存するが、プレイヤー画面は選んだ画像をそのまま保存する。（→ Q66）

<a id="s4"></a>

## 残っている半端なもの

<div align="right"><a href="#top">▲ 目次へ</a></div>

- `src/constant.py` の `Bootstrap.CHARACTER_ITEMS`、`CHARACTER_MEMORY`、`SUB_CHARACTER_MEMORY`: 指しているYAMLが無く、コードからも使われていない。（→ Q58）
- 設定項目名 `local_mode_name`: `local_model_name` の綴り違いに見える。直すと設定ファイル側の書き換えも必要。（→ Q60）
- `OpenRouterService`（未使用）: 送信内容に `logit_bias: {"248068": -100}` が直書きされている。この番号はローカルの Qwen の `<think>` で、OpenRouter のモデルでは別の語を指す。OpenRouter を使い始める前に外すこと。（→ Q61）
- ルートの `構成.txt`: 初期の構想で、今のフォルダ構成とは一致しない（Git管理外）。（→ Q62）
- LLM_CHAT_CONSOLE の `README.txt`: 設定画面を足したときのメモ。書かれている `flask_settings_api.py` は存在せず、該当のAPIはこのリポジトリにある。（→ Q62）
