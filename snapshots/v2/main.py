"""MAC poker tournament entry point.

The decision logic lives in the `pokerbot` package next to this file. This
module only defines the single Bot subclass the engine loads and forwards
every engine message to the agent, which never raises.
"""

from macpoker import Bot

from pokerbot_v2.agent import Agent
from pokerbot_v2.strategy.main_strategy import decide


class PokerBot(Bot):
    def __init__(self):
        self.agent = Agent(strategy=decide)

    def act(self, state):
        return self.agent.act(state)

    def on_match_start(self, info):
        self.agent.on_match_start(info)

    def on_hand_start(self, info):
        self.agent.on_hand_start(info)

    def on_action(self, event):
        self.agent.on_action(event)

    def on_street(self, event):
        self.agent.on_street(event)

    def on_hand_end(self, info):
        self.agent.on_hand_end(info)
