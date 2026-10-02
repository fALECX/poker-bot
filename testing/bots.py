"""Bot catalog and stable identifiers for scenario configuration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BotSpec:
    id: str
    display_name: str
    runner_spec: str
    kind: str
    tags: tuple[str, ...] = ()


HOUSE_BOTS = {
    "house.call": BotSpec("house.call", "House Call", "house:call", "reference", ("passive",)),
    "house.checkfold": BotSpec(
        "house.checkfold", "House Check/Fold", "house:checkfold", "reference", ("tight",)
    ),
    "house.random": BotSpec(
        "house.random", "House Random", "house:random", "reference", ("stochastic",)
    ),
    "house.allin": BotSpec("house.allin", "House All-In", "house:allin", "reference", ("aggressive",)),
}


def candidate(path: Path, bot_id: str = "candidate.current") -> BotSpec:
    return BotSpec(bot_id, path.stem, str(path.resolve()), "candidate", ("under-test",))


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def resolve_reference(value: str) -> BotSpec:
    if value in HOUSE_BOTS:
        return HOUSE_BOTS[value]
    if value.startswith("house:"):
        key = f"house.{value.split(':', 1)[1]}"
        if key in HOUSE_BOTS:
            return HOUSE_BOTS[key]
    return BotSpec(value, value, value, "reference", ())
