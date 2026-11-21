# Runtime protocol identity / Identität des Laufzeitprotokolls

A matching file hash does not prove that a Core DLL implements the manifest's
protocol. An older Core could otherwise be pinned into a new runtime lock and
receive a misleading installation receipt.

Eine passende Dateiprüfsumme beweist nicht, dass eine Core-DLL das Protokoll des
Manifests implementiert. Sonst könnte ein alter Kern mit neuer Prüfsummenliste
fälschlich als vollständige Installation versiegelt werden.

## Required metadata / Erforderliche Metadaten

The x86 Core DLL exports `Coop_Protocol` as a little-endian `uint32_t` **DATA**
value in a readable section with neither WRITE nor EXECUTE permission. A
function, forwarded export, missing symbol, ambiguous mapping or malformed PE
is rejected. Inspection reads bounded file bytes; the DLL is never loaded or
executed by the validator.

Die x86-Core-DLL exportiert `Coop_Protocol` als Little-Endian-`uint32_t` in einer
lesbaren, nicht beschreibbaren und nicht ausführbaren Datensektion. Funktionen,
Weiterleitungen, fehlende Symbole und ungültige PE-Strukturen werden abgelehnt.
Die Prüfung lädt oder startet die DLL nicht.

Both `tools/coop_suite.py` and `installer/suite_check.h` enforce this metadata
before seal/check/prepare succeeds. Runtime-lock hashes remain required as well.
The PE readers limit file size to 32 MiB, sections to 96, export entries to 4096
and export names to 127 bytes plus terminator; RVA/ordinal/raw-file ranges are
checked before use.

Python- und nativer Prüfer verlangen die Metadaten vor erfolgreichem
Versiegeln, Prüfen und Vorbereiten. Die bisherigen Prüfsummen bleiben ebenfalls
verbindlich. Dateigröße, Sektionen, Exportanzahl und Namen sind begrenzt;
Adressen und Indizes werden vor dem Zugriff geprüft.

The native checker provides a game-independent metadata command:

```text
suite-check.exe capabilities
{"kind":"codcoop_suite_checker","schema":1,"protocol":9}
```

`stage_suite.py` requires Core protocol = native checker protocol = manifest
protocol **before creating payload output**. On Linux, use a dedicated,
initialized Wine prefix for this metadata command:

```sh
python3 tools/stage_suite.py \
  --game-source /path/to/owned-game \
  --runtime-source /path/to/frozen-runtime \
  --launcher-source /path/to/matching-launcher-bundle \
  --checker-prefix /path/to/isolated-checker-wine-prefix \
  --output /path/to/new-local-overlay
```

The checker prefix must already contain `system.reg` and must be separate from
the source game and output. No default Wine prefix is selected. Native Windows
runs the checker directly. Old proof binaries without this metadata remain
archives and are not accepted as new staging inputs.

Unter Linux wird ein eigener, bereits initialisierter Wine-Präfix benötigt;
der Standardpräfix wird nicht verwendet. Unter Windows läuft der Prüfer direkt.
Ältere Beleg-Binärdateien ohne Metadaten bleiben archivierte Stände und sind
keine gültigen Eingaben für neue Pakete.

## Verification scope / Prüfumfang

Focused tests use minimal readonly PE data fixtures and reject protocols 7/8,
missing/forwarded/writable/executable/out-of-range exports, malformed counts and
ordinals. An opt-in regression uses the preserved pre-enforcement protocol-9
checker to produce a genuine old receipt around a pinned stale Core; current
check and prepare reject it while preserving the prior profile bytes.

These are identity/integrity checks. They do not prove mission completion,
model-cache safety, individual-equipment application or native Windows gameplay.
Protocol 9 does not itself advertise an equipment capability.

Diese Tests prüfen Identität und Integrität. Sie beweisen weder vollständige
Kampagnen noch sichere Modell-Lebenszyklen, individuelle Ausrüstungsübernahme
oder Spielbetrieb unter nativem Windows. Protokoll 9 aktiviert allein keine
Ausrüstungsfähigkeit.
