"""A11 Trapper: slowplays monsters, check-raises, calls down light to induce.

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {'slowplay_freq': 0.6, 'raise_t': 0.9, 'value_t': 0.85, 'call_margin': 0.0, 'big_bet_respect': 0.4}

bot = RuleBot(PARAMS, name="z_trapper")
