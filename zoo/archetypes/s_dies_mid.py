"""Special: plays like A2, then crashes at hand 55.

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {'die_at_hand': 55, 'strength': 'mc_random', 'allin_mode': 'eq_random', 'value_t': 0.62, 'looseness': 1.3}

bot = RuleBot(PARAMS, name="s_dies_mid")
