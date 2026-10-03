"""Top-level strategy: picks the time budget and dispatches by street."""

from __future__ import annotations

from ..core.clock import Deadline, budget_ms
from . import endgame, exploits, fallback, postflop


def decide(agent, ctx, rng, clock_ms):
    big = ctx.pot >= 40 * ctx.bb or ctx.to_call >= 0.3 * max(ctx.stack, 1)
    importance = 2.5 if big else 1.0
    deadline = Deadline(budget_ms(clock_ms, ctx.hand, agent.num_hands, importance))

    ctx.risk_lambda = endgame.risk_lambda(agent, ctx)
    override = exploits.override(agent, ctx, rng)
    if override is not None:
        return override
    if ctx.street == "preflop":
        return fallback.preflop(ctx, agent.tracker, rng)
    return postflop.decide(agent, ctx, rng, deadline)
