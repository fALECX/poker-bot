"""Freeze the current bot under a unique package name for A/B testing (dev only).

    python tools/snapshot.py v1            -> snapshots/v1/main.py using package pokerbot_v1
    python tools/snapshot.py v0 --fallback-only

Unique package names keep several versions loadable in one interpreter
(in-process games share sys.modules).
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--fallback-only", action="store_true", help="disable the main strategy")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_]+", args.name):
        raise SystemExit("name must be alphanumeric/underscore")
    dest = ROOT / "snapshots" / args.name
    if dest.exists():
        if not args.force:
            raise SystemExit(f"{dest} exists (use --force)")
        shutil.rmtree(dest)
    pkg = f"pokerbot_{args.name}"
    shutil.copytree(ROOT / "scaffold" / "pokerbot", dest / pkg, ignore=shutil.ignore_patterns("__pycache__"))
    main_src = (ROOT / "scaffold" / "main.py").read_text(encoding="utf-8")
    main_src = main_src.replace("from pokerbot.", f"from {pkg}.").replace("import pokerbot", f"import {pkg}")
    if args.fallback_only:
        main_src = main_src.replace("Agent(strategy=decide)", "Agent()")
    (dest / "main.py").write_text(main_src, encoding="utf-8")
    print(f"snapshot written to {dest / 'main.py'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
