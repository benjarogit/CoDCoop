# Launcher party transport / Launcher-Gruppentransport

## English

The **United Fronts → Group lobby** controls start an actual separate UDP worker
(default port 28961). The host chooses an advertised IPv4 address, registered
mission, difficulty and optional original campaign faction; participants paste a
private invitation. For LAN play use the host's LAN address instead of 127.0.0.1.
Mission/package/catalog mismatches are rejected. The full installation receipt
is checked before the worker opens a party.

Each installation has an Ed25519 identity outside the game directory, under the
user's CoDCoop preferences directory. Its GUID derives from its public key.
Atomic owner-private storage retains the key and an increasing worker epoch;
repair/replacing suite files and restarting the native game do not replace it.
The independent lobby worker stays open while owned native processes restart.
Restarting a peer lobby worker can rejoin the same host invitation and slot.
Restarting the host lobby itself creates a new invitation; host migration is not
implemented. Invitations are bearer admission secrets: share privately. They are
kept in owner-private temporary files, never placed in game saves or status logs.
Signatures authenticate messages; the LAN packet contents are not encrypted.

The host assigns at most four slots, owns the world/revision, and cannot submit
another participant's kit or confirmation. Every player submits their own saved
four-slot preference and confirms the current plan. Membership/world/kit changes
invalidate all confirmations. Original automatic kits remain distinct; their
native mission-specific resources still need resolution. Smoke planning needs
an explicit original host campaign/faction; it is not inferred from the caller's
personal kit. Until the native world is available this is a proposed host world,
not evidence that those original engine CVars have been applied.

Signed UDP messages bind wire schema, session nonce, catalog SHA256, package
SHA256, persistent public identity, worker epoch and monotone sequence. Unknown
identities cannot issue actions. Retries have deduplicated request IDs; conflicting
IDs, replay/reordered packets, stale roster revisions, invalid signatures and
other-owner edits are rejected. Heartbeats produce a visible wait while retaining
slots on temporary loss. Explicit Leave sends an own-member removal request;
if it cannot be delivered, the host visibly retains the disconnected slot.
Host Cancel is a signed party cancellation. No network field is a shell command,
executable, game path or native console command. Datagrams and decompressed JSON
have separate fixed bounds; receive work and request deduplication are bounded.

**Native boundary:** choice confirmation is not game readiness. The public
roster's `runtime_ready` stays false. The launcher disables **Start with party
equipment** and the supervisor's `--party-equipment` option fails closed.
State19/resource bootstrap v2 and compiled feature16 currently do not bind GUID,
engine owner slot, personal kit, roster/plan digest and native resource ACK as one
transaction. A future integration must verify that complete tuple on host and
peers, including exact session/map/engine/world, before applying kits or starting
a mission. No protocol number, network boolean or preference file grants this.
Ordinary campaign launching keeps its existing equipment behavior.

Source acceptance: real 2-/4-process UDP traffic, controlled loss/reordering,
peer worker restart with stable GUID/slot, stale/forged/other-owner/conflicting
requests, readiness invalidation, and actual two Qt-created source workers.
This does not certify native kit application, Internet NAT traversal, Steam
transport or any frozen bundle. No package was rebuilt for this milestone.

## Deutsch

**United Fronts → Gruppen-Lobby** startet einen eigenen echten UDP-Prozess
(Standardport 28961). Der Host wählt LAN-Adresse, registrierte Mission,
Schwierigkeit und gegebenenfalls die originale Kampagnenfraktion. Mitspieler
fügen eine privat weitergegebene Einladung ein. Die vollständige Installation
wird vorher geprüft. Persönliche Grafikoptionen und Spielstände bleiben lokal.

Jede Installation behält ihre signierte Spieleridentität außerhalb des
Spielordners. Der Lobby-Prozess bleibt bei Neustarts des eigentlichen Spiels
bestehen. Auch ein neu gestarteter Mitspieler-Lobbyprozess kann mit demselben
Schlüssel wieder seinen bisherigen Gruppenplatz erreichen. Ein Neustart der
Host-Lobby erzeugt eine neue Einladung; Hostmigration ist nicht umgesetzt.
Einladungen sind vertrauliche Zugangsschlüssel. Nachrichten werden signiert,
ihr Inhalt im LAN jedoch nicht verschlüsselt.

Jeder Spieler sendet und bestätigt ausschließlich seine eigene Ausrüstung. Der
Host verwaltet Mission, Weltregeln und bis zu vier Plätze. Änderungen an Gruppe,
Mission oder Ausrüstung verwerfen sämtliche Bestätigungen. Automatische
Originalausrüstung bleibt ein eigener Modus. Die Luftangriff-Planung verwendet
eine ausdrücklich angegebene Host-Kampagne, niemals die persönliche
Waffenfamilie eines Mitspielers. Ohne native Welt ist das eine geplante Auswahl,
kein Nachweis bereits gesetzter Spielregeln.

Signatur, Sitzung, Paket-/Katalogprüfsummen, Spieleridentität, Neustartzähler und
Nachrichtenfolge werden geprüft. Alte, gefälschte, widersprüchliche und fremde
Spieleraktionen werden verworfen. Wiederholungen und Heartbeats ermöglichen
Wiederbeitritt und sichtbare Wartezustände. Verlassen entfernt den eigenen Platz,
soweit die Nachricht den Host erreicht; Abbrechen beendet die Host-Gruppe.

**Noch offene Spielanbindung:** Eine bestätigte Auswahl bedeutet keine
Startbereitschaft des Spiels. Der Ausrüstungsstart bleibt sichtbar deaktiviert;
auch der Supervisor lehnt ihn ab. Die native Bootstrap-v2-Schnittstelle verbindet
noch nicht Spieler-GUID, tatsächlichen Engine-Platz, Ausrüstung, Gruppenplan und
Ressourcenbestätigung. Erst nach dieser geprüften Verknüpfung darf die Auswahl
im Spiel angewendet werden. Die bisherigen normalen Spielstarts behalten ihre
vorhandenen Ausrüstungsregeln. Es wurde kein neues Paket gebaut oder veröffentlicht.
