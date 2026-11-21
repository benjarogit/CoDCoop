# CoDCoop 0.6 development / Entwicklung

This is a source/development workflow, not a published ready-to-play release.
Dies ist der Entwicklungsweg, kein veröffentlichtes fertiges Release.

## Build / Bauen

Use Python 3.10+ and the 32-bit MinGW-w64 toolchain. / Python ab3.10 und
32-Bit-MinGW-w64 verwenden.

```sh
./build.sh
python3 -m unittest discover -s tests -v
g++ -std=c++17 -Wall -Wextra tests/test_suite_protocol.cpp -o build/test_suite_protocol
./build/test_suite_protocol
g++ -std=c++17 -fsanitize=address,undefined tests/test_anim_fragments.cpp -o build/test_anim_fragments
./build/test_anim_fragments
g++ -std=c++17 -fsanitize=address,undefined tests/test_cinematics.cpp -o build/test_cinematics
./build/test_cinematics
g++ -std=c++17 -fsanitize=address,undefined tests/test_patch_ownership.cpp -o build/test_patch_ownership
./build/test_patch_ownership
g++ -std=c++17 -fsanitize=address,undefined tests/test_pregame_gate.cpp -o build/test_pregame_gate
./build/test_pregame_gate
g++ -std=c++17 -fsanitize=address,undefined tests/test_host_rules.cpp -o build/test_host_rules
./build/test_host_rules
g++ -std=c++17 -fsanitize=address,undefined tests/test_archive_rules.cpp -o build/test_archive_rules
./build/test_archive_rules
g++ -std=c++17 -fsanitize=address,undefined tests/test_reload_delivery.cpp -o build/test_reload_delivery
./build/test_reload_delivery
g++ -std=c++17 -fsanitize=address,undefined tests/test_qa_renderer_preload.cpp -o build/test_qa_renderer_preload
./build/test_qa_renderer_preload
g++ -std=c++17 -fsanitize=address,undefined tests/test_qa_deferred_models.cpp -o build/test_qa_deferred_models
./build/test_qa_deferred_models
g++ -std=c++17 -fsanitize=address,undefined tests/test_tree_ownership.cpp -o build/test_tree_ownership
./build/test_tree_ownership
g++ -std=c++17 -fsanitize=address,undefined tests/test_mt_epoch.cpp -o build/test_mt_epoch
./build/test_mt_epoch
g++ -std=c++17 -fsanitize=address,undefined tests/test_qa_dobj_mapping_barrier.cpp -o build/test_qa_dobj_mapping_barrier
./build/test_qa_dobj_mapping_barrier
g++ -std=c++17 -fsanitize=address,undefined tests/test_world_wire.cpp -o build/test_world_wire
./build/test_world_wire
g++ -std=c++17 -fsanitize=address,undefined tests/test_host_body_ownership.cpp -o build/test_host_body_ownership
./build/test_host_body_ownership
g++ -std=c++17 -fsanitize=address,undefined tests/test_host_body_policy.cpp -o build/test_host_body_policy
./build/test_host_body_policy
g++ -std=c++17 -fsanitize=address,undefined tests/test_peer_inventory.cpp -o build/test_peer_inventory
./build/test_peer_inventory
g++ -std=c++17 -fsanitize=address,undefined tests/test_save_provenance.cpp -o build/test_save_provenance
./build/test_save_provenance
g++ -std=c++17 -fsanitize=address,undefined tests/test_spawn_ticket.cpp -o build/test_spawn_ticket
./build/test_spawn_ticket
g++ -std=c++17 -fsanitize=address,undefined tests/test_weapon_selection.cpp -o build/test_weapon_selection
./build/test_weapon_selection
g++ -std=c++17 -fsanitize=address,undefined tests/test_asset_bootstrap.cpp -o build/test_asset_bootstrap
./build/test_asset_bootstrap
```

The asset-bootstrap fixture tests bounded model/ordered-weapon metadata transfer
and rejects mismatched native weapon indices or item-registration flags. It does
not certify actual native weapon/item registration, a ready lobby or production
map-start ordering. The runtime must bind it to the existing session/world and
gameplay identity and use real SHA256 before applying anything.
Die Ressourcen-Fixture prüft die begrenzte Übertragung von Modell- und geordneten
Waffenmetadaten und lehnt falsche native Waffenindizes oder Item-Freigaben ab.
Sie bestätigt keine tatsächliche Registrierung, Lobby oder Produktionsstartfolge.
Die Laufzeit muss Sitzung/Welt und Spielinhalt binden und echtes SHA256 prüfen.

Native checker interoperability uses an isolated Wine prefix. / Der native
Prüfer wird gegen ein getrenntes Wine-Prefix getestet:

```sh
COOP_NATIVE_CHECKER=build/suite-check.exe \
COOP_WINE_PREFIX="$PWD/run/native-prefix" \
python3 -m unittest discover -s tests -p test_installer_native.py -v
```

Do not point this at your normal Wine prefix. / Nicht das normale Wine-Prefix verwenden.

The native engine identity test also uses real Wine CryptoAPI hashing and checks
that prepared QA profiles remain quarantined from regular peers. / Der native
Identitätstest verwendet echte CryptoAPI-Prüfsummen unter Wine und prüft die
Trennung vorbereiteter QA-Profile von regulären Sitzungen:

```sh
COOP_WINE_PREFIX="$PWD/run/native-prefix" \
python3 -m unittest discover -s tests -p test_identity_native.py -v
```

Build Windows setup without a checked-in game directory from an already verified
installed copy. / Windows-Setup aus einer bereits geprüften Kopie bauen:

```sh
python3 tools/build-installer.py --game-source "/path/to/verified/copy" \
  --runtime-source "/path/to/immutable/runtime" --output build/Install-CoD-Coop.exe
```

## Local payload / Lokales Paket

The staging tool reads the owner's game and produces a separate payload. It
validates pinned YAP archives, applies the reviewed UO LAA flag in the copy,
builds per-variant overlays and writes the runtime lock. It never modifies the
source game.

Das Werkzeug liest die vorhandenen Spieldaten und erzeugt ein getrenntes Paket.
Es prüft YAP-Archive, setzt das geprüfte UO-LAA-Flag in der Kopie, baut die
Variantenanpassungen und schreibt die Laufzeit-Prüfsummen. Das Quellspiel bleibt
unverändert.

```sh
python3 tools/build-launcher.py --output build/launcher
python3 tools/stage_suite.py --game-source "/path/to/owned/Call of Duty" \
  --output run/suite-payload
python3 tools/install-linux.py --game "/path/to/test/Call of Duty" \
  --suite-source run/suite-payload --language de --repair --yes
python3 tools/coop_suite.py check --game "/path/to/test/Call of Duty"
```

Supply the pinned YAP r169 ZIP and extras7z through `--yap-archive` and
`--yap-extras`, or their documented local defaults. This step requires7-Zip to
normalize extras; end users receive normal files. See `--help` for exact inputs.

YAP-r169-ZIP und Zusatz-7z über die genannten Optionen oder die lokalen
Standardpfade bereitstellen. Beim Paketbau wird7-Zip benötigt; Endnutzer bekommen
bereits vorbereitete Dateien. `--help` zeigt alle Eingaben.

A Windows payload must include a Windows launcher executable and its runtime.
The setup refuses a Linux-only payload on Windows. A Linux AppImage needs Linux
launcher files. Do not mix their `_internal` directories.

Ein Windows-Paket benötigt einen Windows-Launcher samt Laufzeit. Das Setup lehnt
reine Linux-Pakete unter Windows ab. Linux benötigt Linux-Dateien; die
`_internal`-Verzeichnisse nicht vermischen.

## Launch and transitions / Start und Wechsel

```sh
python3 tools/launch-gui.py --game "/path/to/test/Call of Duty"
# Terminal supervisor / Terminal-Sitzungssteuerung:
python3 tools/coop_session.py --game "/path/to/test/Call of Duty" \
  --variant cod1 --hosting --map training --runner wine
```

For Proton, configure the appropriate runner and Steam launch context; plain
system Wine does not certify Steam integration. / Für Proton den passenden
Runner und Steam-Startkontext konfigurieren. System-Wine bestätigt keine
Steam-Integration.

The GUI sends confirmed host selections to `coopswitch <variant>`. The engine
checks participant readiness, waits for a safe point, saves `coop_switch`, and
requests a supervised restart. `coopswitchretry` and `coopswitchcancel` control a
pending transition. Incoming variants are allowlisted IDs, never shell commands.

Die Oberfläche sendet bestätigte Host-Auswahlen an `coopswitch <variante>`.
Die Engine prüft die Bereitschaft, wartet auf einen sicheren Punkt, speichert
`coop_switch` und fordert den begleiteten Neustart an. Die genannten Befehle
wiederholen oder stoppen ausstehende Wechsel. Übertragen werden zugelassene
Variantenkennungen, keine Shellbefehle.

## Real game smoke tests / Echte Spieltests

```sh
python3 tools/qa_coop.py --source "/path/to/owned/Call of Duty" \
  --run run/qa-cod1 --variant cod1 --map training --players 2
python3 tools/qa_coop.py --source "/path/to/owned/Call of Duty" \
  --run run/qa-four --variant cod1 --map training --players 4
# Waiting joiner before host / Mitspieler wartet vor dem Host:
python3 tools/qa_coop.py --source "/path/to/owned/Call of Duty" \
  --run run/qa-delayed-host --variant cod1 --map training --players 2 --host-delay 35
python3 tools/qa_coop.py --source "/path/to/owned/Call of Duty" \
  --run run/qa-checkpoint --variant cod1 --map training --players 2 --checkpoint-reloads 3
```

The network gate uses the real UDP relay from
[Co-op Anything](https://github.com/cranebeaker/coop-anything/tree/e83fc578ad2c3d3bb30b06f98ba11d965d11e105/tools/chaos),
pinned to the reviewed revision below. The runner rejects another revision or
modified checkout, records the profile/seed, and owns only its relay process.

Der Netzwerktest verwendet den echten UDP-Relay aus Co-op Anything, festgelegt
auf diesen geprüften Stand. Andere oder lokal veränderte Stände werden abgelehnt.
Profil, Seed und Paketereignisse werden aufgezeichnet.

```sh
git clone https://github.com/cranebeaker/coop-anything.git run/reference/coop-anything
git -C run/reference/coop-anything checkout e83fc578ad2c3d3bb30b06f98ba11d965d11e105
python3 tools/qa_coop.py --source "/path/to/owned/Call of Duty" \
  --run run/qa-network --variant cod1 --map training --players 2 \
  --chaos-checkout run/reference/coop-anything --chaos-profile bad_wifi \
  --chaos-seed 260621 --duration 30
```

This is a real-client impairment test, not proof of every campaign or Steam.
Dies ist ein echter Netzwerktest mit Spielinstanzen, kein Nachweis für jede
Kampagne oder die Steam-Verbindung.

To target loss of the actual map-reload controls, use a bounded two-second
server-to-client partition. The probe requires packet-log evidence, automatic
reconnection to the new map and actual remote movement; it never injects a new
join command. A failure is an open recovery defect, not a passing smoke test.

Für den gezielten Verlust der Wechselnachrichten unterbricht dieser Test die
Host-Richtung für zwei Sekunden. Paketnachweis, selbstständige Wiederverbindung
und echte Bewegung sind Pflicht; ein erneuter Beitritt wird nicht erzwungen.

```sh
python3 tools/qa_partition_probe.py --source "/path/to/owned/Call of Duty" \
  --run run/qa-partition --runtime-dir run/reliable-reload-prototype \
  --chaos-checkout run/reference/coop-anything
# Reverse direction drops the acknowledgement / Gegenrichtung verliert die Bestätigung:
python3 tools/qa_partition_probe.py --source "/path/to/owned/Call of Duty" \
  --run run/qa-partition-ack --runtime-dir run/reliable-reload-prototype \
  --chaos-checkout run/reference/coop-anything --partition-direction c2s
python3 tools/qa_reload_cancel_probe.py --source "/path/to/owned/Call of Duty" \
  --run run/qa-cancel --runtime-dir run/reload-cancel-prototype
python3 tools/qa_reconnect_probe.py --source "/path/to/owned/Call of Duty" \
  --run run/qa-reconnect --runtime-dir run/world-wire-final \
  --chaos-checkout run/reference/coop-anything
python3 tools/qa_world_replay_probe.py --source "/path/to/owned/Call of Duty" \
  --run run/qa-world-replay --runtime-dir run/world-wire-final \
  --chaos-checkout run/reference/coop-anything
```

Each run copies game files, freezes one build of the runtime for all slots, owns
its Xvfb/Wine prefix, checks real user-command advancement and movement, requests
game screenshots, and verifies clean exit. Never uses hardlinks or global
`wineserver -k`. QA identities cannot join regular sessions.

Jeder Lauf kopiert die Spieldaten, verwendet denselben Laufzeit-Build für alle
Instanzen und besitzt ein eigenes Xvfb/Wine-Prefix. Mitspielerbefehle, Bewegung,
Spielbilder und sauberes Beenden werden geprüft. Keine Hardlinks und kein
globales Beenden von Wineserver. QA-Sitzungen sind von normalen Sitzungen getrennt.

**A smoke PASS is not a campaign completion. / Ein kurzer erfolgreicher Test ist
kein Nachweis einer durchgespielten Kampagne.**

Use `--runtime-dir /path/to/immutable/runtime` on `qa_coop.py` and the campaign,
mainline and movie probes to bind a regression to exact preserved DLL inputs.
Never point it at the output directory that the runner archives on retries.

Mit `--runtime-dir /pfad/zum/festen/runtime` einen konkreten DLL-Stand vorgeben.
Dieses Verzeichnis muss außerhalb der bei Wiederholungen archivierten Ausgabe
liegen. Laufzeit-Prüfsummen und Testumfang stehen in `provenance.json` und
`result.json`; ein älteres Ergebnis gilt nicht automatisch für einen neueren Build.

```sh
python3 tools/qa_movie_probe.py --source "/path/to/test/source" \
  --run run/qa-movie --runtime-dir "/path/to/immutable/runtime"
python3 tools/qa_mainline_probe.py --source "/path/to/test/source" \
  --run run/qa-mainline --runtime-dir "/path/to/immutable/runtime"
python3 tools/qa_party_probe.py --source "/path/to/test/source" \
  --run run/qa-party --runtime-dir "/path/to/immutable/runtime"
python3 tools/qa_host_rules_probe.py --source "/path/to/test/source" \
  --run run/qa-rules --runtime-dir "/path/to/immutable/runtime"
python3 tools/qa_archive_rules_probe.py --source "/path/to/test/source" \
  --run run/qa-archive --runtime-dir "/path/to/immutable/runtime"
```

The party probe checks explicit departure, normal host-only next-mission start
and a genuine remote rejoin. It must not simulate the second mission's start
click. / Der Gruppentest prüft bewusstes Verlassen, regulären Start der nächsten
Mission allein beim Host und echten Wiederbeitritt, ohne den zweiten Startklick
künstlich auszulösen.
