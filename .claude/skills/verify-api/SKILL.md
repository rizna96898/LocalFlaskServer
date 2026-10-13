---
name: verify-api
description: LocalFlaskServer（サーバー側AP）の変更を、本物のデータやモデルに触れずに確かめる。リポジトリのコピーと専用の venv を一時フォルダに作り、Flask の test_client で実際にAPIを呼ぶ。src/ 配下の Python を変更・削除・改名したとき、APIのレスポンスやリクエストの項目を変えたとき、「検証して」「動作確認して」「壊れてないか見て」「テストして」と言われたとき、PRを作る前には必ず使う。このリポジトリにはテストもリンターも無く、作業するPCにはFlaskも入っていないので、このスキルを使わないと「構文は通るが呼ぶと落ちる」変更を見逃す。
---

# サーバーAPIの検証

このリポジトリには自動テストが無く、普段は人が画面から操作して確かめている。
しかも編集するPC（メインPC）にはFlaskが入っておらず、リポジトリ内の `venv/` はサブPC用で動かない。
そのため、何もしなければ「構文は通るが、呼ぶと必ず落ちる」変更をそのままPRに出してしまう。
実際に過去、引数の数が合わない関数や、存在しない関数の呼び出しが、誰にも気づかれずに残っていた。

このスキルは、その隙間を埋めるための道具をまとめたもの。
検証は一時フォルダのコピーに対して行うので、セッションのデータ・設定ファイル・ログ・モデルには一切触れない。

## 手順

変更の大きさに応じて、上から順に使う。どれもリポジトリのルートで実行する。

### 1. 静的チェック（数秒）

```
py -3 .claude/skills/verify-api/scripts/static_check.py --base main
```

`main` と比べて増えた問題だけを表示する。関数やファイルを消した・改名したときは、まずこれ。
存在しない import、存在しない関数・属性の参照、存在しないメソッドの呼び出しを見つける。
`--unreachable` を付けると、どのルートからも届かない関数も出す（不要コードを探すとき用）。

これで分かるのは「名前が存在するか」だけ。引数の数や、実行して初めて分かる間違いは見つからない。

同じコマンドが、**APIキーの混入**も調べる（`secret_scan.py`）。Git から見えるファイルに鍵らしい文字列があると、場所を示して失敗する。このリポジトリは公開なので、鍵をコミットすると取り返しがつかない。コミットの前に必ず通す。

### 2. スモークテスト（初回のみ環境構築に1〜2分、以降は数秒）

```
py -3 .claude/skills/verify-api/scripts/api_smoke.py
```

全APIを一通り実際に呼び、70項目あまりを確かめる。最後に `結果: N/N 成功` と出る。
`NG` の行があれば、そこに期待との違いと返ってきた本文が出る。原因を追うときは `--verbose` を付けると、サーバーのログも表示される。

変更に関係なさそうでも、PRの前には一度通す。レスポンスの形や画像の保存先のような「サーバーとWebの約束事」は、思わぬ所で壊れるため。

### 3. 変更した箇所そのものを確かめる

スモークテストは「全体が壊れていないこと」の確認で、**今回の変更が意図どおり動くこと**までは見ていない。
新しく足した動作や、直した不具合は、それ専用の確認を書いて実際に呼ぶ。

`scripts/sandbox.py` を使うと短く書ける。スクリプトは scratchpad など一時的な場所に置けばよい。

```python
import sys
sys.path.insert(0, r"z:\LocalFlaskServer\.claude\skills\verify-api\scripts")
import _env, sandbox

_env.utf8_stdout()
_env.run_in_venv(_env.default_sandbox())   # 専用 venv の Python で実行し直す

box = sandbox.prepare()                     # 両リポジトリのコピーを作り直す
client = box.client()                       # Flask の test_client
t = sandbox.Checker()

body = t.api(client, "世界を選ぶ", "post", "/world_start", 200, True, ["sessions"],
             json={"world_id": "kakko_clinic", "world_name": "カッコウ医院編"})
t.check("セッションは空", body["sessions"] == [])

sys.exit(t.finish())
```

- `box.base_chat_path` … 画面が送る `base_chat_path` に相当する値（Web側のコピーの場所）
- `box.web`、`box.server` … コピーの場所。保存されたファイルの中身を直接確かめられる
- `box.worlds()`、`box.characters_with_images()` … リポジトリにある実データのID
- `box.write_settings("port: 5050\n")` … 設定を変えて試す。`client()` より前に呼ぶ
- `box.generation_file` … 生成の設定（`generation.yaml`）のコピー。書き換えて、送信に反映されるかを試せる
- `box.wait_background()` … `/new_chat` が裏で始める記憶生成スレッドの終了を待つ

### 4. 既存のスモークテストを育てる

APIを足した・形を変えたときは、`scripts/api_smoke.py` にもその確認を足す。
次に誰かが別の変更をしたとき、黙って壊れるのを防げる。

## モデルの扱い

検証からは、本物のモデルサーバーを呼ばない。`box.client()` がモデルへの送信を差し替えている。

| 指定 | 動き |
|---|---|
| `box.client()` | モデルサーバーに接続できない扱い。`/chat` は500になる |
| `box.client(llm="現在の状態:\n  ...")` | その文字列をモデルの返事として返す |
| `box.client(llm=lambda prompt: ...)` | プロンプトに応じて返事を変える |
| `box.client(llm=sandbox.scripted_llm)` | 段階ごとにそれらしい返事を返す。初期記憶の生成を最後まで走らせられる |

送られたプロンプトは `box.llm_calls` に、送信した内容の全体（`prompt`、`stop`、温度など）は `box.llm_requests` に溜まるので、「どんなプロンプトを、どんな設定で送ったか」を確かめられる。

記憶生成のように、モデルの返事を決まった形（YAML）として読む処理は、偽の返事が形に合っていないと途中で止まる。
それは検証の都合で起きることで、変更の不具合ではない。どこまで進んだかはサーバーのログ（`--verbose`）で分かる。

## 確かめられないこと

次は、この方法では確認できない。PRの説明と、ユーザーへの報告に「未確認」として書き、実機での確認を頼む。

- 本物のモデルを使った応答と記憶生成の完走
- フォルダ選択ダイアログ、設定YAMLをエディタで開く動作（サーバーを動かしているPCの画面に出るもの）
- 実際のポートでの待ち受け、サブPCでの起動
- 画面側の表示や操作（`verify-ui` スキルを使う）

## 仕組みと置き場所

- 検証用フォルダは既定で `%TEMP%\llmchat-verify`（環境変数 `LLMCHAT_VERIFY_DIR` で変更可）。消しても次回作り直される
- `venv/` … 専用の Python 環境。flask、flask-cors、pyyaml、requests、pillow、esprima が入る
- `server/` … `src/`、`files/prompts/`、`files/templates/` のコピー。`sessions/` と `sessions_list.yaml` は毎回空から始める
- `web/` … LLM_CHAT_CONSOLE の `characters/`、`players/`、`worlds/` のコピー
- 設定ファイル（`system_settings.yaml`）と秘密の値（`secrets.yaml`）はコピーしない。検証用の最小の設定を新しく書いている
- 生成の設定（`generation.yaml`）は、秘密の値を含まないので本物をコピーする
- `llama_cpp` は偽物に差し替えるので、`src/server.py` を import してもモデルは読み込まれない
