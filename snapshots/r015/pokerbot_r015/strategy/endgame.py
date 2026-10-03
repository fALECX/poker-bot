"""Risk attitude from the live standings (the game is scored by rank).

risk_lambda > 0 penalises outcome variance, < 0 rewards it. Mid-game we use
the base value. In the last hands, when the player above us is out of reach
but the one below is close, we protect our place; when the player above is
within reach and nobody below can catch us, we gamble for the extra place.
"""

from __future__ import annotations

import math

from ..params import P


def risk_lambda(agent, ctx) -> float:
    base = P["risk_lambda"]
    st = agent.standings
    hands_left = max(agent.num_hands - ctx.hand, 0)
    if hands_left > P["endgame_hands"]:
        return base
    gap_up, gap_down, _ = st.gaps()
    sigma = st.sigma_hand() * math.sqrt(max(hands_left, 1))
    reach_up = gap_up <= 1.0 * sigma
    safe_up = gap_up > 3.0 * sigma
    threat_down = gap_down <= 1.5 * sigma
    safe_down = gap_down > 3.0 * sigma
    if safe_up and threat_down:
        return P["endgame_protect_lambda"]
    if reach_up and safe_down:
        return P["endgame_gamble_lambda"]
    if safe_up and safe_down:
        return max(base, 0.2)  # place is settled either way: avoid needless swings
    return base
