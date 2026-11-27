# CoDCoop 0.6 development / Entwicklung

This is a source/development workflow, not a published ready-to-play release.
Dies ist der Entwicklungsweg, kein veröffentlichtes fertiges Release.

## Build / Bauen

Use Python 3.10+ and the 32-bit MinGW-w64 toolchain. / Python ab3.10 und
32-Bit-MinGW-w64 verwenden.

Before staging 0.6.3, regenerate the CoD and UO menu packages from the owned
game data with `python3 -I tools/make_ui.py --game "/path/to/staging-game"`. Use the resulting `pakz_coop.pk3`
files for both target-OS suites. The in-game Internet IPv4 control opens a
lookup on demand, and the launcher can copy both addresses with the port.

Vor dem Paketbau für 0.6.3 die Coop-Menüs für CoD und UO mit
`python3 -I tools/make_ui.py --game "/Pfad/zum/Testspielordner"` aus den eigenen Spieldaten neu bauen. Die dabei
erzeugten `pakz_coop.pk3` für beide Plattformpakete verwenden. Im Spiel wird
die öffentliche IPv4 auf Klick ermittelt. Der Launcher kopiert beide Adressen
mit Port.

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
g++ -std=c++17 -fsanitize=address,undefined tests/test_join_guard.cpp -o build/test_join_guard
./build/test_join_guard
g++ -std=c++17 -fsanitize=address,undefined tests/test_join_placement.cpp -o build/test_join_placement
./build/test_join_placement
g++ -std=c++17 -fsanitize=address,undefined tests/test_trigger_filter.cpp -o build/test_trigger_filter
./build/test_trigger_filter
g++ -std=c++17 -fsanitize=address,undefined tests/test_frozen_vm.cpp -o build/test_frozen_vm
./build/test_frozen_vm
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
python3 tools/launcher_provenance.py --output build/launcher-source-graph.json
python3 tools/build-launcher.py --source-graph build/launcher-source-graph.json --output build/launcher
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

### Windows release ZIP / Windows-Installationspaket

Package the verified installer and matching staged Windows suite in one ZIP.
Das geprüfte Setup und die passende Windows-Suite kommen in eine ZIP-Datei.

```sh
python3 tools/package-windows.py --installer build/Install-CoD-Coop.exe \
  --suite run/suite-windows --output build/Install-CoD-Coop-Windows-x86_64.zip
```

The installer opens from the extracted folder and discovers the adjacent
`suite/` directory. Nach dem Entpacken findet das Setup den Ordner `suite/`
neben der EXE.

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

The relay adds packet loss and delay while both game instances run on one machine.
Der Relay simuliert Paketverlust und Verzögerung auf demselben Rechner.

### Separate home networks / Getrennte Heimnetze

The Linux runner creates two private subnets and two NAT routers inside an
isolated network namespace. Direct IP checks that the game port stays blocked
without forwarding and with the host firewall closed, then connects through the
translated public port. WireGuard carries game UDP over an encrypted tunnel
while the public game port stays closed. CI runs the UDP probes. Add game
arguments after `--` to run two actual game processes under Wine, each with its own
prefix. The JSON reports identify the topology and transport.

Der Linux-Runner erzeugt zwei private Netze mit je einem NAT-Router in einem
isolierten Netzwerk-Namespace. Der Direkt-IP-Test prüft die fehlende Weiterleitung
und die geschlossene Host-Firewall und verbindet anschließend über den
übersetzten Außenport. Der WireGuard-Test überträgt Spiel-UDP im verschlüsselten
Tunnel bei geschlossenem öffentlichem Spielport. CI führt die UDP-Tests aus.
Mit Spielargumenten nach `--` laufen zwei echte Spielinstanzen unter Wine mit
eigenen Prefixes. Topologie und Transport stehen in den JSON-Berichten.

The test needs Linux network namespaces, `iproute2`, and `nftables`. Install
`wireguard-tools` for tunnel mode and Wine and Xvfb for gameplay.
Keep game input and output on the same filesystem.

Der Test benötigt Linux-Netzwerk-Namespaces, `iproute2` und `nftables`. Für den
Tunnel kommen `wireguard-tools` hinzu, für die Spieltests Wine und Xvfb.
Spielquelle und Ausgabe müssen auf demselben Dateisystem liegen.

```sh
mkdir -p run
unshare -Urn python3 tools/qa_home_network.py --transport direct \
  --report run/home-direct-network.json
unshare -Urn python3 tools/qa_home_network.py --transport wireguard \
  --report run/home-vpn-network.json -- \
  --source "/path/to/owned/Call of Duty" --run run/qa-home-vpn1 \
  --variant cod1 --map training --players 2 --checkpoint-reloads 1
```

#### Release check across two internet connections / Release-Abnahme über zwei Internetanschlüsse

Use the matching release installers, the same campaign, and two separate
internet connections. A home connection and a mobile hotspot on the other
computer work. Test once with a Linux host and Windows joiner, then swap roles.

Beide Rechner brauchen die passenden Installationspakete, dieselbe Kampagne und
getrennte Internetanschlüsse. Ein Heimanschluss und ein Mobilfunk-Hotspot am
anderen Rechner genügen. Erst Linux als Host und Windows als Mitspieler testen,
dann die Rollen tauschen.

1. **Direct IP / Direkt-IP.** Join using the host's public IPv4 and the router's
   external UDP port. Verify that forwarding leads to the game port and the
   host firewall allows it. / Öffentliche IPv4 und externen UDP-Port des Hosts
   verwenden. Weiterleitung zum Spielport und Host-Firewall prüfen.
2. **Tailscale.** Join using the host's Tailscale IPv4 and the game port. Keep the
   public game port closed. Record `tailscale status` during play and test direct
   and relayed connections separately. An initial relay ping followed by a direct
   game connection counts as direct. / Tailscale-IPv4 des Hosts und dessen
   Spielport verwenden. Öffentlichen Spielport geschlossen halten. Während des
   Spiels den Verbindungsweg mit `tailscale status` erfassen und direkte sowie
   Relay-Verbindungen getrennt testen. Ein erster Ping über den Relay mit
   anschließend direktem Spielverkehr zählt als direkte Verbindung.
   [Tailscale connection types / Verbindungsarten](https://tailscale.com/docs/reference/connection-types)
3. **Steam.** Use two signed-in accounts and join through a real Steam invite.
   A session with the test Steam API covers the local join flow only. /
   Zwei angemeldete Konten und eine echte Steam-Einladung verwenden. Die
   Test-Steam-API deckt den lokalen Beitrittsablauf ab.

For each run, confirm that both players enter the mission, can move, and can
continue after a checkpoint reload. Leave and rejoin once. Record the
release, host and joiner OS, campaign, transport, outcome, and the relevant
`codcoop.log` and `codcoop_join.log` excerpts from each side. Radmin VPN's
documented platform is Windows. If tested, record it as a separate Windows-to-Windows case.

Pro Lauf prüfen, ob beide in die Mission gelangen, sich bewegen und nach dem
Laden eines Checkpoints weiterspielen können. Einmal das Spiel verlassen und
erneut beitreten. Release, Betriebssysteme, Kampagne, Transport, Ergebnis und
relevante Ausschnitte aus `codcoop.log` und `codcoop_join.log` beider Seiten
sichern. Radmin VPN ist für Windows dokumentiert und erhält bei einem Test
einen eigenen Windows-zu-Windows-Eintrag.
[Radmin VPN system requirements / Systemanforderungen](https://www.radmin-vpn.com/help/)

### Recovery probes / Wiederverbindungstests

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

Each run uses private configs and saves, freezes the tested runtime, owns its
Xvfb and Wine processes, and checks user-command advancement, movement, and
clean exit. The two-home runner hardlinks immutable game archives. QA identities
can only join other QA sessions.

Jeder Lauf nutzt eigene Konfigurationen und Spielstände, sichert den getesteten
Laufzeitstand, startet eigene Xvfb- und Wine-Prozesse und prüft Mitspielerbefehle,
Bewegung und sauberes Beenden. Der Heimnetztest verlinkt unveränderliche
Spieldatenarchive. QA-Instanzen können nur anderen QA-Sitzungen beitreten.

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

### Save and actor eligibility / Spielstand und Missionsakteure

The native-derived actor publication is `coop_actor_api=1`, mode HOST/SOLO/
JOINER and per-slot `coop_actor_<n>_identity` plus state WAIT/ELIGIBLE/INELIGIBLE.
HOST identities use the current session, slot, spawn ticket and world tuple;
SOLO uses `solo|<sv_serverid>|0`. Scripts cannot grant eligibility by writing an
inventory receipt. Standing1HP is eligible; downed1HP is not. Native publication
updates on preservation, health, downed/revive and world-ready transitions and
each Core pump. DLL shutdown invalidates the API and all slots.

Die Freigabe für Missionsaktionen stammt aus dem aktuellen nativen Spieler- und
Weltzustand. Ein niedergeschlagener Spieler mit1HP erhält keine Freigabe; ein
stehender Spieler mit1HP bleibt berechtigt. Skriptbelege ersetzen diese Prüfung
nicht. Beim Entladen des Core werden alle Freigaben ungültig.

```sh
for name in inventory_preservation saved_remote_patch actor_eligibility; do
  g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined \
    "tests/test_${name}.cpp" -o "build/test_${name}" && "build/test_${name}" || exit 1
done
python3 -m unittest discover -s tests -v
```

The full sanitizer list is in `.github/workflows/development.yml`. Targeted
Brecourt scene tests do not count as a complete Brecourt playthrough. / Die
vollständige Sanitizer-Liste steht im CI-Workflow. Ein isolierter Brecourt-
Mechaniktest zählt nicht als durchgespielte Mission.

### Native package priority / Native Paketreihenfolge

Do not infer script priority from Python lowercase filename sorting or the
number of leading `z` characters. Native PathCmp folds ASCII letters to
**uppercase**, then compares punctuation. Verified native addresses are
CoD1 1.5 `0x424420` and UO1.51 `0x425840`; their91-byte bodies are identical.
The CoD1 archive comparator `0x4247a0` calls this function; UO uses `0x425bd0`.
Native package insertion reverses ascending order for lookup. CoD1 additionally
sorts lowercase `sp_` as `zz_`, restores it before opening and skips `mp_` packs.
A physical `zz_*.pk3` is therefore a reserved alias, not a safe override name.
UO does not have that `sp_`/`zz_` alias behavior. Localized packages have separate
language ordering and remain excluded from the campaign source inventory.

Die Skriptpriorität ergibt sich nicht aus der Anzahl vorangestellter `z`.
Die Engine vergleicht ASCII-Großbuchstaben und Satzzeichen. CoD1 behandelt
`zz_` außerdem als reservierten Alias für `sp_`; UO tut dies nicht. Darum
verwendet das Inventar je nach Profil die passende Engine-Reihenfolge.
Produktionspakete wurden aufgrund dieses Befunds nicht pauschal umbenannt.

Evidence: `run/campaign-investigation/native-package-order/` and native search
path in `run/qa-cod1-four/history/brecourt-cb7071-old-overlay-precedence-TIMEOUT-1795298622366242296/host/Main/console.log`.
CoD1 SHA256: `c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`.
UO raw QA SHA256: `c17e57c060f08ef65d7cddea738cced61ab7ccb6d98df95fe185b1ab8aa7e325`;
the supported prepared UO `0a0c52e5…` has byte-identical compared functions.
This is PE disassembly and real engine search-path evidence, not a new Ghidra
decompilation or a successful mission-interaction proof.

Reproducible native builds / Reproduzierbare native Builds: preserve both the
compiler version and the exact output argument. MinGW chooses a DLL's default
ImageBase from that argument; compiling identical sources to a different output
path can legitimately produce another SHA256. Two normal `./build.sh` runs from
frozen source checkpoint `98de830` produced byte-identical Core
`6dba814dd378a7c2f69ec9238512ad648b14d5a04df2aa3ed1a268bdf09b828d`,
loader `85fc865c…` and checker `0cd064f6…`. The separately named experimental
Core `602cb6af…` has identical source but its own native evidence and immutable
binary; do not substitute one hash for another in a tested payload.
Dieselben Quelldateien unter einem anderen Ausgabepfad können wegen der
automatisch gewählten ImageBase andere Prüfsummen ergeben. Testnachweise und
Paketierung bleiben deshalb an die tatsächlich ausgeführte Binärdatei gebunden.

```sh
python3 -m unittest discover -s tests -p test_campaign_inventory.py -v
i686-w64-mingw32-objdump -d --start-address=0x424420 \
  --stop-address=0x42447b /path/to/CoDSP.exe
i686-w64-mingw32-objdump -d --start-address=0x425840 \
  --stop-address=0x42589b /path/to/CoDUOSP.exe
```
