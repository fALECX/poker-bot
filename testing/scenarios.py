"""Built-in tournament scenarios."""

from .config import Scenario, TableConfig


def standard_table() -> Scenario:
    return Scenario(
        id="standard-5-seat",
        description="Hackathon-parity five-seat duplicate-deal table.",
        references=("house:call", "house:checkfold", "house:random", "house:allin"),
        table=TableConfig(),
    )


def self_play() -> Scenario:
    return Scenario(
        id="self-play-5-seat",
        description="Five independent copies of the candidate for stability checks.",
        references=("__candidate__", "__candidate__", "__candidate__", "__candidate__"),
        table=TableConfig(),
    )
