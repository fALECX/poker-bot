"""Run repeatable bot simulations against the official macpoker runner.

The runner intentionally delegates game rules to macpoker.  This module only
orchestrates a large duplicate set and turns the official history into a
small machine-readable report.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


DEFAULT_REFERENCES = (
    "house:call",
    "house:checkfold",
    "house:random",
    "house:allin",
)


def _build_command(
    bot: str,
    references: tuple[str, ...],
    *,
    games: int,
    deals: int,
    seed: str,
    subprocess_mode: bool,
    history: Path,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "macpoker",
        "play",
        bot,
        *references,
        "--games",
        str(games),
        "--deals",
        str(deals),
        "--seed",
        seed,
        "--history",
        str(history),
    ]
    if subprocess_mode:
        command.append("--subprocess")
    return command


def _summarize(history: dict, bot_count: int) -> dict:
    config = history["config"]
    games = history["games"]
    chips = [0] * bot_count
    verdicts = [[] for _ in range(bot_count)]
    for game in games:
        result = game["result"]
        for index, value in enumerate(result["chips"]):
            chips[index] += value
        for index, verdict in enumerate(result["verdicts"]):
            if verdict != "OK":
                verdicts[index].append(verdict)

    hands = int(config["deals"]) * len(games)
    bb = int(config["bb"])
    return {
        "games": len(games),
        "deals_per_game": int(config["deals"]),
        "hands": hands,
        "chips": chips,
        "mbb_per_hand": [
            round(value / bb / max(hands, 1) * 1000, 2) for value in chips
        ],
        "verdicts": verdicts,
        "seed": config["seed"],
        "subprocess": bool(config["subprocess"]),
    }


def run_simulation(
    bot: str,
    references: tuple[str, ...] = DEFAULT_REFERENCES,
    *,
    games: int = 100,
    deals: int = 100,
    seed: str = "pokerbot-baseline",
    subprocess_mode: bool = True,
) -> dict:
    """Run a duplicate set and return its aggregate report.

    ``games`` defaults to 100 so every invocation is large enough to expose
    slow decisions, protocol bugs, and unstable strategy changes.
    """

    if not 2 <= len(references) + 1 <= 9:
        raise ValueError("macpoker supports between 2 and 9 total seats")
    if games < 1 or deals < 1:
        raise ValueError("games and deals must be positive")

    bot_path = Path(bot).resolve()
    project_root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="pokerbot-sim-") as temporary_directory:
        history = Path(temporary_directory) / "history.json"
        command = _build_command(
            str(bot_path),
            references,
            games=games,
            deals=deals,
            seed=seed,
            subprocess_mode=subprocess_mode,
            history=history,
        )
        completed = subprocess.run(
            command,
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "macpoker simulation failed:\n"
                f"{completed.stdout}\n{completed.stderr}".strip()
            )
        report = _summarize(json.loads(history.read_text(encoding="utf-8")), len(references) + 1)

    report["bots"] = [bot, *references]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "bot",
        nargs="?",
        default=str(Path(__file__).resolve().parents[1] / "scaffold" / "main.py"),
        help="path to the bot under test (default: scaffold/main.py)",
    )
    parser.add_argument("--games", type=int, default=100, help="duplicate games")
    parser.add_argument("--deals", type=int, default=100, help="hands per game")
    parser.add_argument("--seed", default="pokerbot-baseline")
    parser.add_argument(
        "--reference",
        action="append",
        dest="references",
        metavar="BOT",
        help="reference seat; repeat to override the default four house bots",
    )
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="disable subprocess mode (faster, but not production-parity)",
    )
    parser.add_argument("--report", type=Path, help="write the aggregate report as JSON")
    args = parser.parse_args()

    report = run_simulation(
        args.bot,
        tuple(args.references) if args.references else DEFAULT_REFERENCES,
        games=args.games,
        deals=args.deals,
        seed=args.seed,
        subprocess_mode=not args.in_process,
    )
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"{report['games']} games x {report['deals_per_game']} hands = {report['hands']} hands")
    print(f"{'bot':<30}{'chips':>10}{'mbb/hand':>12}  verdict")
    for bot, chips, mbb, verdicts in zip(
        report["bots"], report["chips"], report["mbb_per_hand"], report["verdicts"]
    ):
        verdict = ", ".join(verdicts) if verdicts else "OK"
        print(f"{bot:<30}{chips:>+10}{mbb:>12.2f}  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
