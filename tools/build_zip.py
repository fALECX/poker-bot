"""Build and audit the submission ZIP (dev only).

    python tools/build_zip.py [--out dist/submission.zip] [--no-play]

Checks: main.py at the root; exactly one Bot subclass in main.py; imports
limited to the standard library, numpy, macpoker and the bundled package;
no network / process / thread modules; no file writes; at most 300 files and
20 MB unpacked. Then extracts the archive to a temporary directory and plays
production-parity subprocess games from the extracted copy.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scaffold"
MAX_FILES = 300
MAX_BYTES = 20 * 1024 * 1024

FORBIDDEN_MODULES = {
    "socket", "http", "urllib", "urllib3", "requests", "ftplib", "smtplib", "ssl",
    "subprocess", "threading", "multiprocessing", "concurrent", "asyncio", "signal",
    "ctypes", "sched", "selectors", "webbrowser", "xmlrpc", "telnetlib", "pickle", "shutil",
}
ALLOWED_THIRD_PARTY = {"numpy", "macpoker", "pokerbot"}
FORBIDDEN_CALLS = {"open", "exec", "eval", "compile", "__import__", "system", "popen", "fork"}


def collect_files() -> list[Path]:
    files = []
    for p in sorted(SRC.rglob("*")):
        if p.is_dir() or "__pycache__" in p.parts or p.suffix in (".pyc", ".pyo"):
            continue
        if p.name == "README.md":
            continue
        files.append(p)
    return files


def audit_source(path: Path, rel: str, problems: list[str]) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    stdlib = set(sys.stdlib_module_names)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import inside our package
                continue
            names = [node.module or ""]
        else:
            names = []
        for name in names:
            top = name.split(".")[0]
            if top in FORBIDDEN_MODULES:
                problems.append(f"{rel}: forbidden import {name}")
            elif top not in stdlib and top not in ALLOWED_THIRD_PARTY:
                problems.append(f"{rel}: non-allowed import {name}")
        if isinstance(node, ast.Call):
            fn = node.func
            fname = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""
            if fname in FORBIDDEN_CALLS:
                problems.append(f"{rel}:{node.lineno}: forbidden call {fname}()")


def audit_main(problems: list[str]) -> None:
    tree = ast.parse((SRC / "main.py").read_text(encoding="utf-8"))
    bots = [n.name for n in tree.body if isinstance(n, ast.ClassDef)
            and any(getattr(b, "id", None) == "Bot" for b in n.bases)]
    if len(bots) != 1:
        problems.append(f"main.py must define exactly one Bot subclass, found {bots}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist" / "submission.zip"))
    ap.add_argument("--no-play", action="store_true")
    args = ap.parse_args()

    files = collect_files()
    problems: list[str] = []
    if not (SRC / "main.py").is_file():
        problems.append("main.py missing")
    total = sum(p.stat().st_size for p in files)
    if len(files) > MAX_FILES:
        problems.append(f"{len(files)} files > {MAX_FILES}")
    if total > MAX_BYTES:
        problems.append(f"{total} bytes > {MAX_BYTES}")
    for p in files:
        rel = p.relative_to(SRC).as_posix()
        if p.suffix == ".py":
            audit_source(p, rel, problems)
        else:
            problems.append(f"unexpected non-Python file {rel}")
    audit_main(problems)
    if problems:
        print("AUDIT FAILED:")
        for msg in problems:
            print("  -", msg)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, p.relative_to(SRC).as_posix())
    print(f"wrote {out}: {len(files)} files, {total / 1024:.1f} KiB unpacked")

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "main.py" in names, "main.py not at archive root"

    if args.no_play:
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(out) as zf:
            zf.extractall(tmp)
        macpoker = Path(sys.executable).with_name("macpoker.exe" if sys.platform == "win32" else "macpoker")
        cmds = [
            [str(macpoker), "play", "main.py", "house:call", "--deals", "100", "--subprocess"],
            [str(macpoker), "play", "main.py", "house:call", "house:checkfold", "house:random",
             "house:allin", "--deals", "100", "--subprocess", "--seed", "zip-audit"],
        ]
        for cmd in cmds:
            res = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)
            print(res.stdout.strip())
            if res.returncode != 0 or "main.py" not in res.stdout:
                print(res.stderr[-2000:])
                return 1
            line = next(l for l in res.stdout.splitlines() if l.startswith("main.py"))
            if not line.rstrip().endswith("OK"):
                print("main.py did not finish with an OK verdict")
                return 1
    print("ZIP OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
