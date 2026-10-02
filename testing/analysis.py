"""Deterministic aggregate metrics for dashboards and bot comparisons."""

from __future__ import annotations

from statistics import mean, pstdev
from typing import Any


def summarize(history: dict, bot_names: list[str]) -> dict[str, Any]:
    config = history["config"]
    games = history["games"]
    bot_count = len(bot_names)
    chips_by_bot = [[] for _ in range(bot_count)]
    verdicts = [[] for _ in range(bot_count)]
    for game in games:
        result = game["result"]
        for index, chips in enumerate(result["chips"]):
            chips_by_bot[index].append(chips)
        for index, verdict in enumerate(result["verdicts"]):
            verdicts[index].append(verdict)

    hands = int(config["deals"]) * len(games)
    bb = int(config["bb"])
    totals = [sum(values) for values in chips_by_bot]
    bot_metrics = []
    for index, name in enumerate(bot_names):
        values = chips_by_bot[index]
        bot_metrics.append(
            {
                "id": name,
                "chips": sum(values),
                "mbb_per_hand": round(sum(values) / bb / max(hands, 1) * 1000, 2),
                "positive_games": sum(value > 0 for value in values),
                "mean_game_chips": round(mean(values), 2) if values else 0,
                "stddev_game_chips": round(pstdev(values), 2) if len(values) > 1 else 0,
                "verdicts": verdicts[index],
                "failed_games": sum(value != "OK" for value in verdicts[index]),
            }
        )
    return {
        "games": len(games),
        "hands": hands,
        "deals_per_game": int(config["deals"]),
        "bots": bot_metrics,
    }
