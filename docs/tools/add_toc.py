"""マークダウンの文書に、先頭の目次と、各見出しの「目次へ」リンクを付ける。

    py -3 docs/tools/add_toc.py                 # このリポジトリと LLM_CHAT_CONSOLE の docs/ 全部
    py -3 docs/tools/add_toc.py docs/status.md  # 指定したファイルだけ
    py -3 docs/tools/add_toc.py --check         # 作り直しが必要なファイルを表示するだけ（書き換えない）

文書を直したら（見出しを足す・消す・改名する）、もう一度実行して目次を作り直す。
何度実行しても同じ結果になる。前回付けた目次とリンクは、いったん取り除いてから付け直す。

付けるもの:
- 題名（# 見出し）のすぐ下に、## と ### の見出しへのリンクを並べた目次
- ## と ### の見出しの下に、右寄せの「▲ 目次へ」リンク

リンク先は、見出しの文字からではなく、見出しの前に置いた目印（<a id="s1-2"></a>）で決める。
見出しに日本語・記号・コードが入っていても、表示するソフト（VS Code、GitHub）の違いに左右されない。
"""
import argparse
import re
import sys
from pathlib import Path

SERVER_REPO = Path(__file__).resolve().parents[2]
WEB_REPO = SERVER_REPO.parent / "LLM_CHAT_CONSOLE"

TOP = '<a id="top"></a>'
TOC_START = "<!-- toc:start -->"
TOC_END = "<!-- toc:end -->"
BACK = '<div align="right"><a href="#top">▲ 目次へ</a></div>'
ANCHOR = re.compile(r'^<a id="s\d+(-\d+)?"></a>$')
FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{1,3}) +(.+?)\s*$")


def strip_generated(lines):
    """前回付けた目次・目印・「目次へ」を取り除き、元の文書に戻す。"""
    out, in_toc = [], False
    for line in lines:
        if line == TOC_START:
            in_toc = True
            continue
        if line == TOC_END:
            in_toc = False
            continue
        if in_toc or line in (TOP, BACK) or ANCHOR.match(line):
            continue
        out.append(line)

    # 取り除いた跡の、連続した空行を1つにまとめる（コードブロックの中は触らない）
    cleaned, in_fence = [], False
    for line in out:
        if FENCE.match(line):
            in_fence = not in_fence
        if not in_fence and line == "" and cleaned and cleaned[-1] == "":
            continue
        cleaned.append(line)
    return cleaned


def link_text(heading: str) -> str:
    """目次に出す文字。見出しの中のリンク記法は、文字だけにする。"""
    return re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", heading)


def build(text: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = strip_generated(text.replace("\r\n", "\n").split("\n"))

    # 見出しを集める（コードブロックの中の # は見出しではない）
    headings, in_fence = [], False
    for index, line in enumerate(lines):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2)))

    title = next((h for h in headings if h[1] == 1), None)
    sections = [h for h in headings if h[1] in (2, 3)]
    if title is None or not sections:
        return text

    # 目印の名前を決める: ## は s1, s2…、### は s1-1, s1-2…
    ids, major, minor = {}, 0, 0
    for index, level, _ in sections:
        if level == 2:
            major, minor = major + 1, 0
            ids[index] = f"s{major}"
        else:
            minor += 1
            ids[index] = f"s{major}-{minor}"

    toc = [TOC_START, "**目次**", ""]
    for index, level, heading in sections:
        toc.append(f'{"  " if level == 3 else ""}- [{link_text(heading)}](#{ids[index]})')
    toc.append(TOC_END)

    out = []
    for index, line in enumerate(lines):
        if index in ids:
            if out and out[-1] != "":
                out.append("")
            out += [f'<a id="{ids[index]}"></a>', "", line, "", BACK]
            continue
        out.append(line)
        if index == title[0]:
            out += ["", TOP, "", *toc]

    # 付けた行の前後の空行を整える
    result = []
    for line in out:
        if line == "" and result and result[-1] == "":
            continue
        result.append(line)
    return newline.join(result)


def targets(args):
    if args.files:
        return [Path(f) for f in args.files]
    found = []
    for repo in (SERVER_REPO, WEB_REPO):
        docs = repo / "docs"
        if docs.exists():
            found += sorted(p for p in docs.rglob("*.md"))
    return found


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("files", nargs="*", help="対象のファイル。省略すると両リポジトリの docs/ 全部")
    parser.add_argument("--check", action="store_true", help="書き換えずに、作り直しが必要なファイルを表示する")
    args = parser.parse_args()

    stale = 0
    for path in targets(args):
        before = path.read_bytes().decode("utf-8")
        after = build(before)
        if after == before:
            print(f"そのまま  {path}")
            continue
        stale += 1
        if args.check:
            print(f"要更新    {path}")
        else:
            path.write_bytes(after.encode("utf-8"))
            print(f"更新した  {path}")

    return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
