# Committed session recovery / Wiederverbindung nach dem Neustart

## English

A successfully started target process is not yet a resumed party. Its `running`
event carries `recovering: true`, followed by `reconnecting`. The launcher stays
in recovery until the requested map, role, renderer and party satisfy the native
state check. Only `resumed` restores the active-session display.

After 180 seconds, `recovery_waiting` explains the delay. This is informational:
the game stays open and the party count stays intact. Explicit Retry gracefully
stops only the owned process, clears commands belonging to its lifetime and
restarts the same validated campaign, map, difficulty, endpoint and party.
Fields attached to a Retry control cannot replace the committed specification.
After `resumed`, that recovery specification is discarded.

Newer source also emits `game_stopped` once per owned process, with its actual
exit code and a flag for forced termination. The newer transition harness
requires one nonforced zero exit for every observed game process. Earlier
`d77e`/`cb1c` workers do not contain this telemetry; their supervisor exit and
log checks cannot independently certify every final or Retry game exit code.

Before commitment, Cancel requests the native switch cancellation. After
commitment, the button says **Leave session**: it ends this owned session cleanly
and retains saves. It does not promise to restore an already ended world.

The source tests exercise the actual supervisor loop with fake owned processes,
including live-but-unconnected targets, stale Quit files, delayed readiness,
pre/post-commit cancellation and a Retry after resumption. No native game run or
new frozen bundle is implied by these tests. The health-preset launcher fix is
retained. Earlier `6101`/`38ce` bundles remain the previous, immutable proof scope.

Separate native evidence now exists in
`run/switch-source-native-exits-pass-1795301199610955755/`: two real games
switch from CoD1 training to UO training, explicitly retry committed recovery,
and reconnect with the required party of two. All five observed native process
lifetimes finish nonforced with exit0. This is source-mode transition evidence,
not a full campaign or a frozen-worker gameplay certificate. Its fresh images
also expose same-spawn body intersection, tracked separately from recovery.
New `c6558d2c` Linux and `7ab8e72f` Windows workers contain the stop telemetry;
their build and installer checks are recorded in
`run/worker9-api15-provenance.json`.

## Deutsch

Ein gestarteter Zielprozess bedeutet noch nicht, dass der Trupp wieder verbunden
ist. Sein `running`-Ereignis enthält `recovering: true`; danach folgt
`reconnecting`. Erst wenn Zielkarte, Rolle, Renderer und Gruppe im nativen Zustand
passen, beendet `resumed` die Wiederverbindungsanzeige.

Nach 180 Sekunden erklärt `recovery_waiting` die Verzögerung. Das Spiel bleibt
offen; die Gruppengröße bleibt erhalten. **Erneut versuchen** beendet ausschließlich
den eigenen Prozess geordnet, entfernt dessen alte Befehlsdateien und startet
dieselbe geprüfte Kampagne mit unveränderter Mission, Schwierigkeit, Adresse und
Gruppe. Zusätzliche Felder einer Retry-Nachricht ersetzen diesen Auftrag nicht.

Der neuere Quellstand protokolliert mit `game_stopped` außerdem jeden eigenen
Spielprozess samt tatsächlichem Exitcode und erzwungenem Beenden. Der neue
Wechseltest verlangt für jeden Prozess einen regulären Exit mit Code0. Die
älteren Worker `d77e`/`cb1c` enthalten dies noch nicht; deren Supervisor- und
Logprüfungen belegen nicht unabhängig jeden Spiel-Exit nach Retry oder Stop.
Nach erfolgreicher Wiederverbindung wird der Auftrag verworfen.

Vor der Bestätigung bricht **Wechsel abbrechen** den nativen Wechsel ab. Nach der
Bestätigung heißt die Aktion **Sitzung verlassen**: Sie beendet die eigene Sitzung
geordnet und erhält die Spielstände. Eine bereits beendete Welt wird dadurch
nicht rückgängig gemacht.

Die Quelltests führen die echte Supervisor-Schleife mit kontrollierten
Testprozessen aus. Separat belegt
`run/switch-source-native-exits-pass-1795301199610955755/` den echten Wechsel
zweier Spiele von CoD1-Training zu UO-Training, eine ausdrückliche Wiederholung
nach Bestätigung und die Wiederverbindung mit zwei Spielern. Alle fünf erfassten
Spielprozess-Laufzeiten enden regulär mit Code0. Dies bestätigt diesen Wechsel
mit dem Quellcode-Supervisor, keinen Kampagnendurchlauf oder Laufzeittest der
Frozen-Worker. Frische Bilder zeigen außerdem eine getrennt erfasste
Körperüberschneidung am gemeinsamen Spawn. Neue Worker `c6558d2c` (Linux) und
`7ab8e72f` (Windows) enthalten die Exit-Telemetrie; Build-/Installationsprüfungen
stehen in `run/worker9-api15-provenance.json`. Frühere Nachweise bleiben erhalten.
