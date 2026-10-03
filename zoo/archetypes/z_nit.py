"""A9 Nit: plays ~8% of hands, bets big with strong hands, folds to pressure.

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {'looseness': 0.5, 'value_t': 0.85, 'bet_size': 0.9, 'cbet_freq': 0.3, 'call_margin': 0.1, 'allin_assumed_top': 0.05, 'big_bet_respect': 1.2, 'semibluff_freq': 0.1}

bot = RuleBot(PARAMS, name="z_nit")
