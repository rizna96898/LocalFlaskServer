"""サーバー側コードの静的チェック。起動せずに、呼ぶと必ず落ちる種類の間違いを探す。

    py -3 .claude/skills/verify-api/scripts/static_check.py              # 今のコードを検査
    py -3 .claude/skills/verify-api/scripts/static_check.py --base main  # main と比べて増えた分だけ表示
    py -3 .claude/skills/verify-api/scripts/static_check.py --unreachable  # どこからも呼ばれない関数も表示

見つけるもの:
- 構文エラー
- 存在しないモジュール・名前の import        （例: from helpers import 消したファイル）
- 自作モジュールに存在しない関数・属性の参照  （例: response_checker._json_ok）
- クラス内に存在しないメソッドの呼び出し      （例: self._load）
- 使われなくなった自作モジュールの import

見つけられないもの:
- 引数の数や型の間違い、実行時にしか決まらない名前。これは api_smoke.py で実際に呼んで確かめる。

名前の文字列だけで判定している。動的な呼び出し(getattr など)はこのコードベースでは使っていない前提。
"""
import argparse
import ast
import io
import subprocess
import sys
import tempfile
import tokenize
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _env  # noqa: E402

_env.utf8_stdout()


def load(root: Path):
    mods = {}
    problems = []
    for path in sorted(root.rglob("*.py")):
        name = ".".join(path.relative_to(root).with_suffix("").parts)
        if name.endswith(".__init__"):
            name = name[: -len(".__init__")]
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError as error:
            problems.append(f"構文エラー          {name}: {error.msg} (line {error.lineno})")
            continue

        top, classes = set(), {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                top.add(node.name)
            if isinstance(node, ast.ClassDef):
                classes[node.name] = {m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if isinstance(node, ast.Assign):
                top |= {t.id for t in node.targets if isinstance(t, ast.Name)}
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                top |= {(a.asname or a.name).split(".")[0] for a in node.names}
        mods[name] = dict(path=path, text=text, tree=tree, top=top, classes=classes)
    return mods, problems


def check(root: Path):
    """問題の一覧を返す。行番号は比較の邪魔になるので文字列に含めない。"""
    mods, problems = load(root)
    packages = set(mods) | {m.rsplit(".", 1)[0] for m in mods if "." in m}
    roots = {m.split(".")[0] for m in mods}

    for name, mod in mods.items():
        alias = {}
        for node in ast.walk(mod["tree"]):
            if isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    full = f"{node.module}.{a.name}"
                    if full in mods:
                        alias[a.asname or a.name] = full
                    elif node.module in mods:
                        if a.name not in mods[node.module]["top"]:
                            problems.append(f"存在しない名前のimport {name}: from {node.module} import {a.name}")
                    elif node.module.split(".")[0] in roots and full not in packages:
                        problems.append(f"存在しないモジュール   {name}: from {node.module} import {a.name}")
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in mods:
                        alias[a.asname or a.name.split(".")[-1]] = a.name

        for node in ast.walk(mod["tree"]):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                target = alias.get(node.value.id)
                if target and node.attr not in mods[target]["top"]:
                    problems.append(f"存在しない関数・属性   {name}: {node.value.id}.{node.attr}")

        for cls in [n for n in mod["tree"].body if isinstance(n, ast.ClassDef)]:
            attrs = set(mod["classes"][cls.name])
            for node in ast.walk(cls):
                if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                        and node.value.id == "self" and isinstance(node.ctx, ast.Store)):
                    attrs.add(node.attr)
            for node in ast.walk(cls):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == "self"
                        and node.func.attr not in attrs):
                    problems.append(f"存在しないメソッド     {name}: self.{node.func.attr}")

        used = {n.id for n in ast.walk(mod["tree"]) if isinstance(n, ast.Name)}
        for local, full in alias.items():
            if local not in used:
                problems.append(f"未使用のimport        {name}: {local} ({full})")

    return sorted(set(problems))


def unreachable(root: Path):
    """ルート（デコレーター付きの関数＝Flaskのルート、モジュール直下のコード）から辿って届かない関数。

    同じ名前の関数がどこかで使われていれば「使用中」と見なす、控えめな判定。
    ここに出たものは消せる可能性が高いが、出なかったものが全部使用中とは限らない。
    """
    mods, _ = load(root)
    defs = []
    for name, mod in mods.items():
        for node in mod["tree"].body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([node.lineno] + [d.lineno for d in node.decorator_list])
                defs.append(dict(mod=name, qual=node.name, name=node.name, start=start, end=node.end_lineno,
                                 line=node.lineno, kind="func", deco=bool(node.decorator_list)))
            elif isinstance(node, ast.ClassDef):
                defs.append(dict(mod=name, qual=node.name, name=node.name, start=node.lineno, end=node.end_lineno,
                                 line=node.lineno, kind="class", deco=False))
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        defs.append(dict(mod=name, qual=f"{node.name}.{sub.name}", name=sub.name, start=sub.lineno,
                                         end=sub.end_lineno, line=sub.lineno, kind="method", deco=False))

    def owner(mod, line):
        best = None
        for d in defs:
            if d["mod"] == mod and d["start"] <= line <= d["end"]:
                if best is None or (d["end"] - d["start"]) < (best["end"] - best["start"]):
                    best = d
        return best

    refs = {id(d): set() for d in defs}
    module_refs = set()
    for name, mod in mods.items():
        for tok in tokenize.generate_tokens(io.StringIO(mod["text"]).readline):
            if tok.type != tokenize.NAME:
                continue
            o = owner(name, tok.start[0])
            if o is None:
                module_refs.add(tok.string)
            elif o["kind"] == "class":
                if not (tok.start[0] == o["line"] and tok.string == o["name"]):
                    module_refs.add(tok.string)
                    refs[id(o)].add(tok.string)
            elif not (tok.start[0] == o["line"] and tok.string == o["name"]):
                refs[id(o)].add(tok.string)

    by_name = {}
    for d in defs:
        by_name.setdefault(d["name"], []).append(d)

    reached, stack = set(), []

    def mark(d):
        if id(d) not in reached:
            reached.add(id(d))
            stack.append(d)

    for d in defs:
        if d["deco"]:
            mark(d)
    for n in module_refs:
        for d in by_name.get(n, []):
            mark(d)
    while stack:
        d = stack.pop()
        if d["kind"] == "class":
            for m in defs:
                if m["mod"] == d["mod"] and m["kind"] == "method" and m["qual"].startswith(d["name"] + ".") \
                        and m["name"].startswith("__"):
                    mark(m)
        for n in refs[id(d)]:
            for target in by_name.get(n, []):
                mark(target)

    dead = [d for d in defs if id(d) not in reached]
    return [f"届かない              {d['mod']}: {d['qual']}  ({d['end'] - d['start'] + 1}行, line {d['start']})"
            for d in sorted(dead, key=lambda d: (d["mod"], d["start"]))]


def export_base(repo: Path, ref: str) -> Path:
    """比較用に、指定したブランチ/コミットの src/ を一時フォルダへ取り出す。作業ツリーには触れない。"""
    out = Path(tempfile.mkdtemp(prefix="static_check_base_"))
    archive = out / "src.zip"
    subprocess.run(["git", "-C", str(repo), "archive", "--format=zip", "-o", str(archive), ref, "src"], check=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(out)
    return out / "src"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo", default=str(_env.SERVER_REPO), help="LocalFlaskServer の場所")
    parser.add_argument("--base", help="比較元のブランチやコミット（例: main）。指定すると増えた分・減った分だけ表示")
    parser.add_argument("--unreachable", action="store_true", help="どこからも呼ばれない関数も表示")
    args = parser.parse_args()

    repo = Path(args.repo)
    current = check(repo / "src")
    if args.unreachable:
        current += unreachable(repo / "src")

    if args.base:
        base_src = export_base(repo, args.base)
        base = check(base_src) + (unreachable(base_src) if args.unreachable else [])
        added = [p for p in current if p not in base]
        fixed = [p for p in base if p not in current]
        print(f"{args.base} との比較: 増えた {len(added)} 件、減った {len(fixed)} 件（変わらず {len(current) - len(added)} 件）")
        for p in added:
            print("  + " + p)
        for p in fixed:
            print("  - " + p)
        serious = [p for p in added if not p.startswith(("未使用のimport", "届かない"))]
    else:
        print(f"{len(current)} 件")
        for p in current:
            print("  " + p)
        serious = [p for p in current if not p.startswith(("未使用のimport", "届かない"))]

    if serious:
        print(f"\n呼ぶと落ちる種類の問題が {len(serious)} 件あります。")
        return 1
    print("\n呼ぶと落ちる種類の問題はありません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
