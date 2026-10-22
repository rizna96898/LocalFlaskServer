"""LLM_CHAT_CONSOLE の画面を、画面なしのブラウザ(Edge)で描画してスクリーンショットを撮る。

    py -3 .claude/skills/verify-ui/scripts/screenshot.py --page "person_card.html?kind=player" --out shot.png

リポジトリのコピーに対して実行するので、元のファイルは書き換えない。
撮れたPNGは Read ツールで開いて目で確かめる。

よく使う指定:
  --page FILE          開くHTML（既定: index_3column_session.html）。? 以降はURLに付く
                       （例: person_card.html?kind=player でプレイヤー設定の画面）
  --inject FILE.js     ページのJSの後に読み込ませるJS。ボタンを押す、ウィンドウを開く、など
                       画面を「見たい状態」にするために使う
  --storage KEY=VALUE  ページのJSより前に localStorage へ入れておく値（何度でも指定可）
  --hash TEXT          URLの # 以降。--inject のJSから location.hash で読める
  --size WxH           ウィンドウの大きさ（既定: 1280x900）
  --wait MS            描画を待つ時間（既定: 5000）。タイマーやアニメーションもこの時間ぶん進む
  --title              撮影後の document.title を表示する。--inject のJSで測った値を
                       document.title = JSON.stringify(...) と入れておけば、数値で受け取れる

注意:
- file:// で開くので、ページ内の fetch はローカルのファイルを読めない。
  サーバーが必要な表示は、--storage flask_base_url=... で動いているサーバーを指すか、
  --inject のJSで requestJson / postJson を差し替えて偽の返事を返す。
- 画像を使う確認は、--inject のJSで canvas から作ると外部ファイルが要らない。
"""
import argparse
import html
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _env  # noqa: E402

_env.utf8_stdout()

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_browser() -> str:
    for candidate in [os.environ.get("LLMCHAT_VERIFY_BROWSER"), *BROWSERS]:
        if candidate and Path(candidate).exists():
            return candidate
    for name in ("msedge", "chrome", "chromium", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("Edge / Chrome が見つかりません。LLMCHAT_VERIFY_BROWSER に実行ファイルのパスを指定してください。")


def copy_site(repo: Path, dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(repo, dest, ignore=shutil.ignore_patterns(".git", ".claude", "node_modules"))


def prepare_page(site: Path, page: str, inject: Path, storage: dict) -> Path:
    path = site / page
    if not path.exists():
        raise SystemExit(f"ページがありません: {page}")
    text = path.read_text(encoding="utf-8")

    if storage:
        seed = "".join(
            f"localStorage.setItem({_js(k)}, {_js(v)});" for k, v in storage.items()
        )
        tag = f"<script>try {{ {seed} }} catch (e) {{}}</script>"
        text, count = re.subn(r"(<head[^>]*>)", lambda m: m.group(1) + tag, text, count=1)
        if not count:
            text = tag + text

    if inject:
        shutil.copyfile(inject, site / "__verify_inject.js")
        tag = '<script src="__verify_inject.js"></script>'
        if "</body>" in text:
            text = text.replace("</body>", tag + "</body>", 1)
        else:
            text += tag

    path.write_text(text, encoding="utf-8")
    return path


def _js(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("</", "<\\/") + '"'


def run_browser(browser: str, profile: Path, url: str, size: str, wait: int, extra):
    width, height = size.lower().split("x")
    command = [
        browser, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
        f"--user-data-dir={profile}", f"--window-size={width},{height}",
        f"--virtual-time-budget={wait}", *extra, url,
    ]
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo", default=str(_env.WEB_REPO), help="LLM_CHAT_CONSOLE の場所")
    parser.add_argument("--page", default="index_3column_session.html")
    parser.add_argument("--inject", help="ページのJSの後に読み込ませるJSファイル")
    parser.add_argument("--storage", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--hash", default="")
    parser.add_argument("--size", default="1280x900")
    parser.add_argument("--wait", type=int, default=5000)
    parser.add_argument("--out", default="screenshot.png")
    parser.add_argument("--title", action="store_true", help="撮影後の document.title を表示する")
    args = parser.parse_args()

    # --page person_card.html?kind=player のように、? 以降はURLに付ける
    page_file, _, page_query = args.page.partition("?")

    repo = Path(args.repo)
    if not (repo / page_file).exists():
        raise SystemExit(f"{repo} に {page_file} がありません。")

    sandbox = _env.default_sandbox()
    site = sandbox / "ui" / "site"
    profile = sandbox / "ui" / "browser-profile"
    profile.mkdir(parents=True, exist_ok=True)

    storage = {}
    for item in args.storage:
        if "=" not in item:
            raise SystemExit(f"--storage は KEY=VALUE の形で指定してください: {item}")
        key, value = item.split("=", 1)
        storage[key] = value

    copy_site(repo, site)
    page = prepare_page(site, page_file, Path(args.inject).resolve() if args.inject else None, storage)

    url = page.resolve().as_uri() + (f"?{page_query}" if page_query else "") + (f"#{args.hash}" if args.hash else "")
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    browser = find_browser()
    run_browser(browser, profile, url, args.size, args.wait, [f"--screenshot={out}"])

    if not out.exists():
        print("スクリーンショットを作れませんでした。")
        return 1
    print(f"保存しました: {out}")

    if args.title:
        dumped = run_browser(browser, profile, url, args.size, args.wait, ["--dump-dom"]).stdout or ""
        found = re.search(r"<title>(.*?)</title>", dumped, re.S)
        print("document.title: " + (html.unescape(found.group(1)) if found else "(取得できませんでした)"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
