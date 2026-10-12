"""Web側(LLM_CHAT_CONSOLE)のJSの静的チェック。ブラウザを開かずに、すぐ落ちる種類の間違いを探す。

    py -3 .claude/skills/verify-ui/scripts/js_check.py              # 今のコードを検査
    py -3 .claude/skills/verify-ui/scripts/js_check.py --base main  # main と比べて増えた分だけ表示

見つけるもの:
- 構文エラー
- 宣言されていないのに使われている名前
  （例: 変数を消したのに console.log(消した変数) が残っている。実行するとその行でエラーになる）

各画面は js/constant.js → js/common.js → 画面のJS の順に読み込み、全部グローバルなので、
その3つを1組として検査する。

見つけられないもの:
- 見た目、クリックした時の動き、サーバーとのやり取り。これは screenshot.py や実機で確かめる。

構文解析に使う esprima(Python版) は ES2017 までしか読めないため、新しい書き方
（catch {}、?.、??）は検査の時だけ同じ意味の古い書き方に置き換えている。
元のファイルは書き換えない。
"""
import argparse
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _env  # noqa: E402

_env.utf8_stdout()
_env.run_in_venv(_env.default_sandbox())

import esprima  # noqa: E402  (venv に入ってから読み込む)

SHARED = ["js/constant.js", "js/common.js"]

# ブラウザが最初から持っている名前
BROWSER_GLOBALS = set("""
window document localStorage sessionStorage console fetch FormData File FileReader Blob URL URLSearchParams
JSON Error TypeError Array Object String Number Boolean Date Math Promise Set Map RegExp Symbol
setTimeout clearTimeout setInterval clearInterval requestAnimationFrame
encodeURIComponent decodeURIComponent parseInt parseFloat isNaN isFinite
undefined NaN Infinity alert confirm prompt navigator location history event Image getComputedStyle arguments
""".split())


def downlevel(source: str) -> str:
    source = re.sub(r"catch\s*\{", "catch (e) {", source)
    return source.replace("?.", ".").replace("??", "||")


def walk(node, visit):
    if isinstance(node, list):
        for item in node:
            walk(item, visit)
    elif hasattr(node, "type"):
        visit(node)
        for key, value in vars(node).items():
            if key in ("type", "range", "loc"):
                continue
            if isinstance(value, list) or hasattr(value, "type"):
                walk(value, visit)


def analyze(root: Path, files):
    """(構文エラーの一覧, 未宣言の名前 {名前: (ファイル, 行)}) を返す。"""
    errors, declared, used = [], set(), {}

    for rel in files:
        path = root / rel
        if not path.exists():
            continue
        try:
            tree = esprima.parseScript(downlevel(path.read_text(encoding="utf-8")), loc=True)
        except Exception as error:
            errors.append(f"構文エラー  {rel}: {str(error)[:120]}")
            continue

        skip = set()

        def declare(pattern):
            if pattern is None:
                return
            if pattern.type == "Identifier":
                declared.add(pattern.name)
            elif pattern.type == "ObjectPattern":
                for prop in pattern.properties:
                    declare(prop.value)
            elif pattern.type == "ArrayPattern":
                for element in pattern.elements:
                    declare(element)
            elif pattern.type == "AssignmentPattern":
                declare(pattern.left)
            elif pattern.type == "RestElement":
                declare(pattern.argument)

        def visit(node, rel=rel):
            kind = node.type
            if kind == "VariableDeclarator":
                declare(node.id)
            elif kind in ("FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"):
                if getattr(node, "id", None):
                    declared.add(node.id.name)
                    skip.add(id(node.id))
                for param in node.params:
                    declare(param)
            elif kind == "CatchClause":
                declare(node.param)
            elif kind == "MemberExpression" and not node.computed:
                skip.add(id(node.property))
            elif kind in ("Property", "MethodDefinition") and not node.computed:
                skip.add(id(node.key))
            elif kind == "LabeledStatement":
                skip.add(id(node.label))
            elif kind == "Identifier" and id(node) not in skip:
                used.setdefault(node.name, (rel, node.loc.start.line))

        walk(tree.body, visit)

    undefined = {name: where for name, where in used.items() if name not in declared and name not in BROWSER_GLOBALS}
    return errors, undefined


def pages(root: Path):
    """HTMLが読み込んでいるJSの組を返す。{画面名: [読み込み順のJS]}"""
    found = {}
    for html in sorted(root.glob("*.html")):
        scripts = re.findall(r'<script\s+src="([^"]+)"', html.read_text(encoding="utf-8"))
        scripts = [s.split("?")[0] for s in scripts if not s.startswith(("http:", "https:", "//"))]
        if scripts:
            found[html.name] = scripts
    return found


def check(root: Path):
    problems = []
    for page, scripts in pages(root).items():
        errors, undefined = analyze(root, scripts)
        problems += [f"{page}: {e}" for e in errors]
        problems += [f"{page}: 宣言されていない名前 {name}  ({rel})" for name, (rel, _line) in sorted(undefined.items())]
    return sorted(set(problems))


def lines_of(root: Path):
    """表示用に、未宣言の名前の行番号を引く。"""
    where = {}
    for page, scripts in pages(root).items():
        _errors, undefined = analyze(root, scripts)
        for name, (rel, line) in undefined.items():
            where[f"{page}: 宣言されていない名前 {name}  ({rel})"] = line
    return where


def export_base(repo: Path, ref: str) -> Path:
    """比較用に、指定したブランチ/コミットの中身を一時フォルダへ取り出す。作業ツリーには触れない。"""
    out = Path(tempfile.mkdtemp(prefix="js_check_base_"))
    archive = out / "web.zip"
    subprocess.run(["git", "-C", str(repo), "archive", "--format=zip", "-o", str(archive), ref], check=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(out / "web")
    return out / "web"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo", default=str(_env.WEB_REPO), help="LLM_CHAT_CONSOLE の場所")
    parser.add_argument("--base", help="比較元のブランチやコミット（例: main）。指定すると増えた分・減った分だけ表示")
    args = parser.parse_args()

    repo = Path(args.repo)
    current = check(repo)
    where = lines_of(repo)

    def show(problem, mark="  "):
        line = where.get(problem)
        print(f"{mark}{problem}" + (f" line {line}" if line else ""))

    print("検査した画面: " + ", ".join(pages(repo)))

    if args.base:
        base = check(export_base(repo, args.base))
        added = [p for p in current if p not in base]
        fixed = [p for p in base if p not in current]
        print(f"{args.base} との比較: 増えた {len(added)} 件、減った {len(fixed)} 件（変わらず {len(current) - len(added)} 件）")
        for p in added:
            show(p, "  + ")
        for p in fixed:
            print("  - " + p)
        failed = bool(added)
    else:
        print(f"{len(current)} 件")
        for p in current:
            show(p)
        failed = bool(current)

    print("\n問題があります。" if failed else "\n問題はありません。")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
