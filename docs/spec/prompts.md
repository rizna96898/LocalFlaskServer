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
  - [最大トークン数](#s6-1)
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
| `message_header` | `header` と同じ役割（分類のプロンプトだけがこの名前を使っている） |

全部が必須ではない。使うキーだけ書く。

- **【要確認 Q38】** 分類のプロンプトだけ `header` ではなく `message_header` という名前になっている。`header` に揃えてよいか。

<a id="s3-1"></a>

### 差し込み口

<div align="right"><a href="#top">▲ 目次へ</a></div>

`template` などの中の `{summary_data}` のような部分は、送る前にコードが実際の内容で置き換える。

| 差し込み口 | 入るもの |
|---|---|
| `{character_name}` | キャラクターの表示名（要約のプロンプトの本文だけは、表示名ではなくキャラクターIDが入る） |
| `{character_data}` | キャラクター設定YAMLの全文 |
| `{characters}` | 登場人物（要約のプロンプトでは、世界の記憶の `世界の状態` → `参加者`） |
| `{scenario}` | シナリオ本文 |
| `{first_mes}`、`{first_message}` | 開始メッセージ |
| `{mes_example}` | シナリオパラメータ |
| `{summary_data}`、`{summary}` | 要約の段階の結果 |
| `{location}`、`{clothing_data}` | 場所・服装の段階の結果 |
| `{participants_data}` | 世界の記憶の参加者 |

- **【要確認 Q39】** 同じものに、プロンプトによって違う名前が付いている（`{first_mes}` と `{first_message}`、`{summary_data}` と `{summary}`）。
  `{first_mes}`、`{mes_example}` は SillyTavern のキャラクターカードの項目名の名残に見える。揃えるか。
  また、要約のプロンプトでは `{character_name}` に、system 側は表示名、本文側はIDが入る。どちらかに揃えるか。

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
| `02_main/02_query_chat.yaml` | 返答の生成 | 未使用 |
| `02_main/02_query_judge_character_identification.yaml` | 誰に向けた発言かの判定 | **使用中**（`/chat` の仮実装が、これの結果を返答として返している） |
| `03_postprocess/01_query_parameter_fluctuation.yaml` | パラメーターの変動 | 未使用 |
| `03_postprocess/01_query_update_edit_summary.yaml` | 要約の更新 | 未使用 |
| `03_postprocess/01_query_update_world_memory.yaml` | 世界の記憶の更新 | 未使用 |
| `03_postprocess/02_query_update_character_items.yaml` | キャラクターの所持品の更新 | 未使用 |
| `03_postprocess/02_query_update_character_memory.yaml` | キャラクターの記憶の更新 | 未使用 |

`chat/` のプロンプトは、ほとんどが文面だけ用意されていて、呼び出す処理がまだ無い（[`../status.md`](../status.md)）。

<a id="s5"></a>

## 組み立て方

<div align="right"><a href="#top">▲ 目次へ</a></div>

YAMLの各キーから、「system」と「user」の2つのメッセージを作る。

```
system  ←  YAMLの system
user    ←  header ＋ その場で作った本文 ＋ template ＋ tail_template   （空のものは飛ばし、空行でつなぐ）
```

- 世界の記憶は、この形（`MemoryPromptBuilder._build_messages`）で組み立てる。
- キャラクターの記憶の各段階は、`memory_manager.py` の中で、`template` の差し込み口を置き換えてから `tail_template` をつなげている。

- **【要確認 Q40】** 組み立て方が2通りある（共通の関数を使うものと、各段階で個別につなげるもの）。1つに揃えるか。

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

用途ごとに、コード（`memory_builders/use_memory_constant.py`、`chat_builders/use_chat_constant.py`）で決めている。
今は、どの用途も同じ値。

| 項目 | 値 |
|---|---|
| 温度 | 0.5 |
| `top_p` | 0.9 |
| `top_k` | 0 |
| 繰り返し抑制 | 1.1 |
| `logit_bias` | 使わない |

生成を打ち切る文字列は、形式に応じて `llm_service.py` の `build_stop` が付ける（`chatml` なら `<|im_end|>`、`alpaca` なら `### Instruction:`）。
モデルがそこまで書いたら生成を止める指定で、答えのあとに次の質問まで勝手に書き続けるのを防ぐ。
呼び出し側が打ち切る文字列を足したい場合は、`stop` に入れて渡すと、形式ごとの分に加えられる。

- 以前は、用途ごとに `<think>` の禁止の強さ（-5 〜 -100）と打ち切る文字列を変えていた。
  形式を直してからは、その使い分けが不要になった（上の「なぜこの形にしたか」）。

<a id="s6-1"></a>

### 最大トークン数

<div align="right"><a href="#top">▲ 目次へ</a></div>

用途の種類（`task_type`）で決まる（`ModelHandlingService._get_default_max_tokens`）。

| `task_type` | 最大トークン数 |
|---|---|
| `chat` | 400 |
| `memory` | 1500 |
| `judge` | 200 |
| それ以外 | 800 |

- **【要確認 Q44】** 今の呼び出しは、すべて `task_type` が `memory` になっている（誰に向けた発言かの判定も `memory`）。
  判定は `judge`、返答は `chat` にするのが本来の形か。

<a id="s7"></a>

## 送った内容の記録

<div align="right"><a href="#top">▲ 目次へ</a></div>

ローカルモデルへ送るたびに、`logs/` に2つのファイルを書く（`log.debug_dump_all`）。

- `{時刻}_prompt.txt`: 送った文章の全文
- `{時刻}_params.json`: 生成の設定

プロンプトを直したときは、ここを見て、差し込み口が正しく置き換わっているかを確かめる。

<a id="s8"></a>

## 要確認の一覧（この文書の分）

<div align="right"><a href="#top">▲ 目次へ</a></div>

| 番号 | 対象 | 確認したいこと |
|---|---|---|
| Q38 | YAMLのキー | `message_header` を `header` に揃えるか |
| Q39 | 差し込み口 | 同じものの名前（`{first_mes}` と `{first_message}` など）を揃えるか |
| Q40 | 組み立て方 | 2通りあるのを1つに揃えるか |
| Q44 | 最大トークン数 | 判定は `judge`、返答は `chat` にするか |
