# AGENTS.md — CoDCoop

## Platten-Hygiene (verbindlich)

`run/` ist **Wegwerf-Material** (steht in `.gitignore`). Trotzdem ist es der größte
Verbraucher auf `/mnt/intern-1tb`: **jeder QA-Lauf legt eine komplette Spielkopie an
(~15 GB)** — `run/<tag>/host/`, `join1/`, `join2/`, `prefix/`, `runtime/`.

Ist-Stand als Warnung: 266 Läufe ≈ **596 GB**, Platte war bei **99 %** (15 GB frei).

### Vor jedem QA-Lauf

```bash
df -h /mnt/intern-1tb          # < 60 GB frei? -> erst aufräumen, nicht starten
home-cleanup --cod-status      # Anzahl + Top-Verbraucher der Läufe
```

### Nach jedem QA-Lauf (Pflicht, gleiche Session)

1. Nachweise sichern: `result.json`, `provenance.json`, `*.log`, `tree-watch.json`,
   `*-proof.json` nach `run/<tag>/evidence/` kopieren.
2. Schwere Kopien löschen: `run/<tag>/{host,join1,join2,join3,prefix,runtime}`.
3. Läufe, die nicht mehr gebraucht werden: `home-cleanup --cod-runs` (siehe unten).

Ein Lauf, der älter als 12 h ist und nicht in `docs/` referenziert wird, ist Müll.

### Namensschema (macht das Aufräumen automatisierbar)

`run/<familie><n>` — z. B. `qa-noville-m1-union1 … union7`.
Der Prune behält pro Familie die neuesten N und erkennt Zusammen­gehörigkeit am
Zahlen-Suffix. **Keine** Einmalnamen wie `switch-protocol9-bundled-final-final`.

### Aufräumen

```bash
home-cleanup --cod-status                  # Übersicht
home-cleanup --cod-runs --dry-run          # zeigt, was weg würde
home-cleanup --cod-runs                    # löscht überholte Iterationen
home-cleanup --cod-runs --keep 2 --max-age-d 7
```

Der Prune schützt automatisch:

- alles, was in `docs/`, `notes/`, `README*.md`, `CHANGELOG.md` als `run/<name>`
  referenziert ist (Nachweis, z. B. `run/qa-noville-m1-union7`),
- Läufe jünger als `--min-age-h` (Standard 12 h, also „aktiv“),
- alles, worauf ein Prozess gerade arbeitet (er bricht dann ab).

### Schwellen

| Frei auf /mnt/intern-1tb | Verhalten |
|---|---|
| > 100 GB | normal |
| 60–100 GB | nächsten Lauf nur mit `--cod-runs` davor |
| < 60 GB | **kein** neuer QA-Lauf, erst aufräumen |
| < 20 GB | Notfall: alte Familien komplett löschen (`--keep 1 --max-age-d 3`) |

### Nicht anfassen

- `run/<tag>/evidence/` und die in der Doku genannten Läufe (Nachweise).
- `game/`, `build/` nur nach Rücksprache — die sind nicht Teil des QA-Mülls.
- Nichts in `run/` löschen, während ein Wine/Xvfb/QA-Prozess läuft.

### Regel für Berichte

Jeder Abschlussbericht eines QA-Laufs nennt zusätzlich:
`df -h /mnt/intern-1tb` (frei) und ob der Lauf aufgeräumt wurde.
