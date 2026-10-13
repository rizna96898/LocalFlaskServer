"""Git から見えるファイルに、APIキーらしい文字列が入っていないかを調べる。

    py -3 .claude/skills/verify-api/scripts/secret_scan.py           # このリポジトリ
    py -3 .claude/skills/verify-api/scripts/secret_scan.py --all     # LLM_CHAT_CONSOLE も

調べる範囲は「Git が管理しているファイル」と「まだ管理していないが、.gitignore で除外もされていないファイル」。
つまり、git add すればコミットに入りうるもの全部。.gitignore で除外しているファイル（secrets.yaml など）は調べない。

このリポジトリは公開(PUBLIC)で、過去に一度、APIキーの入った設定ファイルをコミットしてしまったことがある
（鍵はその後作り直して無効にしてある）。同じことを繰り返さないための検査で、コミットの前に通す。
static_check.py からも毎回呼ばれる。

見つけても、鍵の値そのものは表示しない（先頭と末尾の数文字だけ）。
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _env  # noqa: E402

# 鍵の形。左が名前、右が正規表現
PATTERNS = [
    ("OpenRouter のAPIキー", re.compile(r"sk-or-[A-Za-z0-9_-]{10,}")),
    ("Anthropic のAPIキー", re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}")),
    ("OpenAI 形式のAPIキー", re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{32,}")),
    ("GitHub のトークン", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("Hugging Face のトークン", re.compile(r"hf_[A-Za-z0-9]{30,}")),
    ("AWS のアクセスキー", re.compile(r"AKIA[0-9A-Z]{16}")),
]

SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".gguf", ".pyc", ".lnk", ".zip"}
MAX_BYTES = 2_000_000


def visible_files(repo: Path):
    """Git が管理しているファイル ＋ 管理も除外もしていないファイル。"""
    out = set()
    for args in (["ls-files"], ["ls-files", "--others", "--exclude-standard"]):
        result = subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=false", *args],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        out |= {line for line in result.stdout.splitlines() if line}
    return sorted(out)


def mask(value: str) -> str:
    return value[:8] + "…" + value[-4:] + f"（{len(value)}文字）"


def scan(repo: Path):
    """[(ファイル, 行番号, 種類, 伏せ字にした値)] を返す。"""
    found = []
    for rel in visible_files(repo):
        path = repo / rel
        if path.suffix.lower() in SKIP_SUFFIX or not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for name, pattern in PATTERNS:
                for match in pattern.finditer(line):
                    found.append((rel, number, name, mask(match.group(0))))
    return found


def main() -> int:
    _env.utf8_stdout()

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--all", action="store_true", help="LLM_CHAT_CONSOLE も調べる")
    args = parser.parse_args()

    repos = [_env.SERVER_REPO] + ([_env.WEB_REPO] if args.all else [])
    total = 0
    for repo in repos:
        found = scan(repo)
        total += len(found)
        print(f"{repo.name}: {len(visible_files(repo))} ファイルを調べ、{len(found)} 件")
        for rel, number, name, masked in found:
            print(f"  {rel}:{number}  {name}  {masked}")

    if total:
        print("\nAPIキーらしい文字列があります。コミットしないでください。")
        print("秘密の値は files/settings/secrets.yaml（Git 管理外）に書きます。")
        return 1
    print("\nAPIキーらしい文字列はありません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
