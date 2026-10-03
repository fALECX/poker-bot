"""A6 Loose-aggressive pressure bot: wide opens, 3bet bluffs, 100% c-bet, barrels, overbets.

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {'looseness': 1.6, 'open_size_bb': 3.0, 'threebet_pct': 0.08, 'threebet_bluff_freq': 0.2, 'cbet_freq': 1.0, 'barrel_freq': 0.5, 'overbet_freq': 0.25, 'bluff_freq': 0.15, 'value_t': 0.72, 'bluff_raise_freq': 0.08, 'call_margin': 0.0, 'semibluff_freq': 0.8}

bot = RuleBot(PARAMS, name="z_lag_pressure")
