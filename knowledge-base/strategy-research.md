# Poker-Bot Strategy Research

Arbeitsliste für recherchierte, modulare Strategien. Jede Idee soll später
isoliert getestet und mit anderen Modulen kombiniert werden können.

## Wettbewerbsregeln, die alle Varianten berücksichtigen müssen

- Gegner sind innerhalb eines Spiels über eine stabile Player-ID trackbar.
- Sitze wechseln; Statistiken dürfen daher nicht nach Sitznummer gespeichert
  werden.
- `on_action`, `on_street`, `on_hand_end` und `on_match_end` dürfen für
  begrenztes Bookkeeping verwendet werden.
- Zustand auf `self` bleibt innerhalb eines Spiels erhalten und wird zwischen
  Spielen zurückgesetzt.
- Gegner-Hole-Cards sind nur bei Showdowns sichtbar.
- Jede Hand startet mit 200 Chips; es gibt keine Eliminierung.
- Duplicate Deals reduzieren den Einfluss von Kartenluck.
- Zielgröße ist der kumulierte Chip-EV, der anschließend in Spiel- und
  Placement-Punkte umgewandelt wird.
- Rechenzeit, Speicher und Laufzeitabhängigkeiten sind begrenzt; jede Variante
  braucht einen sicheren Fallback bei niedrigem `clock_ms`.

Quellen:

- [Game format](https://docs.poker.monashcoding.com/game-format/)
- [Duplicate deals](https://docs.poker.monashcoding.com/game-format/duplicate-deals/)
- [Opponents and information](https://docs.poker.monashcoding.com/game-format/information/)
- [Clocks and verdicts](https://docs.poker.monashcoding.com/game-format/clocks/)
- [Writing a bot](https://docs.poker.monashcoding.com/writing-a-bot/)
- [Rules](https://docs.poker.monashcoding.com/rules/)

## Erlaubtes Gegner-Tracking

### Was wir speichern dürfen

- Öffentliche Aktionen jedes Gegners.
- Player-ID, aktuelle Position und Position relativ zum Button.
- Freiwilliges Einsteigen in den Pot.
- Raises, Calls, Folds und All-ins.
- Betgrößen relativ zu Pot und Stack.
- Aktionen pro Street.
- Showdown-Karten, wenn sie vom Engine-Event tatsächlich offengelegt werden.
- Ergebnisse und gewonnene/verlorene Pots.

### Was wir nicht voraussetzen dürfen

- Hole-Cards bei gefoldeten Händen.
- Zukünftige Karten oder Deck-Reihenfolge.
- Informationen aus anderen Bot-Prozessen oder anderen Spielen.
- Rechenarbeit außerhalb der erlaubten eigenen Hooks und `act()`.

### Minimaler Gegner-Datensatz

Pro Player-ID:

```text
hands_seen
vpip
pfr
raise_frequency_by_street
fold_to_raise
fold_to_cbet
showdown_count
showdown_hands
showdown_wins
average_bet_size_by_pot_fraction
aggression_by_street
```

Statistiken erst ab ausreichender Stichprobe stark gewichten. Für wenige
Beobachtungen zunächst mit neutralen Prior-Werten arbeiten.

## Bekannte externe Bots und Ansätze

### GTO3 / PokerHack

**Quelle:** [GTO3 auf Devpost](https://devpost.com/software/penelopethepokerbot)

**Macht:**

- GTO-inspirierte, balancierte Entscheidungen.
- Bewertung von Handstärke, Board-Textur, Gegneranzahl und Position.
- Probabilistische Preflop-Strategie.
- Bets mit mittelstarken Händen statt ausschließlich Premium-Hände.
- Entwicklung und Tests mit `pypokerengine`.

**Warum das plausibel funktioniert:**

- Eine Strategie, die nur auf sehr starke Hände wartet, gibt zu viele Pots auf.
- Mittelstarke Hände können durch Fold Equity profitabel werden.
- Position und Board-Textur verändern die tatsächliche Equity deutlich.

**Mögliche Schwächen:**

- Die Devpost-Beschreibung ist high-level; vollständiger Siegercode und
  detaillierte Resultate sind nicht eindeutig öffentlich belegt.
- Der PokerHack-Scoring- und Engine-Kontext kann von MAC abweichen.
- GTO-inspiriert bedeutet nicht, dass tatsächlich ein vollständiger GTO-Solver
  verwendet wurde.
- Gegen stark exploitative Gegner kann eine rein balancierte Strategie zu
  wenig ausnutzen.

**Für uns testen:**

- Preflop-Range mit kontrollierter Randomisierung.
- Position-aware Open-Raises.
- Board-aware Postflop-Bets.
- Vergleich gegen `house:call`, `house:checkfold`, `house:allin` und
  `house:random`.

### PokerBattle.ai LLM-Bots

**Quellen:**

- [PokerNews Ergebnisbericht](https://www.pokernews.com/news/2025/11/poker-bot-battle-results-49971.htm)
- [PokerNews Hintergrundbericht](https://www.pokernews.com/news/2025/10/poker-bot-battle-49955.htm)
- [PokerBattle.ai Hand Histories](https://pokerbattle.ai/hand-history)

**Macht:**

- Bots durften Notizen über Gegner führen.
- Bots konnten ihre Einschätzung im Verlauf anpassen.
- Es wurden beobachtete Spielstile wie loose, passive oder aggressive
  Gegner beschrieben.

**Warum das plausibel funktioniert:**

- Wiederkehrende Gegner erzeugen verwertbare Muster.
- Gegen einen Spieler mit zu hoher Fold-Rate sind Bluffs profitabler.
- Gegen einen Spieler mit zu hoher Call-Rate sind Value-Bets profitabler.

**Mögliche Schwächen:**

- PokerBattle.ai war ein anderes Format und kein Beweis für MAC-Performance.
- Kleine Samples können VPIP- und Aggressionswerte verzerren.
- Ergebnisranglisten einzelner Matches beweisen keine dauerhafte Stärke.
- Sprachmodell-Notizen sind nicht mit einem strikt begrenzten lokalen Bot
  gleichzusetzen.

**Für uns testen:**

- Gegnerprofile nach Player-ID.
- Bayesian Shrinkage oder Mindestanzahl von Beobachtungen.
- Unterschiedliche Exploit-Stärken für 0, 10, 30 und 60 Beobachtungen.
- Profilbasierte Anpassung nur als Overlay auf eine robuste Basisstrategie.

### Libratus

**Quelle:** [Noam Brown – research overview](https://noambrown.com/)

**Macht:**

- Spieltheoretische Abstraktion.
- Strategische Randomisierung.
- Lösung schwieriger Spielsituationen.
- Schutz vor systematischer Ausnutzung.

**Für uns nützlich:**

- Nicht jede Situation deterministisch gleich spielen.
- Ranges statt einzelner vermuteter Hände verwenden.
- Gegen starke Gegner nicht immer dieselbe Betgröße und Linie wählen.

**Für uns wahrscheinlich zu schwer:**

- Vollständige CFR- oder Subgame-Solver-Architektur.
- Rechenbudget und Trainingsumfang der Originalsysteme.

### Pluribus

**Quelle:** [Science paper: Superhuman AI for multiplayer poker](https://www.science.org/doi/10.1126/science.aay2400)

**Macht:**

- Self-play.
- Mehrspielerstrategie für 6-max.
- Depth-limited Search.
- Echtzeit-Subgame-Solving.
- Randomisierte Entscheidungen.

**Für uns nützlich:**

- Multiway-Pots nicht wie Heads-up-Situationen behandeln.
- Anzahl aktiver Gegner in Equity und Bluff-Frequenz einbeziehen.
- Kleine begrenzte Suche nur in kritischen Entscheidungen erwägen.

**Für uns wahrscheinlich zu schwer:**

- Vollständige Echtzeit-Suche in jeder Entscheidung.
- Training eines vergleichbaren Self-play-Systems innerhalb des Wettbewerbs.

## Modulare Bot-Varianten zum Testen

Jede Variante sollte dieselbe Engine-Schnittstelle und denselben Test-Seed
verwenden.

### Variante A: Robuste Baseline

- Pot Odds.
- Einfache Hand- und Boardbewertung.
- Position.
- Anzahl aktiver Gegner.
- Keine Gegnerhistorie.

**Hypothese:** Stabiler Referenzpunkt; jede Erweiterung muss diese Variante
über reproduzierbare Seeds schlagen.

### Variante B: Tight Value

- Wenige Preflop-Hände.
- Starke Value-Bets.
- Sehr wenige Bluffs.

**Gut gegen:** Calling Stations und `house:call`.

**Risiko:** Zu viele kleine profitable Pots werden aufgegeben.

### Variante C: Loose Pressure

- Breitere Opens in später Position.
- Kleine bis mittlere Bets mit Fold Equity.
- Mehr Druck gegen passive Gegner.

**Gut gegen:** `house:checkfold` und Spieler mit hoher Fold-Rate.

**Risiko:** Zu viele marginale Multiway-Spots.

### Variante D: Anti-All-in

- Breitere Calling-Range gegen unselektierte Shoves.
- Keine automatische Panik gegen hohe Varianz.
- Hand-Equity und Pot Odds statt Betgröße allein.

**Gut gegen:** `house:allin` und hyperaggressive Gegner.

**Risiko:** Große Calls mit zu wenig tatsächlicher Equity.

### Variante E: Opponent-Modeling

- Statistiken nach Player-ID.
- Shrinkage zu neutralen Prior-Werten.
- Exploit-Overlay auf die Baseline.

**Gut gegen:** Wiederkehrende, erkennbare Gegner innerhalb eines Spiels.

**Risiko:** Overfitting auf wenige Hände oder falsche Showdown-Schlüsse.

### Variante F: Board- und Street-Aware

- Flush-/Straight-Draws.
- Paired Boards.
- Coordinated Boards.
- Anzahl möglicher gegnerischer Kombinationen.
- Unterschiedliche Turn-/River-Aggression.

**Hypothese:** Verbesserte Postflop-Entscheidungen gegenüber reiner
Preflop-/Pot-Odds-Logik.

### Variante G: Randomisierte Balanced Strategy

- Mehrere annähernd gleichwertige Aktionen.
- Zufällige Auswahl innerhalb einer gewichteten Range.
- Keine zufälligen Aktionen ohne Equity- oder Fold-Equity-Grundlage.

**Hypothese:** Weniger exploitable als eine vollständig deterministische Linie.

**Risiko:** Zufall verschlechtert EV, wenn die Gewichte nicht kalibriert sind.

### Variante H: Bounded Monte Carlo

- Equity-Simulation nur in nichttrivialen Spots.
- Samples abhängig von `clock_ms`.
- Sofortiger Fallback auf Baseline bei niedrigem Budget.

**Hypothese:** Nützlich auf Turn/River und in Multiway-Pots.

**Risiko:** Timeout, schlechte Varianz oder fehlerhafte Equity-Berechnung.

### Variante I: Begrenzte Lookahead-Suche

- Nur wenige plausible gegnerische Aktionen simulieren.
- Nur in großen Pots oder All-in-Nähe.
- Harte Zeit- und Knotengrenze.

**Hypothese:** Kann kritische Entscheidungen verbessern.

**Risiko:** Hohe Komplexität; muss klar gegen Monte Carlo und Baseline
  gewinnen, bevor sie behalten wird.

## Testmatrix

| Achse | Varianten |
|---|---|
| Basis | A gegen jede Erweiterung |
| Gegner | call, checkfold, allin, random, tight-aggressive, loose-passive |
| Tischgröße | 4, 5 und 6 Bots |
| Position | jede Position über Duplicate Deals |
| Spiel | mindestens 100 Hände, identischer Seed im A/B-Test |
| Laufzeit | normaler Clock und künstlich niedriger `clock_ms` |
| Robustheit | In-Process und `--subprocess` |
| Metriken | Chips, mbb/Hand, Platzierung, Varianz, TLE/RTE/PV |

## Offene Forschungsfragen

- Wie viele Beobachtungen braucht ein Gegnerprofil, bevor ein Exploit aktiviert
  werden sollte?
- Ist ein Gegnerprofil über das ganze Spiel besser als street-spezifische
  Profile?
- Wie stark sollte Position die Range im Vergleich zur Gegnerhistorie verändern?
- Wie viel Randomisierung verbessert Robustheit, ohne EV zu verschenken?
- Sind kleine Bets gegen `house:checkfold` besser als größere Bets?
- Wie häufig overfolden Bots nach einem Raise?
- Wie viel Multiway-Discount braucht unsere Equity-Schätzung?
- Ist Monte Carlo den Zeitverbrauch gegenüber einer Lookup-/Heuristikstrategie
  wert?
- Welche Gegnerprofile bleiben über die 100 Hände stabil genug, um exploitet zu
  werden?

## Quellenstatus

### Verifiziert

- MAC erlaubt öffentliches Gegner-Tracking über Observer-Hooks.
- Player-IDs bleiben innerhalb eines Spiels stabil.
- Zustand auf `self` bleibt innerhalb eines Spiels erhalten.
- Gegnerkarten werden nur bei erlaubtem Showdown bekannt.
- Duplicate Deals und Stack-Reset sind Bestandteil des MAC-Formats.
- PokerBattle.ai dokumentierte Gegnernotizen und Anpassungen.
- GTO3 dokumentierte Handstärke, Board-Textur, Position und probabilistische
  Preflop-Entscheidungen.

### Noch nicht verifiziert

- Ob GTO3 tatsächlich der Gesamtsieger von PokerHack war.
- Vollständiger Quellcode oder exakte Parameter von GTO3.
- Exakte interne Implementierungen der PokerBattle.ai-Bots.
- Ob ein bestimmter komplexer Algorithmus in diesen Hackathons tatsächlich
  besser war als eine gut kalibrierte Heuristik.

## Short English Evaluation of Bot Ideas

These are the same ideas in a short format for team discussion. Each module
should first be tested independently against the baseline using identical
seeds.

### Robust Baseline

- **Does:** Uses pot odds, basic hand strength, board texture, position, and
  active-player count without opponent history.
- **Why it could work:** Stable, cheap, easy to debug, and a reliable benchmark.
- **Why it might not:** It cannot exploit predictable opponents and may be too
  generic or conservative.

### Tight Value

- **Does:** Plays fewer starting hands and emphasizes strong value bets.
- **Why it could work:** Punishes calling stations and avoids many marginal
  spots.
- **Why it might not:** It gives up small profitable pots, becomes predictable,
  and lets passive opponents realize equity cheaply.

### Loose Pressure

- **Does:** Opens more hands, especially in late position, and uses bets to
  create fold equity.
- **Why it could work:** Strong against opponents who fold too often and can
  accumulate many small pots.
- **Why it might not:** It enters too many marginal or multiway pots and can
  lose heavily against callers.

### Anti-All-in

- **Does:** Responds to shoves using equity and pot odds rather than treating
  every all-in as automatically strong.
- **Why it could work:** It directly targets `house:allin` and hyperaggressive
  opponents.
- **Why it might not:** Calling too widely creates large losses if the
  opponent's shove range is actually strong.

### Opponent Modeling

- **Does:** Tracks VPIP, raises, folds, aggression, bet sizing, and showdowns
  per Player-ID.
- **Why it could work:** It uses information explicitly exposed by the format
  and allows targeted adjustments against recurring opponents.
- **Why it might not:** Early samples are noisy, opponents may change style,
  and overfitting can be worse than a neutral strategy.
- **Safe version:** Use confidence thresholds or Bayesian shrinkage and apply
  the profile only as an overlay on the baseline.

### Board- and Street-Aware Play

- **Does:** Adjusts decisions for draws, paired boards, coordinated boards,
  and flop/turn/river context.
- **Why it could work:** Board texture changes equity and bluff success
  substantially.
- **Why it might not:** Simple board heuristics can be wrong and increase
  implementation complexity.

### Randomized Balanced Strategy

- **Does:** Mixes actions with calibrated probabilities instead of always
  taking the same action in the same situation.
- **Why it could work:** Makes the bot less predictable and supports balanced
  ranges.
- **Why it might not:** Randomness does not create EV by itself; bad weights
  simply lose chips and make debugging harder.
- **Safe version:** Randomize only between actions that are already
  individually reasonable.

### Bounded Monte Carlo Equity

- **Does:** Simulates future cards and plausible opponent holdings with a
  sample count limited by the remaining clock.
- **Why it could work:** Gives better estimates in unusual, turn/river, and
  multiway situations than fixed hand categories.
- **Why it might not:** It costs CPU time, has simulation variance, and is only
  as good as its assumed opponent ranges.
- **Safe version:** Use it only for difficult decisions and fall back to
  deterministic heuristics when the clock is low.

### Bounded Lookahead Search

- **Does:** Simulates a small set of likely future actions and responses.
- **Why it could work:** It considers future consequences in large pots and
  near all-in decisions.
- **Why it might not:** Incorrect response models create false precision, and
  search can be expensive or time out.
- **Recommendation:** Test only after equity and baseline logic are strong.

### GTO-Inspired Preflop Ranges

- **Does:** Uses position-dependent opening, calling, and raising ranges.
- **Why it could work:** Preflop happens frequently, position matters, and
  ranges are harder to exploit than isolated hand rules.
- **Why it might not:** Static or heads-up-derived ranges may not fit a
  five-player duplicate-deal format or weak opponents.

### Adaptive Preflop Ranges

- **Does:** Widens or tightens the starting range based on position and
  opponent tendencies.
- **Why it could work:** Combines robust defaults with targeted exploitation.
- **Why it might not:** Sparse statistics can cause large systematic leaks.
  Adaptation should be gradual rather than binary.

### Position-Aware Strategy

- **Does:** Plays more hands and applies more pressure late, while tightening
  early and from the blinds.
- **Why it could work:** Position is a reliable source of information and EV,
  and duplicate deals make its effect measurable.
- **Why it might not:** Position alone does not account for multiway pots or
  opponent-specific behavior.

### Multiway-Pot Strategy

- **Does:** Adjusts equity thresholds, bluff frequency, and value-bet sizing
  according to the number of opponents still in the hand.
- **Why it could work:** Equity and fold probability usually fall as more
  players continue.
- **Why it might not:** Simple multiway discounts may be too conservative
  against opponents with unusually weak ranges.

### Showdown-Based Range Updating

- **Does:** Uses legitimately revealed showdown cards to update opponent
  ranges and tendencies.
- **Why it could work:** Showdowns provide stronger evidence than actions alone.
- **Why it might not:** Showdowns are sparse and biased toward hands that were
  not folded; one hand must not dominate the profile.

### Exploitative Strategy

- **Does:** Explicitly targets weaknesses, such as bluffing more against
  frequent folders or value-betting more against frequent callers.
- **Why it could work:** Beginner and heuristic bots are often predictable,
  and opponents repeat within a game.
- **Why it might not:** It fails against adaptive or unknown opponents and can
  overreact to early noise.
- **Safe version:** Start with weak adjustments and increase exploit strength
  only as confidence grows.

### Self-Play Testing

- **Does:** Runs multiple bot versions against one another with identical
  seeds.
- **Why it could work:** Gives clean A/B comparisons and catches regressions
  or position-dependent inconsistencies.
- **Why it might not:** A bot can overfit to its own style; self-play cannot
  replace testing against diverse opponents.

### Strategy Ensemble

- **Does:** Combines baseline, position, board, equity, opponent, and
  randomization modules.
- **Why it could work:** A safe baseline can handle normal cases while
  specialized modules handle high-value situations.
- **Why it might not:** Conflicting modules make behavior unstable and harder
  to debug.
- **Suggested priority:** Legal-action safety, low-clock fallback, baseline,
  board/equity adjustment, opponent adjustment, then controlled randomization.

### Full CFR or Solver-Based Strategy

- **Does:** Attempts to approximate game-theoretic strategies using CFR or
  related solving methods.
- **Why it could work:** It has a strong theoretical foundation and can produce
  less exploitable play.
- **Why it might not:** The state space, runtime, validation burden, and
  sandbox limits make a full solver risky; practical heuristics may achieve
  higher EV against the actual field.
- **Recommendation:** Borrow the concepts—ranges, randomization, and balance—
  without making a full solver the core bot.
