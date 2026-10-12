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
  - [返事の後始末](#s5-2)
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

```
### Instruction:
（system の内容）
### Instruction:
（user の内容）
### Response:
```

モデルは `### Response:` の続きを書く。

- **【要確認 Q41】** system も user も同じ `### Instruction:` という見出しになる。この形は、以前使っていたモデル（mythomax）に
  合わせたものと思われ、今のモデル（Qwen3）が学習している会話の形式とは違う。モデルに合わせた形式に変えるか。
  空の返事（[`../status.md`](../status.md)）との関係は確かめていないが、試す価値はある。

<a id="s5-2"></a>

### 返事の後始末

<div align="right"><a href="#top">▲ 目次へ</a></div>

返ってきた文章から、次のものを取り除いてから使う（`cleanup_model_output`、`strip_code_block`）。

- `<think>` 〜 `</think>` の部分（思考の過程）
- `### Response:` が混ざっていた場合、その前の部分
- 前後のコードブロックの記号（```` ``` ````）

返事が空だった場合は、同じ内容であと2回まで送り直す。それでも空なら失敗とする。

<a id="s6"></a>

## 生成の設定

<div align="right"><a href="#top">▲ 目次へ</a></div>

用途ごとに、コード（`memory_builders/use_memory_constant.py`、`chat_builders/use_chat_constant.py`）で決めている。

| 用途 | 温度 | `top_p` | `top_k` | 繰り返し抑制 | 打ち切る文字列 | 思考タグの抑制 |
|---|---|---|---|---|---|---|
| 世界の記憶 | 0.5 | 0.9 | 0 | 1.1 | なし | 弱い（-5） |
| キャラクター: 要約 | 0.5 | 0.9 | 0 | 1.1 | なし | 弱い（-5） |
| キャラクター: 分類・場所・服装・金額 | 0.5 | 0.9 | 0 | 1.1 | `### Instruction:` | 最大（-100） |
| キャラクター: 所持品 | 0.5 | 0.9 | 0 | 1.1 | `### Instruction:` | 強い（-90） |
| キャラクター: 意識 | 0.5 | 0.9 | 0 | 1.1 | `### Instruction:` | 強い（-80） |
| 誰に向けた発言かの判定 | 0.5 | 0.9 | 0 | 1.1 | なし | 弱い（-5） |

- 「打ち切る文字列」は、モデルがそこまで書いたら生成を止める指定。答えのあとに、次の質問まで勝手に書き続けるのを防ぐ。
- 「思考タグの抑制」は `logit_bias` という設定で、特定の語（番号 `248068`）を出にくくする。数値が小さいほど強く抑える。
  返事の頭に思考の過程を書き始めるのを防ぐ目的と思われる。
- **【要確認 Q42】** 番号 `248068` が何の語を指すかは確かめていない（今のモデルの `<think>` と思われる）。
  モデルを替えると、同じ番号が別の語を指すので、意図しない語を抑えることになる。モデルごとに設定を持つべきか。
- **【要確認 Q43】** 抑制の強さが、用途によって -5、-80、-90、-100 とまちまち。試しながら調整した結果と思われるが、それぞれの値に意図があるか。

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
| Q41 | モデルへ送る形 | 今のモデル（Qwen3）に合わせた形式に変えるか |
| Q42 | 思考タグの抑制 | モデルごとに設定を持つか |
| Q43 | 思考タグの抑制 | 用途ごとの値の違いに意図があるか |
| Q44 | 最大トークン数 | 判定は `judge`、返答は `chat` にするか |
