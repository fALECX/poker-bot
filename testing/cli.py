"""AI-friendly command line entry point for runs and comparisons."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bots import candidate
from .config import project_root
from .runner import run
from .scenarios import self_play, standard_table


def main() -> int:
    root = project_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bot", nargs="?", default=str(root / "scaffold" / "main.py"))
    parser.add_argument("--scenario", choices=("standard", "self-play"), default="standard")
    parser.add_argument("--seed", default="ai-baseline")
    parser.add_argument("--games", type=int, help="override games; standard defaults to 5")
    parser.add_argument("--fast", action="store_true", help="use in-process mode for iteration")
    parser.add_argument("--runs-root", type=Path, default=root / "runs")
    args = parser.parse_args()

    scenario = standard_table() if args.scenario == "standard" else self_play()
    result = run(
        candidate(Path(args.bot)),
        scenario,
        project_root=root,
        runs_root=args.runs_root.resolve(),
        seed=args.seed,
        games=args.games,
        subprocess_mode=not args.fast,
    )
    print(json.dumps({"run_id": result["run_id"], "directory": result["directory"]}, indent=2))
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
