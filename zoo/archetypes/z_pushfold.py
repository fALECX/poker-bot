"""A7 Push/fold bot: shoves the top ~20% preflop, re-shoves strong hands, jams any decent pair or draw.

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {'pushfold': True, 'shove_pct': 0.2, 'allin_assumed_top': 0.25, 'allin_margin': 0.0}

bot = RuleBot(PARAMS, name="z_pushfold")
