# Bot-Simulation-Suite

Die Suite verwendet den offiziellen `macpoker`-Runner als Spiel-Engine. Dadurch
werden Regeln, Pot-Aufteilung, Duplicate Deals und Clock/Verdicts nicht
nachgebaut oder versehentlich anders implementiert.

## Schnelltest

Aus dem Projektroot:

```powershell
.\.venv\Scripts\python.exe testing\simulate.py --games 100 --deals 100 --report out\baseline.json
```

Der Default testet `scaffold\main.py` gegen:

- `house:call` – callt jede Hand
- `house:checkfold` – checkt kostenlos, foldet sonst
- `house:random` – zufällige Calls/Folds/Raises
- `house:allin` – geht bei jeder Gelegenheit all-in

Das sind Referenz-Baselines, keine perfekten Poker-Bots. Ein „perfekter“ Bot ist
für diese variable Multiway-Situation nicht verfügbar; entscheidend ist daher
ein reproduzierbarer Vergleich gegen dieselben Gegner und Seeds.

## Eigene Bots vergleichen

```powershell
.\.venv\Scripts\python.exe testing\simulate.py bots\v2.py --seed v2-a
.\.venv\Scripts\python.exe testing\simulate.py bots\v2.py --in-process --games 20 --deals 100
.\.venv\Scripts\python.exe testing\simulate.py bots\v2.py `
  --reference bots\v1.py --reference house:random --games 100
```

`--subprocess` ist der Default und testet den echten Wire-Protocol-Pfad.
`--in-process` ist nur für schnelle Strategie-Iterationen gedacht. Mit
demselben `--seed` sind Läufe reproduzierbar; ein neuer Seed prüft, ob ein
Ergebnis nicht nur ein Deck-Artefakt ist.

Der JSON-Report enthält Spiele, Hände, Chip-Summe, `mbb_per_hand` und alle
Nicht-OK-Verdicts (`TLE`, `RTE`, `PV`).
