# Feasibility: kleines neuronales Netz im Poker-Bot

**Stand:** 2026-10-02  
**Kontext:** Die Turnierregeln erlauben ein selbst entwickeltes und zur Laufzeit
eingesetztes neuronales Netzwerk. Nicht erlaubt ist ein vollständiges LLM oder
ein externer KI-/Service-Aufruf während des Spiels.

## Kurzfazit

Ja, ein kleines neuronales Netz ist technisch machbar und regelkonform. Es ist
aber nur als kompakter Bestandteil einer Poker-Policy sinnvoll, nicht als
vollständiger Ersatz für Legalitätsprüfungen, Pot-Odds und robuste
Fallback-Regeln.

Die beste Kosten-Nutzen-Variante ist ein **hybrider Bot**:

1. deterministische State- und Legalitätslogik,
2. berechnete Poker-Features statt roher Text- oder Karten-IDs,
3. kleines MLP für eine begrenzte Entscheidung, zum Beispiel
   `fold/check`, `call` oder `raise` plus Raise-Größe,
4. deterministischer Fallback bei niedrigem Clock-Stand oder ungültiger
   Modell-Ausgabe.

Ein großes Modell, Online-Training während des Spiels oder eine Suche über
viele Spielvarianten ist unter den Zeit- und Ressourcenlimits nicht
empfehlenswert.

## Randbedingungen und Konsequenzen

### Erlaubnis und Deployment

- Die Regeln erlauben selbst geschriebenen Bot-Code; AI-Tools sind nur zur
  Entwicklung erlaubt. Zur Laufzeit darf der Bot weder ein LLM noch Netzwerk,
  externe APIs, Prozesse oder Hintergrund-Threads verwenden.
- `numpy` ist als Runtime-Abhängigkeit erlaubt. Gewichte müssen mit dem
  Submission-ZIP ausgeliefert werden. Am sichersten ist, kleine Gewichte direkt
  als Python-Konstanten einzubetten, statt auf Dateien außerhalb des ZIPs zu
  vertrauen.
- Training gehört in den Entwicklungs-/Offline-Schritt. Das eingereichte
  Programm sollte nur Inferenz ausführen. Zwischen Spielen darf kein Wissen
  vorausgesetzt werden; jeder Spielprozess startet frisch.

### Zeitbudget

Ein Spiel umfasst 100 Hände und hat 30 Sekunden Zeitbank plus 0,1 Sekunden
pro Hand. Eine Entscheidung bis 0,1 Sekunden belastet die Zeitbank nicht,
aber die 0,1 Sekunden sind **kein** sinnvolles Zielbudget für die Inferenz:
`act()` kann pro Hand mehrfach aufgerufen werden und Schwankungen würden sich
aufsummieren.

Für ein einzelnes kleines MLP ist die Rechenmenge gering:

- Eingabe: etwa 24–48 numerische Features,
- eine versteckte Schicht mit etwa 16–32 Neuronen,
- 3–5 Ausgaben für Aktion/Größe,
- keine rekurrenten Schichten und keine Suche im Inferenzpfad.

Bei dieser Größenordnung ist Inferenz auf einem Kern grundsätzlich
unkritisch. Für den Turnierbetrieb sollte trotzdem ein Ziel von höchstens
5–10 ms pro `act()` angesetzt werden, damit Feature-Berechnung, Python- und
`numpy`-Overhead sowie mehrere Aktionen pro Hand sicher in der 30-Sekunden-
Zeitbank bleiben. Die tatsächliche Zielmaschine muss den Wert vor der
Submission messen; die Entwicklungsumgebung hat derzeit kein installiertes
`numpy`, daher liegt aus diesem Repository noch kein belastbarer
Benchmarkwert vor.

### Warum es strategisch helfen kann

- Duplicate Deals reduzieren den Einfluss des Kartenglücks: In einer Runde
  werden dieselben Hände aus allen Sitzen gespielt. Bessere Entscheidungen
  können dadurch direkt gegen eine Regelstrategie verglichen werden.
- Beobachter-Hooks liefern öffentliche Aktionen und Showdown-Karten. Ein
  Modell kann daraus pro Spieler einfache Tendenzen nutzen, solange die
  Statistiken nach Player-ID und nur innerhalb des aktuellen Spiels geführt
  werden.
- Ein Modell kann nicht sichtbare Hole Cards oder die Zukunft rekonstruieren.
  Es sollte deshalb nicht versuchen, eine vermeintliche perfekte
  Spieltheorie zu lernen, sondern robuste Aktionsgrenzen und Größen
  approximieren.

## Empfohlene Modellgrenze

### Sinnvoller erster Prototyp

Trainiere offline auf simulierten oder aufgezeichneten, regelkonformen
Entscheidungssituationen ein kleines MLP mit:

- Features für Position, Street, Pot, `to_call`, effektiven Stack und
  Stack-to-Pot-Ratio,
- hand-strength-/draw-/board-texture-Features aus einem schnellen
  deterministischen Evaluator,
- kompakten Gegnerstatistiken wie beobachtete Raise-/Fold-/Showdown-Raten,
- Ausgaben für Aktionspräferenz und eine grobe Raise-Kategorie.

Die Ausgabe sollte nicht direkt eine möglicherweise illegale SDK-Aktion
erzeugen. Eine Policy-Schicht klemmt die Ausgabe auf
`state.can_raise`, `min_raise_to`, `max_raise_to` und die übrigen legalen
Zustände. Bei Unsicherheit wird auf eine getestete Pot-Odds-/Positionsregel
zurückgefallen.

### Nicht sinnvoll als erster Ansatz

- großes MLP, Transformer, LSTM oder „LLM als Pokerberater“,
- Online-Gradientenupdates in `act()`,
- Monte-Carlo-Suche über viele zufällige Zukunftsverläufe,
- End-to-end-Eingabe als undurchsichtige Karten-/History-Vektoren ohne
  Baseline,
- Modell, das die Legalitätslogik oder Clock-Prüfung ersetzt.

Diese Varianten erhöhen Debugging- und TLE-Risiko stärker, als sie bei nur
100 Händen pro Spiel voraussichtlich zusätzliche Spielstärke liefern.

## Validierungsplan

Ein neuronales Netz sollte nur übernommen werden, wenn es die regelbasierte
Baseline reproduzierbar schlägt:

1. Baseline und Modell mit demselben `--seed` und denselben Duplicate Deals
   ausführen.
2. Mindestens mehrere unabhängige Seeds und ausreichend viele Spiele
   vergleichen; ein einzelner Lauf kann ein Deck-Artefakt sein.
3. `mbb_per_hand`, Chip-Summe und Nicht-OK-Verdicts getrennt auswerten.
4. Produktionspfad mit `--subprocess` testen, nicht nur In-Process.
5. Worst-Case-Laufzeit von Feature-Berechnung und `act()` messen; bei
   `clock_ms` nahe null muss der Fallback sofort greifen.
6. Jede Ausgabe auf legale Aktionen, Raise-to-Semantik, All-in,
   Short-Stack, alle Streets und wechselnde Sitze testen.

**Entscheidungskriterium:** Das Modell wird nur behalten, wenn der Vorteil
über mehrere Seeds stabil ist und kein TLE/RTE/PV auftritt. Andernfalls ist
eine verbesserte deterministische Policy die bessere Nutzung der knappen
Hackathon-Zeit.

## Verbindliche Projektannahme

Für die weitere Bot-Entwicklung gilt: Ein kleines, offline trainiertes
neuronales Netz ist erlaubt und kann eingesetzt werden; ein vollständiges LLM
oder irgendein externer KI-Aufruf zur Laufzeit bleibt ausgeschlossen. Die
Implementierung muss auf einem Kern, ohne Netzwerk und mit einer konservativen
Inferenzzeit funktionieren.
