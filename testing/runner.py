"""Run the official macpoker engine and persist complete run artifacts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .analysis import summarize
from .bots import BotSpec, file_fingerprint
from .config import Scenario
from .storage import create_run_dir, persist_history, write_json


def run(
    bot: BotSpec,
    scenario: Scenario,
    *,
    project_root: Path,
    runs_root: Path,
    seed: str,
    games: int | None = None,
    subprocess_mode: bool | None = None,
) -> dict:
    scenario.validate()
    table = scenario.table
    actual_games = games if games is not None else table.games
    if actual_games < 1:
        raise ValueError("games must be positive")
    use_subprocess = table.subprocess if subprocess_mode is None else subprocess_mode

    specs = [bot]
    for reference in scenario.references:
        specs.append(bot if reference == "__candidate__" else BotSpec(reference, reference, reference, "reference"))
    bot_names = [spec.id for spec in specs]
    run_id, run_dir = create_run_dir(runs_root, scenario.id, seed)
    history_path = run_dir / "runner-history.json"
    command = [
        sys.executable,
        "-m",
        "macpoker",
        "play",
        *[spec.runner_spec for spec in specs],
        "--games",
        str(actual_games),
        "--deals",
        str(table.deals),
        "--stack",
        str(table.stack),
        "--sb",
        str(table.sb),
        "--bb",
        str(table.bb),
        "--seed",
        seed,
        "--time-ms",
        str(table.time_ms),
        "--increment-ms",
        str(table.increment_ms),
        "--history",
        str(history_path),
    ]
    if use_subprocess:
        command.append("--subprocess")
    completed = subprocess.run(command, cwd=project_root, capture_output=True, text=True, check=False)
    (run_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
    (run_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        write_json(run_dir / "run.json", {"run_id": run_id, "status": "failed", "command": command})
        raise RuntimeError(f"macpoker failed with exit code {completed.returncode}; see {run_dir}")

    history = json.loads(history_path.read_text(encoding="utf-8"))
    summary = summarize(history, bot_names)
    metadata = {
        "run_id": run_id,
        "status": "completed",
        "scenario_id": scenario.id,
        "seed": seed,
        "mode": "subprocess" if use_subprocess else "in-process",
        "candidate": {
            "id": bot.id,
            "path": bot.runner_spec,
            "sha256": file_fingerprint(Path(bot.runner_spec)) if Path(bot.runner_spec).is_file() else None,
        },
        "engine": "macpoker",
        "command": command,
    }
    write_json(run_dir / "run.json", metadata)
    write_json(run_dir / "config.json", {"scenario": scenario.id, "table": table.__dict__, "bots": bot_names})
    write_json(run_dir / "summary.json", summary)
    history_path.unlink()
    persist_history(history, run_dir)
    return {"run_id": run_id, "directory": str(run_dir), "summary": summary}
