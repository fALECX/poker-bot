"""Validated run and scenario configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TableConfig:
    seats: int = 5
    deals: int = 100
    games: int = 5
    stack: int = 200
    sb: int = 1
    bb: int = 2
    time_ms: int = 30_000
    increment_ms: int = 100
    subprocess: bool = True

    def validate(self) -> None:
        if self.seats != 5:
            raise ValueError("the standard tournament table must have exactly 5 seats")
        if self.games != self.seats:
            raise ValueError("duplicate-deal tournament mode needs one game per seat")
        if self.deals != 100 or self.stack != 200 or (self.sb, self.bb) != (1, 2):
            raise ValueError("standard table must match the hackathon format")
        if self.time_ms <= 0 or self.increment_ms < 0:
            raise ValueError("clock values must be non-negative, with a positive bank")


@dataclass(frozen=True)
class Scenario:
    id: str
    description: str
    references: tuple[str, ...]
    table: TableConfig

    def validate(self) -> None:
        self.table.validate()
        if len(self.references) != self.table.seats - 1:
            raise ValueError("a five-seat scenario needs four reference bots")


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]
