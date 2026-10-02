# Modular Bot Testing Suite

Diese Suite ist **ausschließlich für AI-gestützte Entwicklung** gedacht. Menschen
sollen keine Run-Dateien oder Auswertungsdaten manuell pflegen. Eine AI soll
neue Bot-Versionen, Szenarien und Seeds über die CLI erzeugen und danach die
persistierten Artefakte auswerten. Der Code ist deshalb in kleine, eindeutige
Module geteilt und speichert alle entscheidenden Eingaben und Ergebnisse.

## Abgrenzung

- [`scaffold/`](../scaffold/) bleibt der submission-nahe Bot-Code.
- [`testing/`](.) enthält nur Runner, Konfiguration, Speicherung und Analyse.
- [`runs/`](../runs/) enthält generierte Ergebnisse und ist nicht für Git gedacht.
- Die Spielregeln werden **nicht** nachgebaut: `macpoker` bleibt die einzige
  Spiel-Engine.

## Struktur

```text
testing/
├── cli.py        # AI-Einstiegspunkt
├── config.py     # validierte Hackathon-Tischkonfiguration
├── scenarios.py  # standard-5-seat und self-play
├── bots.py       # stabile Bot-IDs und Referenzkatalog
├── runner.py     # offizieller macpoker-Aufruf
├── storage.py    # Run-Verzeichnisse, JSON und JSONL
└── analysis.py   # deterministische Kennzahlen
runs/
└── <run-id>/
    ├── run.json
    ├── config.json
    ├── summary.json
    ├── games.jsonl
    ├── hands.jsonl
    ├── raw-history.json
    ├── stdout.log
    └── stderr.log
```

## Hackathon-Standardtisch

Das Szenario `standard-5-seat` erzwingt:

- 5 Bots am Tisch
- 5 Duplicate-Deal-Games
- 100 Hände pro Game
- 200 Chips Stack
- Blinds 1/2
- 30.000 ms Startzeit plus 100 ms pro Hand
- Subprocess-Modus als Standard

Die fünf Sitze bestehen aus dem Kandidaten und vier offiziellen House-Bots.
Die fünf Games sind der korrekte Duplicate-Deal-Round-Modus. Für Lasttests
kann `--games 100` gesetzt werden; dieser Modus ist dann bewusst ein Stresslauf
und nicht mehr die normale Turnier-Runde.

## AI-Workflow

```powershell
# Hackathon-paritätsnaher Run: 5 Bots, 5 Games, 500 Hände
.\.venv\Scripts\python.exe -m testing scaffold\main.py --seed baseline-a

# Schnelle Iteration ohne Prozess-Overhead
.\.venv\Scripts\python.exe -m testing scaffold\main.py --fast --games 1

# Stresslauf mit 10.000 Händen
.\.venv\Scripts\python.exe -m testing scaffold\main.py --games 100 --seed stress-a

# Selbstspiel zur Positions-/Stabilitätsprüfung
.\.venv\Scripts\python.exe -m testing scaffold\main.py --scenario self-play
```

Eine AI soll nach jedem Lauf den ausgegebenen Run-Ordner lesen, insbesondere
`summary.json`, `games.jsonl`, `hands.jsonl`, `stderr.log` und `run.json`.
Neue Läufe bekommen eine eigene ID und überschreiben keine alten Ergebnisse.

## Datensätze und Frontend-Vertrag

`summary.json` ist für Dashboard-Karten gedacht. `games.jsonl` ist für
Game-Vergleiche und `hands.jsonl` für Replay-/Detailansichten gedacht.
`raw-history.json` bleibt als unveränderte Engine-Nähe erhalten.

Die Daten werden in zwei Perspektiven gehalten:

1. **Bot-visible**: Was der Bot laut SDK während der Entscheidung sehen durfte.
2. **Post-game**: Vollständige Engine-History für Replay und Ergebnisprüfung.

Analysen dürfen für Strategieentscheidungen keine versteckten Hole Cards
verwenden. Post-game-Daten dürfen nur zur Auswertung und zum Replay dienen.

Spätere Frontends können direkt auf `run.json`, `summary.json`, `games.jsonl`
und `hands.jsonl` aufsetzen, ohne den Runner zu kennen.

## Austauschbare Gegner

Die standardmäßigen House-Bots sind in `scenarios.py` gesammelt. Für neue
Bot-Versionen übergibt die AI einfach einen neuen Pfad. Für einen eigenen
Referenz-Mix wird später ein neues Scenario-Modul ergänzt; die Engine bleibt
unverändert. Jede Candidate-Datei wird per SHA-256 in `run.json` identifiziert,
damit Ergebnisse trotz gleicher Anzeigenamen eindeutig bleiben.

## Was bewusst nicht in dieser Schicht liegt

- Pokerstrategie
- eigene Spielregeln oder Equity-Engine
- Frontend-Code
- manuell gepflegte Ergebnisdateien
- Tournament-Submission-ZIP-Inhalte

Diese Trennung hält schnelle AI-Iteration und auditable Submission sauber
auseinander.
