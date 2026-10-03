"""A1 Tight-aggressive chart bot: positional opens, value bets two-pair+, c-bets half pot.

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {}

bot = RuleBot(PARAMS, name="z_tag_chart")
