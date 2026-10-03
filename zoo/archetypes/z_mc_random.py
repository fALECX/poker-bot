"""A2 Canonical LLM Monte Carlo bot: equity vs random hands, call when equity > pot odds, size proportional to equity, calls shoves by equity vs random.

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {'strength': 'mc_random', 'allin_mode': 'eq_random', 'allin_margin': 0.02, 'value_t': 0.62, 'raise_t': 0.85, 'size_mode': 'proportional', 'size_min': 0.5, 'size_max': 1.0, 'call_margin': 0.0, 'cbet_freq': 0.3, 'looseness': 1.3, 'limp_pct': 0.1, 'bluff_freq': 0.05, 'big_bet_respect': 0.0}

bot = RuleBot(PARAMS, name="z_mc_random")
