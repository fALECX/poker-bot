"""A5 Opponent-modelling TAG: tracks fold/aggression per player id and adapts bluff and call thresholds.

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {'adaptive': True, 'bluff_freq': 0.1, 'barrel_freq': 0.2, 'semibluff_freq': 0.5}

bot = RuleBot(PARAMS, name="z_model_adaptive")
