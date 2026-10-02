# game-format-duplicate-deals

Source: https://docs.poker.monashcoding.com/game-format/duplicate-deals/

Duplicate deals | macpoker docs- - - - - Skip to content
Card luck is engineered out across each round. Every table plays one game
per seat, and all of a table’s games deal the same 100 hands. Each game
shifts every bot one seat along, so by the end of the round every bot has
played every hand from every seat, exactly as its opponents did. What
separates scores is decisions, not the deck.
One table, one round
Pick a game, then step through its hands.
‹›
Hand · fresh deck
Who held what in hand , game by game
Every row ends up holding all five sets of cards from all five positions, once each. Within a game every hand is a new deck, so no bot ever sees the same cards twice.
How a round is dealt
Section titled “How a round is dealt”
- A table of 5 plays 5 games, a table of 4 plays 4, and a table of 6
plays 6.
- Within a game, every hand is dealt from a new deck and the button moves
one seat each hand.
- Hand 1 of every game at the table uses the same deck, as does hand 2,
and so on. Game 2 starts every bot one seat further round than game 1.
- Each game runs your bot as a new process, so it starts every game
knowing nothing about the others.
Running macpoker play locally deals the same way, so two versions of
your bot get a fair comparison on your machine too. See
testing locally.
