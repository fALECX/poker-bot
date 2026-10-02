# quickstart

Source: https://docs.poker.monashcoding.com/quickstart/

Quickstart | macpoker docs- - - - - Skip to content
-
Install the SDK
- Terminal windowpip install https://poker.monashcoding.com/dl/macpoker-0.1.0-py3-none-any.whl
Or start from the scaffold, which contains a
ready-to-run main.py.
-
Write a bot
main.pyfrom macpoker import Bot
class MyBot(Bot):
def act(self, state):
if state.to_call == 0:
return state.check()
pot_odds = state.to_call / (state.pot + state.to_call)
if pot_odds < 0.3:
return state.call()
return state.fold()
One main.py, one Bot subclass, one decision method. Everything your bot can see and do is on
state.
-
Test it
Terminal windowmacpoker play main.py house:call house:random --deals 50
Your bot plays three games of 50 hands against two house bots, once from each seat, and you get a chip count. See
testing locally.
-
Submit it
Zip your folder with main.py at the root and upload it from the
app. Each upload plays a validation game against the house; pick a
passing upload as your main before the deadline. That is your tournament entry.
Iterate with a fixed seed
Add --seed anything while you tweak your bot. Same seed, same cards, so a change in chips is a change in
your decisions.
