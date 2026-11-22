# Private native party bridge draft / Privater Entwurf der Spielanbindung

**Status:** Python worker half implemented; native counterpart and an actual
native end-to-end acceptance are pending. IDL `coop-party-native-1` is a private
draft. This is not an equipment-ready capability. Ordinary source launcher
`--party-equipment` still fails closed; no package has been rebuilt for this work.

## Fixed local records

Only these names under the selected, receipt-checked installation's
`coop/party-bridge/` are used. No remote string supplies a local path.

- `party.json`: worker-owned public context/heartbeat, no invitation/private key.
  Contains party session, catalog/package/world/plan SHA, revision, GUID→lobby
  slot membership and confirmations. Includes `plan`: the exact canonical
  `roster.plan()` object (own submitted kits, required weapons/models/support
  and its plan SHA). Hash canonical plan bytes with `plan_sha256` excluded;
  Native must verify that SHA and all catalog/package/world/revision bindings
  and validate original manual choices before pre-G_INIT application. This
  addition is not proof that the pending Native consumer exists. Refreshed at most once per second; expiry
  five seconds. Loss of confirmations writes an explicit waiting record.
- `host-ready.json`: **Native HostCore-produced** phase2 context plus actual full
  bootstrap resources. Context fields match `CONTEXT_FIELDS` in the helper.
  Native must only emit this after its real Game/CG/renderer closure. This is
  shared world/resource/party context: `client_target` is deliberately absent.
  Different peers may target the same Host through LAN/public addresses; each
  target remains bound separately in its exact challenge and local peer intent.
- `host-0.json` to `host-2.json`: **Native HostCore-produced** pending challenges.
  Three pending indices are distinct from the eventual native player slots;
  native slot zero always belongs to the host.
- `client.json`: **local Native JoinerCore-produced**, atomically contains current
  own intent, exact challenge actually received on its own current socket,
  actual received source and local receipt Unix milliseconds. A UDP party-server
  request alone cannot substitute for this record.
- `ack-0.json` to `ack-2.json`: worker-produced atomic one-use approval, echoing
  the exact challenge, canonical challenge SHA and verified owner public key /
  Ed25519 signature. This answers that pending transaction only; it does not
  assert that a kit has been applied or a native slot allocated.

Records have size limits, exact field sets, regular-file/owner checks and reject
symlinks, Windows reparse points and duplicate JSON fields. ACK paths are fixed.

## Challenge identity

`CHALLENGE_FIELDS` in `tools/party_native_bridge.py` is the executable schema.
Required: schema/kind, pending index, unpredictable **32-byte** host nonce and
**32-byte** local client-join nonce (64 lowercase hexadecimal characters each),
native session (16 hex), globally increasing uint64 `challenge_serial` (16 hex),
native world (8 hex), engine `uo`, variant
`united_fronts`, bounded registered map name, echoed client target IPv4 endpoint
and distinct host-observed client endpoint, party session, catalog/package/world
SHA, member GUID, roster revision, plan SHA, resource SHA, creation/expiry Unix
milliseconds. No Steam endpoint is silently converted to IPv4.

The worker checks that every current member confirmed the exact current plan,
that the challenged GUID is an admitted remote owner (never the host), and that
world/catalog/package/revision/plan agree. It compares Native phase2 resources
against actual selected catalog model and registered-weapon requirements.
Automatic original loadouts remain unresolved until a real native resolver exists.

The **resource SHA** hashes exact `asset_bootstrap::EncodeResources` ASCII bytes:
`codcoop-assets-1\n`, sorted/deduplicated lowercase `m\txmodel/name\n` rows, then
complete native-index-ordered `w\t%03u\t0|1\tcanonicalweapon\n` rows. It is not
an archive, package or roster digest. A C++ encoder parity test checks these bytes.

## Actual proof flow

1. Host worker reads the fixed local Native pending challenge and phase2 context.
   It forwards the bounded challenge through its signed party UDP connection.
2. Peer worker validates the signed host/session/party. It **does not sign yet**.
   Its own local JoinerCore record must contain the exact received challenge,
   matching current intent and client-join nonce, own GUID, target/session/world/
   map/plan/resources. The recorded actual socket source must equal its current
   echoed target; NAT does not make Host's observed client endpoint equal this.
3. Peer signs canonical full challenge bytes with its persistent installation key
   and returns `native_proof` over the admitted signed party channel.
4. Host verifies admitted public key/GUID, Ed25519 proof, still-current roster,
   still-present exact Native pending record and real local phase2 resource SHA.
   It writes one atomic ACK. Removing/consuming that ACK never causes retries to
   rewrite it. Three fixed per-pending-index highwater records retain serial,
   descriptor SHA, first monotone observation and one-use state. A new serial
   on the same index must be strictly higher; that Native-issued replacement
   fences the old descriptor without keeping a lifetime nonce list. Lower
   serials on other still-active indices remain valid out of order. There is
   no campaign-total count limit and no manual party restart requirement.
5. **Still required in Native:** compare the ACK against its exact pending tuple,
   enforce its own monotone POD deadline, consume once, then allocate/associate
   the native slot. Apply personal kits only through the later verified native
   owner/roster/resource transaction. Missing worker/context/proof must remain
   visible asynchronous WAIT, never fall back to granting a slot in party mode.

Native must increase its global uint64 `challenge_serial` across worlds,
retries and pending-index reuse within the same native session. It may only
reset the serial epoch with an explicitly new native session; a Python worker
restart does not imply a new native session. Worker fences switch epochs only
after validating the matching trusted local Native ready-context/own client
record, never from a network challenge alone. Native must still consume once,
check its own monotone deadline and retire/remove its consumed pending file.
This policy was coordinated with the Native implementer; actual emission and
ACK consumption remain pending.

Host expiry is at most 30 seconds and the worker retains a non-resettable
monotone first-seen deadline. Peer clocks need not agree with Host UTC: Peer
requires its own recent local Native receipt and own monotone first-seen budget;
Host rechecks Host expiry. Native must independently retain a monotone deadline,
so wall-clock rollback cannot authorize an old pending request.

## Evidence and remaining integration

Tests execute real source CLI workers with genuine sealed tiny installation
fixtures, actual signed UDP traffic and actual fixed-file reads/atomic ACK writes.
The Native file producer in these tests is explicitly a **test harness**, not
CoD/CoD UO. Tests cover no-intent and wrong received-challenge/source/client-nonce
refusal, then valid signed proof, one-use consume, stale plan/resources, expiry,
unknown/host owner rejection, new nonce/serial recovery, safe paths, 300 actual
worker approvals in the same session with stable party identity, 1,100 bounded
ledger cycles, independent out-of-order indices, expired-serial/clock rollback
rejection and C++ resource
encoding parity. No native end-to-end, game slot allocation, native kit
application or frozen-worker acceptance is claimed by these tests.

## Deutsch

Der Python-Teil des privaten Entwurfs ist umgesetzt und mit echten
Launcher-Prozessen, UDP-Nachrichten und atomaren lokalen Dateien getestet.
Die Gegenstelle, welche die Native-Dateien in diesen Tests erzeugt, ist bewusst
ein **Testprogramm**. Sie ist kein Nachweis eines erfolgreichen Spielbeitritts.

Der Host darf erst nach lokaler nativer Ressourcenbereitschaft eine konkrete
Challenge anfragen. Der Mitspieler unterschreibt nur mit eigenem lokalem
Beitrittsauftrag **und genau der am eigenen Spiel-Socket empfangenen Challenge**.
Spielerkennung, Sitzung, Welt, Mission, Paket/Katalog, Gruppenrevision, Plan,
Ressourcen und beide Zufallswerte müssen zusammenpassen. Eine gefälschte Anfrage
mit der Spielerkennung eines anderen Teilnehmers reicht nicht aus.

Die bisherige Gesamtgrenze von 256 Vorgängen wurde entfernt. Drei feste
Datensätze merken sich die steigende native Seriennummer je offenem Platz.
Neue, nativ ausgestellte Seriennummern ersetzen alte sicher; verspätete
Vorgänge bleiben gesperrt. Gruppenidentität und Spielerplätze bleiben auch
über viele Missionen und Checkpoints bestehen. Die native Gegenseite muss
ihre eigene einmalige Verarbeitung und monotone Frist weiterhin prüfen.

Der Host-Worker erstellt danach eine einmalige Antwort unter einem festen
lokalen Dateinamen. Das Spiel muss diese Antwort noch gegen seinen offenen
Vorgang und seine eigene monotone Frist prüfen, verbrauchen und den tatsächlichen
Spielerplatz zuordnen. Die Spielfreigabe und Anwendung eigener Ausrüstung bleiben
bis zur nachgewiesenen nativen Integration gesperrt. Es gibt weiterhin keine
neue Paketveröffentlichung und keine behauptete vollständige Coop-Abnahme.
