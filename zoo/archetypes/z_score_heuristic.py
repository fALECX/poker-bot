"""A10 Scoring-function bot: fixed hand-score thresholds, limps, random 10% bluffs.

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {'limp_pct': 0.15, 'looseness': 1.2, 'bet_size': 0.5, 'value_t': 0.7, 'raise_t': 0.9, 'bluff_freq': 0.1, 'semibluff_freq': 0.3, 'big_bet_respect': 0.3}

bot = RuleBot(PARAMS, name="z_score_heuristic")
