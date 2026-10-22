---
name: verify-ui
description: LLM_CHAT_CONSOLE（Web側の画面、z:\LLM_CHAT_CONSOLE）の変更を、ブラウザを手で開かずに確かめる。JSの構文と未宣言の変数を検査し、Edge を画面なしで起動してスクリーンショットを撮り、見た目を目で確認する。HTML・CSS・JS を変更したとき、ボタンやウィンドウの見た目を作った・直したとき、「画面を確認して」「見た目どうなった？」「表示が崩れてないか見て」と言われたとき、Web側のPRを作る前には必ず使う。Web側にはビルドもテストも無く、消した変数への参照のような間違いは実行するまで分からないので、このスキルを使わないとそのまま見逃す。
---

# 画面の検証

LLM_CHAT_CONSOLE はビルドなしの素の HTML / CSS / JS で、テストもリンターも無い。
普段は人がブラウザで開いて確かめているので、何もしなければ「書いたが一度も描画していない」変更をPRに出すことになる。

過去に実際にあった見逃し:

- 変数を消したのに、それを使うログ出力が残っていた（実行するとその行でエラーになる）
- アイコン切り抜きウィンドウのHTMLとJSはあるのに、CSSが一度もコミットされていなかった

このスキルは、こうした間違いを手元で見つけるための道具をまとめたもの。
どれもリポジトリのコピーに対して動くので、元のファイルやブラウザの設定には触れない。

スクリプトは LocalFlaskServer 側の `.claude/skills/verify-ui/` にある。
実行は LocalFlaskServer のルートから行う（Web側のリポジトリは `z:\LLM_CHAT_CONSOLE` を自動で見に行く）。

## 手順

### 1. JSの静的チェック（数秒）

```
py -3 .claude/skills/verify-ui/scripts/js_check.py --base main
```

全画面について、構文エラーと「宣言されていないのに使われている名前」を調べ、`main` より増えた分だけ表示する。
JSを触ったら、まずこれを通す。

各画面は `js/constant.js` → `js/common.js` → 画面のJS の順に読み込み、全部グローバルなので、その組ごとに検査している。
見つけられるのは名前の有無だけで、動きの正しさは分からない。

### 2. スクリーンショットで見た目を確かめる

```
py -3 .claude/skills/verify-ui/scripts/screenshot.py --page "person_card.html?kind=character" --out <保存先>.png
```

撮れたPNGは **Read ツールで開いて、自分の目で見る**。撮っただけで「確認した」ことにしない。
見るときは、崩れ・はみ出し・重なり・文字切れ・意図した要素が出ているか、を確かめる。

保存先は scratchpad など一時的な場所にする。リポジトリの中に置くと、うっかりコミットしてしまう。

主な指定:

| 指定 | 用途 |
|---|---|
| `--page FILE` | 開くHTML。既定は `index_3column_session.html`。`?` 以降はURLに付く（`person_card.html?kind=player` でプレイヤー設定） |
| `--inject FILE.js` | ページのJSの後に読み込ませるJS。画面を「見たい状態」にする |
| `--storage KEY=VALUE` | ページのJSより前に `localStorage` へ入れる値。何度でも指定できる |
| `--hash TEXT` | URLの `#` 以降。`--inject` のJSから `location.hash` で読める |
| `--size WxH` | ウィンドウの大きさ。既定は `1280x900` |
| `--title` | 撮影後の `document.title` を表示する（下の「数値で確かめる」を参照） |

### 3. 見たい状態を作る（`--inject`）

開いただけでは、ボタンを押した後のウィンドウや、データが入った状態は撮れない。
小さなJSを書いて `--inject` で渡し、ページの関数を直接呼んだり、ボタンを押したりして、その状態にしてから撮る。

`examples/open_icon_cropper.js` が実例。キャラクター画面でアイコン切り抜きウィンドウを開き、OKを押した後まで撮れる。

```
py -3 .claude/skills/verify-ui/scripts/screenshot.py --page "person_card.html?kind=character" ^
    --inject .claude/skills/verify-ui/examples/open_icon_cropper.js --title --out cropper.png
```

書くときの要点:

- ページの関数や変数は全部グローバルなので、そのまま呼べる
- 画像が必要なら canvas で作る。`file://` で開くので、ページ内の `fetch` はローカルのファイルを読めない
- 状態が落ち着くまで `setTimeout` で少し待ってから、次の操作や計測をする
- 「開いた状態」「OKを押した後」のように、状態ごとに `--hash` を変えて複数枚撮る

### 4. 数値で確かめる（`--title`）

見た目だけでは分からない一致・不一致は、数値で比べる。
`--inject` のJSで測った値を `document.title = JSON.stringify(...)` と入れておけば、`--title` で受け取れる。

たとえば切り抜きウィンドウでは、CSSで描いた枠の位置と、JSが切り抜きに使う計算値が一致していないと、
「枠で囲んだ範囲」と「実際に切り抜かれる範囲」がずれる。これはスクリーンショットを眺めても気づきにくいので、
両方の値を出して比べている。

## サーバーが必要な画面

`file://` で開いたページからでも、動いているサーバーへの通信はできる。

- **本物のサーバーにつなぐ**: `--storage flask_base_url=http://192.168.x.x:5000 --storage base_chat_path=E:\LLM_CHAT_CONSOLE`
  表示の確認には手軽だが、保存や削除のボタンを押すJSを `--inject` で流すと本物のデータが変わるので、読み取りだけにする
- **偽の返事を返す**: `--inject` のJSで `postJson` / `requestJson` を差し替える。データに触れず、エラー時の表示も作れる

```js
// 例: セッション一覧と履歴を偽の返事にする
const fake = {
  "/load_session_list": { ok: true, sessions: [{ session_id: "s1", display_name: "テスト-1", world_id: "w", updated_at: "2026年10月12日 10:00" }] },
  "/selected_session": { ok: true, session_id: "s1", message_list: [{ line_id: "1", message: "こんにちは", icon_data: { character_id: "shirai_yui", character_name: "白井　結" } }] },
};
window.requestJson = async (path) => fake[path] || { ok: true };
```

`postJson` は中で `requestJson` を呼ぶので、`requestJson` を差し替えれば両方に効く。
サーバー側の動きまで確かめたいときは、`verify-api` スキルを使う。

## 確かめられないこと

次は、この方法では確認できない。PRの説明と、ユーザーへの報告に「未確認」として書き、実機での確認を頼む。

- ドラッグ、スクロール、スライダーなど、連続した操作の手触り
- iframe で埋め込まれた子画面どうしの連携（メイン画面とキャラクター画面など）の実際の動き
- 実際のサーバー・モデルとつないだ一連の流れ

## 仕組みと置き場所

- 作業用フォルダは既定で `%TEMP%\llmchat-verify`（`verify-api` と共通。環境変数 `LLMCHAT_VERIFY_DIR` で変更可）
- `ui/site/` … 撮影のたびに作り直す、LLM_CHAT_CONSOLE のコピー。`--inject` と `--storage` はここのHTMLに差し込まれる
- `ui/browser-profile/` … 撮影専用のブラウザ設定。普段使いのEdgeの設定や履歴とは別
- ブラウザは Edge、次に Chrome を探す。別の場所にある場合は環境変数 `LLMCHAT_VERIFY_BROWSER` に実行ファイルのパスを入れる
- `js_check.py` が使う構文解析（esprima の Python 版）は ES2017 までしか読めない。`catch {}`、`?.`、`??` は検査のときだけ
  同じ意味の古い書き方に置き換えている。それ以外の新しい構文を使うと「構文エラー」と出ることがあるが、その場合は
  ブラウザでは動く可能性があるので、スクリーンショットで実際に描画して確かめる
