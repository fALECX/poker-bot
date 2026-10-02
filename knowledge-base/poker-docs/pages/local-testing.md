# local-testing

Source: https://docs.poker.monashcoding.com/local-testing/

Testing locally | macpoker docs- - - - - Skip to content
The macpoker CLI plays full games on your machine using the same engine
the tournament runs, in the same duplicate format: one game per seat over
the same decks, every bot shifted one seat each game, and a fresh instance
of every bot for each game.
Play a game
Section titled “Play a game”
- Terminal windowmacpoker play main.py house:call house:random --deals 50
Every argument after play is one seat at the table. Pass 2 to 9 seats
in any mix of:
- a path to one of your bot files: main.py, v2.py, ../old/bot.py
- a built-in house bot, written with the house: prefix
House bot
Style
house:call
Calls everything, never raises. The validation opponent.
house:checkfold
Checks when free, folds to any bet.
house:allin
Shoves every chance it gets.
house:random
Mixes calls, folds and odd raises.
Options
Section titled “Options”
Flag
Default
Meaning
--deals N
50
Hands per game, each from a fresh deck.
--games N
one per seat
Games in the set. Fewer than one per seat leaves the cards unbalanced.
--seed S
local
Deck seed. Same seed, same cards.
--stack N
200
Starting stack each hand (blinds are 1 and 2).
--time-ms N
30000
Starting time bank per bot.
--increment-ms N
100
Clock increment per hand.
--subprocess
off
Run bots as separate processes over the real wire protocol.
--history FILE
off
Write the full hand history as JSON.
Comparing your own bots
Section titled “Comparing your own bots”
Any seat can be one of your files, and you can pass several at once:
Terminal windowmacpoker play v1.py v2.py aggressive.py house:call --deals 100 --seed fight
Because every bot plays every deck from every seat over the set, all of
your variants play the same cards from the same positions. The final chip
totals are a fair head-to-head comparison, not deck luck. Keep old versions
around (v1.py, v2.py, …) and A/B them: pin --seed while you iterate
so runs repeat exactly, then change the seed to confirm an improvement
holds up.
A bot can also play its own copy:
Terminal windowmacpoker play main.py main.py --deals 200
Each seat gets an independent instance, and self-play should net close to
zero. A large swing means your bot behaves inconsistently between
positions.
Reading the result
Section titled “Reading the result”
Output100 hands (2 games x 50 hands, same decks, seats shifted each game)
bot chips mbb/hand verdict
main.py +140 700.0 OK
house:call -140 -700.0 OK
Chips is the score. mbb/hand is milli-big-blinds per hand, a rate that is
comparable across game lengths. Chips and mbb/hand are totals over the
whole set. A verdict other than OK names the game it happened in and means
your bot stopped playing for the rest of that game: see
clocks and verdicts.
Debugging
Section titled “Debugging”
- print() from your bot goes to stderr and is shown after the game if it
had problems.
- --subprocess catches an entire class of bugs (protocol misuse, crashes on
startup, slow imports) exactly as the tournament would.
- --seed makes runs reproducible while you iterate.
