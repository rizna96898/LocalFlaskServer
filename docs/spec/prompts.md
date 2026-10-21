# プロンプトの仕様

<a id="top"></a>

<!-- toc:start -->
**目次**

- [基本の決まり](#s1)
- [置き場所](#s2)
- [YAMLの形](#s3)
  - [差し込み口](#s3-1)
- [プロンプトの一覧](#s4)
  - [初期記憶の生成（`bootstrap/`）](#s4-1)
  - [発言ごとの処理（`chat/`）](#s4-2)
- [組み立て方](#s5)
  - [ローカルモデルへ送る形](#s5-1)
  - [なぜこの形にしたか（2026-10-13 の実験）](#s5-2)
  - [返事の後始末](#s5-3)
- [生成の設定](#s6)
  - [値の決まり方](#s6-1)
  - [プロンプトごとに変える](#s6-2)
  - [コードでの組み立て](#s6-3)
- [送った内容の記録](#s7)
- [要確認の一覧（この文書の分）](#s8)
<!-- toc:end -->

モデルに送る文章を、どこに置き、どう組み立て、どんな設定で送るか。

**この文書の位置づけ**: 2026-10-12 時点のコードから書き起こした下書き。
判断がつかなかった所には **【要確認 Q番号】** を付けている（番号は [`api.md`](api.md) からの通し）。
どの場面でどのプロンプトを使うかの流れは [`chat-flow.md`](chat-flow.md)、作りかけは [`../status.md`](../status.md) を見る。

<a id="s1"></a>

## 基本の決まり

<div align="right"><a href="#top">▲ 目次へ</a></div>

- **プロンプトの文章は、すべて `files/prompts/` のYAMLに書く。コードには書かない。**
  文面を直すときに、Python を触らずに済むようにするため。
- YAMLのファイル名は、`src/constant.py` に定数として持つ。YAMLを足す・改名するときは、ここも直す。
- 使わなくなったプロンプトは `files/prompts/backups/` に移す（Git管理外）。

<a id="s2"></a>

## 置き場所

<div align="right"><a href="#top">▲ 目次へ</a></div>

```
files/prompts/
├─ bootstrap/            新規チャット時の、初期記憶の生成
└─ chat/
   ├─ 01_preprocess/     発言ごとの前処理
   ├─ 02_main/           発言ごとの本処理（返答）
   └─ 03_postprocess/    発言ごとの後処理
```

ファイル名の先頭の数字は、その段階の中での順番を表す。

| フォルダ | 定数のクラス（`src/constant.py`） | `config` での参照 |
|---|---|---|
| `bootstrap/` | `Bootstrap` | `config.BOOTSTRAP` |
| `chat/01_preprocess/` | `PromptsPreprocess` | `config.PREPROCESS` |
| `chat/02_main/` | `PromptsMain` | `config.MAIN` |
| `chat/03_postprocess/` | `PromptsPostprocess` | `config.POSTPROCESS` |

<a id="s3"></a>

## YAMLの形

<div align="right"><a href="#top">▲ 目次へ</a></div>

1つのYAMLが、1回分の「モデルへの頼みごと」。使うキーは次のとおり。

| キー | 中身 |
|---|---|
| `system` | モデルへの役割と決まり。「あなたは○○を特定する担当です」「YAMLでのみ返す」など |
| `header` | 本文の前に置く文 |
| `template` | 本文のひな形。`{名前}` の形の差し込み口を持てる |
| `tail_template` | 本文の後に置く念押し。「出力開始は必ず『服装:』から」など |
| `params` | そのプロンプトだけ生成の設定を変えたいときに書く（→「生成の設定」）。普段は書かない |

全部が必須ではない。使うキーだけ書く。

<a id="s3-1"></a>

### 差し込み口

<div align="right"><a href="#top">▲ 目次へ</a></div>

`template` などの中の `{summary}` のような部分は、送る前にコードが実際の内容で置き換える。

| 差し込み口 | 入るもの |
|---|---|
| `{character_name}` | キャラクターの表示名 |
| `{character_data}` | キャラクター設定YAMLの全文 |
| `{characters}` | 登場人物（要約のプロンプトでは、世界の記憶の `世界の状態` → `参加者`） |
| `{scenario}` | シナリオ本文 |
| `{first_message}` | 開始メッセージ |
| `{scenario_parameter}` | シナリオパラメータ |
| `{summary}` | 要約の段階の結果 |
| `{location}`、`{clothing_data}` | 場所・服装の段階の結果 |
| `{participants_data}` | 世界の記憶の参加者 |

- 同じものには、どのプロンプトでも同じ名前を使う。新しく差し込み口を作るときは、上の表の名前に合わせる。

<a id="s4"></a>

## プロンプトの一覧

<div align="right"><a href="#top">▲ 目次へ</a></div>

<a id="s4-1"></a>

### 初期記憶の生成（`bootstrap/`）

<div align="right"><a href="#top">▲ 目次へ</a></div>

| ファイル | 用途 | 使われているか |
|---|---|---|
| `01_query_create_world_memory.yaml` | 世界の記憶を作る | 使用中 |
| `00_..._middle_summary.yaml` | キャラクター: 今の状況の要約 | 使用中 |
| `00_..._middle_location.yaml` | キャラクター: 場所 | 使用中 |
| `00_..._middle_categorize.yaml` | キャラクター: 要約を行動・状態・心情に分類 | 使用中 |
| `00_..._middle_clothing.yaml` | キャラクター: 服装 | 使用中 |
| `00_..._middle_items.yaml` | キャラクター: 所持品 | 使用中 |
| `00_..._middle_target.yaml` | キャラクター: 意識を向けている相手 | 使用中 |
| `00_..._middle_currency.yaml` | キャラクター: 所持金 | 使用中 |
| `01_query_create_edit_summary.yaml` | 要約の編集 | 未使用 |

（`00_..._middle_` は `00_query_create_character_memory_middle_` の略）

キャラクターの記憶は、「要約 → 場所 → 分類 → 服装 → …」と小分けにして1つずつ聞いている。
1回で全部を聞くと、ローカルモデルでは形が崩れたり抜けが出たりしやすいため、と思われる（コードからの推測）。

<a id="s4-2"></a>

### 発言ごとの処理（`chat/`）

<div align="right"><a href="#top">▲ 目次へ</a></div>

| ファイル | 用途（ファイル名から） | 使われているか |
|---|---|---|
| `01_preprocess/01_query_update_world_memory.yaml` | 世界の記憶の更新 | 未使用（中身も空） |
| `01_preprocess/99_query_judge_player_identification.yaml` | 誰の発言かの判定 | 未使用 |
| `02_main/01_query_validation_chat.yaml` | 返答に矛盾がないかの検証 | 未使用（中身も空） |
| `02_main/00_query_judge_newcomer.yaml` | 返事の前に、プレイヤーの発言で呼ばれた人のうち、まだその場にいない人の確認 | **使用中** |
| `02_main/02_query_chat.yaml` | 返事の生成（プレイヤーへの返事と、掛け合いで話しかけられた側の返事） | **使用中** |
| `02_main/02_query_judge_character_identification.yaml` | 誰に向けた発言かの判定（返事をする人を決める） | **使用中** |
| `02_main/03_query_judge_attention.yaml` | 返事のあと、意識が誰に向いているかの確認 | **使用中** |
| `02_main/04_query_cross_talk.yaml` | 掛け合いの話しかけ（意識が向いている相手に一言） | **使用中** |
| `02_main/05_query_judge_consult.yaml` | 返事の前に、同じパーティーの人に相談するかの確認 | **使用中**（2026-10-20 に新しく作った） |
| `02_main/06_query_consult.yaml` | 相談の話しかけ（プレイヤーに答える前に、同じパーティーの人へ） | **使用中**（2026-10-20 に新しく作った） |
| `03_postprocess/01_query_parameter_fluctuation.yaml` | パラメーターの変動 | 未使用 |
| `03_postprocess/01_query_update_edit_summary.yaml` | 要約の更新 | 未使用 |
| `03_postprocess/01_query_update_story_summary.yaml` | 発言のあとの会話のあらすじの更新（`summary.yaml`） | **使用中**（2026-10-20 に新しく作った） |
| `03_postprocess/01_query_update_world_memory.yaml` | 発言のあとの「その場の参加者」の更新（来た人・出て行った人、新しく現れた人） | **使用中**（2026-10-19 に書き直した） |
| `03_postprocess/02_query_update_character_items.yaml` | キャラクターの所持品の更新 | 未使用 |
| `03_postprocess/02_query_update_character_memory.yaml` | 発言のあとのキャラクターの記憶の更新（今の記憶＋今回の会話 → 更新した記憶） | **使用中**（2026-10-18 に今の記憶の形で書き直した） |

`chat/` のプロンプトのうち、`02_main/` の返事・判定・意識・掛け合いと、`03_postprocess/` のその場の参加者・あらすじ・キャラクターの記憶の更新は使っている。
`03_postprocess/` のほかのYAMLは以前の作り（英語のキーなど）で、使うときに書き直しが要る（Q69）。`01_query_update_edit_summary.yaml` は、キャラクターの記憶を文章にまとめ直す別の用途のもので、あらすじの更新には使っていない。それ以外は文面だけ用意されていて、呼び出す処理がまだ無い（[`../status.md`](../status.md)）。

`02_main/` の返事・意識・掛け合いのプロンプトは、`system`・`template`・`tail_template` のどこにでも差し込み口を置ける
（`string_utils.fill_template(..., fields=("system", "template", "tail_template"))` で埋める）。差し込み口の意味は、各YAMLの先頭のコメントにある。

<a id="s5"></a>

## 組み立て方

<div align="right"><a href="#top">▲ 目次へ</a></div>

YAMLの各キーから、「system」と「user」の2つのメッセージを作る。

```
system  ←  YAMLの system
user    ←  header ＋ その場で作った本文 ＋ template ＋ tail_template   （空のものは飛ばし、空行でつなぐ）
```

- 組み立ては、すべてのプロンプトで共通の関数 `string_utils.build_messages` を使う。各段階で個別に文字列をつながない。
- 差し込み口（`{summary}` など）は、組み立ての前に埋める。`template` の差し込み口は `string_utils.fill_template` で埋める。
  `system` にも差し込み口がある段階（キャラクターの記憶の要約）は、その段階で埋めてから渡す。
- 各部分は前後の空白を取ってから、空行1つで区切る。YAMLの値の先頭や末尾の改行は、送る内容には残らない。

<a id="s5-1"></a>

### ローカルモデルへ送る形

<div align="right"><a href="#top">▲ 目次へ</a></div>

ローカルモデルは「system」「user」という区別を受け取らないので、送る直前に1本の文章にまとめる（`messages_to_prompt`）。

**形式は、モデルが学習した形式に合わせる。** 設定の `local_model_prompt_format` で選ぶ。

| 値 | 形式 | 使うモデル |
|---|---|---|
| `chatml`（既定） | `<\|im_start\|>役割 … <\|im_end\|>` で区切る | Qwen 系など |
| `alpaca` | `### Instruction:` / `### Response:` | mythomax など |

`chatml` のとき、送る文章は次の形になる。

```
<|im_start|>system
（system の内容）<|im_end|>
<|im_start|>user
（user の内容）<|im_end|>
<|im_start|>assistant
<think>

</think>

```

モデルは、この続きを書く。

- **思考の止め方**: 最後の `<think>` 〜 `</think>` は、中身が空の思考ブロック。こちらで先に書いておくと、モデルは「もう考え終わった」ものとして、
  本文から書き始める。設定の `local_model_no_think`（既定は `true`）を `false` にすると、置かない。
- **`<think>` を禁止する方法（`logit_bias`）は使わない。** 思考するように学習したモデルは、返事を `<think>` から書き始めようとする。
  そこを禁止すると、モデルは代わりに改行だけを出して、そのまま終わってしまう（空の返事）。
- 形式が合っていないと、プロンプトに「思考過程は出力しない」と書いてあっても、その指示が指示として伝わらない。

<a id="s5-2"></a>

### なぜこの形にしたか（2026-10-13 の実験）

<div align="right"><a href="#top">▲ 目次へ</a></div>

初期記憶の生成で、モデルが空の返事を返して失敗することがあった。実際に失敗したプロンプト（服装）を、条件を変えて10回ずつ送って比べた。
モデルは Qwen3.6-35B-A3B（Q3_K_XL）。

| 条件 | 空の返事 | 使える答え | 平均時間 |
|---|---|---|---|
| `alpaca` ＋ `<think>` を禁止（-100）※以前の送り方 | 6/10 | 4/10 | 0.8秒 |
| `alpaca` ＋ `<think>` を弱く禁止（-5） | 6/10 | 4/10 | 0.8秒 |
| `alpaca` ＋ 禁止なし | 0/10 | 0/10 | 6.8秒 |
| `chatml` ＋ 禁止なし | 0/10 | 10/10 | 1.1秒 |
| `chatml` ＋ 空の思考ブロックを先に置く ※今の送り方 | 0/10 | 10/10 | 1.1秒 |
| `chatml` ＋ `<think>` を禁止（-100） | 0/10 | 10/10 | 1.1秒 |

わかったこと:

- 主な原因は、形式がモデルと合っていなかったこと。`<think>` の禁止は、合っていない形式の上でだけ空の返事を生んでいた。
- `alpaca` で禁止を外すと、モデルは英語で長々と考え続け、答えにたどり着かない（以前 `<think>` を禁止した理由は、これだったと思われる）。
- `chatml` では、何もしなくても、モデルは自分から空の思考ブロックを書いてすぐ答える。プロンプトの「思考過程は出力しない」が効いている。
- 番号 `248068` は、このモデルの `<think>`。番号はモデルごとに違うので、モデルを替えると別の語を指す。

確かめたのは服装のプロンプト1種類。実験の道具は `z:\SendPromptTest\`（`empty_reply_test.py`、`token_lookup.py`）にある。
モデルを替えたとき、または空の返事がまた出たときは、同じ道具で確かめ直す。

<a id="s5-3"></a>

### 返事の後始末

<div align="right"><a href="#top">▲ 目次へ</a></div>

返ってきた文章から、次のものを取り除いてから使う（`cleanup_model_output`、`strip_code_block`）。

- `<think>` 〜 `</think>` の部分（思考の過程）
- `### Response:` が混ざっていた場合、その前の部分
- 前後のコードブロックの記号（```` ``` ````）

返事が空だった場合は、同じ内容であと2回まで送り直す。それでも空なら失敗とする。形式を直してからは、空の返事は出ていない（上の実験）。この送り直しは、念のための備えとして残している。

<a id="s6"></a>

## 生成の設定

<div align="right"><a href="#top">▲ 目次へ</a></div>

温度や最大トークン数は、コードには書かず、**`files/settings/generation.yaml`** に書く。

```yaml
default:              # 基本の値
  temperature: 0.5
  top_p: 0.9
  top_k: 0
  repeat_penalty: 1.1
  max_tokens: 800

memory:               # 用途ごとの欄。変えたい項目だけ書く
  max_tokens: 1500
judge:
  max_tokens: 200
chat:
  max_tokens: 400
```

| 項目 | 意味 |
|---|---|
| `temperature` | ばらつき。小さいほど毎回同じ答えになり、大きいほど多彩になる |
| `top_p` | 候補を、確率の上位から合計がこの割合になるまでに絞る |
| `top_k` | 候補を、確率の上位この個数に絞る。0 は絞らない |
| `repeat_penalty` | 同じ言葉の繰り返しを抑える強さ。1.0 は抑えない |
| `max_tokens` | 1回の返事の長さの上限 |

<a id="s6-1"></a>

### 値の決まり方

<div align="right"><a href="#top">▲ 目次へ</a></div>

上にあるものほど優先される。

1. プロンプトのYAMLの `params`（そのプロンプトだけ変えたいとき）
2. `generation.yaml` の用途ごとの欄（`memory`、`judge`、`chat`）
3. `generation.yaml` の `default`
4. コードに持っている組み込みの値（`generation.yaml` が無い・項目が欠けているときの備え）

用途は、呼び出し側が `build_send_parameters` に渡す1つ目の値で決まる。

| 用途 | 使う場面 |
|---|---|
| `memory` | 記憶の生成（世界の記憶、キャラクターの記憶の各段階） |
| `judge` | 判定（誰の発言か、誰に向けた発言か） |
| `chat` | キャラクターの返答 |

- `generation.yaml` を書き換えると、次にモデルへ送るときから反映される。サーバーの再起動は要らない。
- `generation.yaml` が壊れていても（YAMLとして読めない、形が違う）、止めずに、直前に読めた内容で送る。
- `generation.yaml` は Git で管理する。`files/settings/` は丸ごと管理外だが、このファイルだけ例外にしている。
  APIキーなど秘密の値は書かない（それは `system_settings.yaml` に書く）。
- 誰に向けた発言かの判定は `judge`、キャラクターの返答は `chat` で送る。

<a id="s6-2"></a>

### プロンプトごとに変える

<div align="right"><a href="#top">▲ 目次へ</a></div>

特定のプロンプトだけ値を変えたいときは、そのプロンプトのYAMLに `params` を足し、変えたい項目だけ書く。

```yaml
system: |
  あなたは「現在の服装」を特定する担当です。
  …
params:
  temperature: 0.2
```

今は、どのプロンプトにも書いていない（全部が用途の値で動いている）。

<a id="s6-3"></a>

### コードでの組み立て

<div align="right"><a href="#top">▲ 目次へ</a></div>

モデルへ送る内容は、`services/llm/generation_params.py` の `build_send_parameters` で組み立てて、`ModelHandlingService.send_message` に渡す。

```python
parameters = generation_params.build_send_parameters(
    "memory",                    # 用途
    system_prompt=system_prompt,
    user_content=temp_str,       # 本文。messages=[...] で渡してもよい
    prompt_data=prompt_yaml,     # プロンプトのYAMLを読んだ辞書。params があれば上書きに使う
)
response_text = self.model_handling_service.send_message(parameters)
```

- 生成を打ち切る文字列は、形式に応じて `llm_service.py` の `build_stop` が付ける（`chatml` なら `<|im_end|>`、`alpaca` なら `### Instruction:`）。
  モデルがそこまで書いたら生成を止める指定で、答えのあとに次の質問まで勝手に書き続けるのを防ぐ。
- `logit_bias` は使わない（上の「ローカルモデルへ送る形」）。
- 以前は、用途ごとに関数を分け（`use_memory_constant.py` の8つと `use_chat_constant.py` の1つ）、`<think>` の禁止の強さや
  打ち切る文字列を変えていた。形式を直してからは、その使い分けが不要になり、1つにまとめた。

<a id="s7"></a>

## 送った内容の記録

<div align="right"><a href="#top">▲ 目次へ</a></div>

ローカルモデルへ送るたびに、`logs/{セッションID}/{通し番号}_{時分秒}_{段階}.txt` を1つ書く（`log.debug_dump_all` と `log.debug_dump_response`）。
中身は次の順に並ぶ。

- `===== 生成の設定 =====`: 温度・最大トークン数など
- `===== 送った内容 =====`: 送った文章の全文（改行はそのまま改行で書く）
- `===== 返事 =====`: モデルの返事（後始末のあと。後始末の前と違えば、その下に両方書く）

セッションIDと段階は、送る前に `log.set_session` / `log.set_step` で決める（スレッドごとに持つ）。APサーバーは、リクエストごとに空に戻す。
セッションに属さない問い合わせは `logs/_セッション外/` に入る。
返事がおかしいとき・YAMLとして読めなかったときは、`===== 返事 =====` で、モデルが実際に何を返したかを見る。

プロンプトを直したときは、ここを見て、差し込み口が正しく置き換わっているかを確かめる。

<a id="s8"></a>

## 要確認の一覧（この文書の分）

<div align="right"><a href="#top">▲ 目次へ</a></div>

答えが決まっていても、コードに反映するまでは表に残す。反映したら、本文を仕様として書き直し、表から外す。

| 番号 | 対象 | 確認したいこと | 回答・状況 |
|---|---|---|---|
