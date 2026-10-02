"""Durable, frontend-friendly run storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def create_run_dir(root: Path, scenario_id: str, seed: str) -> tuple[str, Path]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}_{scenario_id}_{seed}".replace(" ", "_")
    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=False)
    return run_id, directory


def persist_history(history: dict, directory: Path) -> None:
    write_json(directory / "raw-history.json", history)
    games = []
    hands = []
    for game_index, game in enumerate(history["games"]):
        result = game["result"]
        games.append(
            {
                "game_index": game_index,
                "offset": game["result"].get("offset"),
                "chips": result["chips"],
                "verdicts": result["verdicts"],
                "mbb_per_hand": result["mbb_per_hand"],
                "num_hands": result["num_hands"],
            }
        )
        for hand in game["hands"]:
            hands.append({"game_index": game_index, **hand})
    (directory / "games.jsonl").write_text(
        "".join(json.dumps(game) + "\n" for game in games), encoding="utf-8"
    )
    (directory / "hands.jsonl").write_text(
        "".join(json.dumps(hand) + "\n" for hand in hands), encoding="utf-8"
    )
