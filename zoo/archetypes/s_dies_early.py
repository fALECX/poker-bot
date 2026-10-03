"""Special: plays like A1, then crashes at hand 25 (engine check-folds it afterwards).

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {'die_at_hand': 25}

bot = RuleBot(PARAMS, name="s_dies_early")
