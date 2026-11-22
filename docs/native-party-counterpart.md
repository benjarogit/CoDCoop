# Native party bridge counterpart / Native Gegenstelle

**Status: helpers and contract fixtures only.** These headers are not included
by Core. No game socket, native slot allocation, kit application, launcher
capability, package build or release is enabled by this work. The existing
compiled feature16 means initial asset bootstrap support only.

## Implemented helpers

- `party_native_bridge.h`: fixed POD transaction state for three pending indices
  (distinct from player slots), native-session/global uint64 serial fences,
  unpredictable nonce inputs, wrap-safe30s native deadline and one-use consume
  before returning the confirmed GUID's **originally issued slot**. Roster,
  endpoint, world, plan, resource digest, descriptor and native-init receipts
  must still match. Worker restarts do not reset the native serial epoch.
- `party_native_bridge_json.h`: bounded131072-byte JSON, depth16/node8192 limits,
  duplicate decoded-key rejection, exact integer handling and Python-compatible
  canonical `ensure_ascii` output. UTF8/paired Unicode escapes are supported for
  pinned catalog prose; typed IDs, family names, endpoints and map names retain
  their narrower validation. No JSON value is executed as a command or path.
- `party_native_bridge_plan.h`: parses the actual worker `party.json` full plan;
  recomputes canonical catalog/world/plan identity; binds all confirmed owners,
  individual kits and current worker heartbeat. A pre-GAME_INIT plan receipt
  must match the actual native-init serial before phase2 may issue a challenge.
- `party_native_bridge_catalog.h`: exact original menu choice validation,
  alternate-weapon closure and selected server/media/support requirements for
  all four kits. Smoke aircraft follows an **independently supplied authoritative
  world graph**. Copying the declared party world into that parameter would not
  establish native authority. Unresolved automatic kits fail closed; their
  authoritative original map/year resolver remains required before final hash.
- `party_native_bridge_win.h`: CryptoAPI SHA256/randomness and fixed local
  record IO, owner/write-ACL/reparse checks, bounded stable reads and atomic
  replacement. Native cannot write worker-owned `party.json` or ACK records.
  On Wine, actual POSIX symlinks require an additional resolved-Unix-name check:
  Wine's apparent DOS handle path/reparse flag alone did not reject them.

All JSON/STL objects are ephemeral. Only the explicit POD stores may be added to
future versioned Core State; no such State change is made by these helpers.
Bridge endpoints store numerical IPv4 octets/ports in host order; the future
socket adapter must use `ntohl`/`ntohs` when converting `sockaddr_in`. The existing
resource-bootstrap endpoint stores raw socket/network-order values instead.

## Required Core integration seams — not yet implemented

1. Read the receipt-checked local worker context and full four-owner kit plan
   **before Host GAME_INIT**. Verify the installed catalog and actual UF map/year
   graph. Stage only reviewed fixed equipment/world inputs, not arbitrary CVars.
   Bind the native plan receipt to the intended world/init serial. Missing or
   unresolved data remains visible WAIT before starting that world.
2. Retain the existing resource transfer/item/renderer/index checks. Host phase2
   readiness and its exact resource SHA must cover the complete selected plan.
3. Negotiate a distinct suite-bound party capability/wire version before adding
   claim/challenge messages. A claimed GUID is untrusted. Preserve readable old
   client rejection; do not change M_JOIN shape silently.
4. Joiner creates its own32-byte join nonce. The native challenge must actually
   arrive on that current game socket from its exact target. `ClientJson` also
   requires the current local native-init/pre-init-plan/resource serial stamp.
   Cold native loading does not consume the later30s proof budget. Native then
   atomically publishes its intent plus the exact received challenge; a party
   packet alone cannot manufacture that socket receipt.
5. Host publishes native-generated pending nonce/serial/deadline and phase2
   resource context under fixed records. It does not contact the party network.
   The long-lived Python worker verifies the admitted Ed25519 owner proof.
6. Native reads the exact one-use ACK, checks its canonical descriptor SHA,
   current live worker/plan/native receipts and endpoint, then calls
   `ConsumeApproved`. Persistent consumption happens **before** native slot
   allocation. Associate the confirmed GUID with its planned slot/lease; never
   fall back to whichever native slot is free first. Retire pending/ACK records.
7. Apply only that owner's reviewed kit through the actor-bound native/GSC
   bridge. Require its real applied receipt before group readiness. Existing
   checkpoint inventory/selection/pose/role preservation must remain intact.
8. Invalidate pending transactions on world/plan/session/endpoint changes and
   retire them on explicit leave/reload. Preserve serials across DLL reloads,
   or explicitly end/rehandshake under a new locally generated native session.

**Liveness adapter still required:** `worker_pid` is an OS PID. Under Linux/Wine,
the Python worker PID is not a Win32 PID and must not be passed blindly to
`OpenProcess`. The helper requires an explicit `alive(pid)` provider plus the
five-second owned-file/monotone heartbeat gate. Actual Linux-native process
liveness or a documented heartbeat lease must be connected before Core uses
this result. No permanently true provider is installed in Core.

Cross-process saved guest ownership still needs stable GUID save provenance and
authenticated saved-owner staging. Current same-session save metadata does not
become cross-process ownership merely because these helpers understand GUIDs.
Dense UF resource capacity, live asset updates, automatic original loadouts,
native Windows/Steam/mixed-platform acceptance and full campaigns remain open.

## Reproduction and evidence

Run the focused portable fixtures:

```sh
g++ -std=c++17 -g -fsanitize=address,undefined -fno-omit-frame-pointer tests/test_party_native_bridge.cpp -o /tmp/coop-party-native-bridge
/tmp/coop-party-native-bridge
python3 -m unittest discover -s tests -p test_party_native_bridge_cpp.py -v
```

The C++/OpenSSL fixture checks actual Python plan/catalog identities and all four
original kit choices, including rejection after recomputing a malicious plan
hash with an invalid enum, inactive family or omitted support/media. It is a
contract fixture, not an authoritative native world resolver.

For actual32-bit MinGW/Wine file/crypto fixtures, use an exclusively owned prefix:

```sh
python3 tools/qa_native_party_bridge_io.py --run run/native-party-io --prefix /absolute/path/to/owned/wine-prefix
```

The fixture never launches a game and never kills a wineserver. It records exact
sources/executable hashes, validates canonical challenge SHA against Python,
and tests atomic replacement/failure, size limits and unsafe path refusal.
Record directories receive a protected current-user write ACL; existing records
writable by an unrelated principal are refused. Actual native Windows hardware
ACL behavior remains a separate platform gate from the Wine fixture.
The first actual POSIX-symlink failure is retained in
`run/party-native-bridge-fixture/before-wine-link-guard-FAIL.json`; the corrected
full run is recorded under `run/party-native-bridge-io-final/`.

## Deutsch

Diese Gegenstelle besteht bisher aus getesteten C++-Hilfsfunktionen und
Vertragstests. Sie ist noch nicht mit dem Spiel-Socket oder der tatsächlichen
Spielerzuweisung verbunden und schaltet keine Ausrüstung frei.

Der vollständige bestätigte Viererplan muss vor dem nativen Missionsstart geprüft
werden. Eine Freigabe bindet Spielerkennung, vorgesehenen Platz, native Sitzung,
Welt, Plan, Ressourcen, Zufallswerte und Fristen. Der Mitspieler muss die konkrete
Challenge selbst am eigenen Spiel-Socket empfangen haben. Wiederholte, veraltete
oder umgebundene Antworten geben keinen Platz frei.

Die eigentliche Integration, der native Welt-/Jahresresolver, automatische
Originalausrüstung und die Anwendung samt echter Bestätigung stehen noch aus.
Datei- und Kryptotests unter Wine sind ausdrücklich kein Nachweis eines fertigen
Coop-Beitritts oder einer durchgespielten Kampagne.
