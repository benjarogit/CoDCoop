# UF equipment presentation integration / Anzeige der UF-Ausrüstungswahl

## Current boundary / Aktuelle Grenze

The launcher source can save one local player's preferences and present a
read-only group projection. Neither feature applies a kit, confirms a player
through a network connection, or authorizes a campaign start. Protocol9 adds
session/world-bound transport; the protocol number does **not** enable an
individual-equipment lobby.

Der Launcher-Quellstand speichert persönliche Wünsche und kann einen
schreibgeschützten Gruppenstand anzeigen. Er übernimmt keine Ausrüstung,
bestätigt keinen Spieler über das Netzwerk und gibt keinen Kampagnenstart frei.
Protokoll9 bindet die Übertragung an Sitzung und Welt; die Protokollnummer
aktiviert **keine** individuelle Ausrüstungslobby.

The State16 native actor-selection bridge is now proven separately with two
and four real UF players, their own cgame weapon selection, checkpoint retention
and real firing. Those probes supply an offline approved resource union and
host-plan fixture. They do not establish a production pre-mission lobby or
resource transport. See the immutable evidence in `HANDOFF-0.6.md`.

Die native Waffenwahl pro Spieler ist mit zwei und vier echten UF-Spielern,
Checkpoint und Schüssen belegt. Diese Tests liefern Ressourcen und Hostplan
vorbereitet aus Testdateien. Eine produktive Lobby oder Ressourcenübertragung
vor Missionsstart ist damit nicht nachgewiesen; Belege stehen in der Übergabe.

## Explicit presentation API / Ausdrückliche Anzeige-Schnittstelle

`Launcher.present_authoritative_roster(snapshot, native_capability)` accepts the
`uf_equipment_roster.public_snapshot(state, catalog)` projection only after a
future trusted session controller has authenticated and validated its source.
The matching display capability is:

```json
{
  "id": "uf.individual_equipment.v1",
  "schema": 1,
  "per_player": true,
  "catalog_sha256": "<canonical catalog SHA256>",
  "roster_snapshot": "uf-equipment-roster-v1"
}
```

A protocol number, a manifest field, or a game log line is insufficient. No
stdout event handler or invented network message is connected to this API.
The future controller must establish the native capability independently and
bind each update to the authenticated session and participant identity.

Eine Protokollnummer, ein Manifest-Feld oder eine Spiel-Logzeile genügt nicht.
Es wurde kein stdout-Ereignis und keine neue Netzwerknachricht angeschlossen.
Der spätere Controller muss die native Fähigkeit unabhängig prüfen und jeden
Stand an die authentifizierte Sitzung und Spieleridentität binden.

## Controller requirements / Anforderungen an den Controller

Before invoking the view, the future controller must verify:

- Registered package/world identity and the exact catalog hash.
- One to four unique engine slots, including the host.
- Kit submissions from their owning player, including when the owner is host.
  A host suggestion must not overwrite another player's selected kit.
- Owner-confirmed readiness for the current immutable revision and plan digest.
- The authoritative contract's exact resource/media union and the separate
  native registration, renderer preload and application checks.
- Automatic authored kits remain unresolved until the actual original rules
  have been evaluated; manual enums must not be used to guess them.

Vor der Anzeige muss der Controller Paket/Welt und Katalog prüfen, ein bis vier
Spieler eindeutig zuordnen, ausschließlich eigene Ausrüstungswahlen übernehmen
und Bestätigungen an den aktuellen Stand sowie dessen Plan-Prüfsumme binden.
Ressourcenprüfung, natives Vorladen und tatsächliche Übernahme bleiben getrennte
Pflichtprüfungen. Automatische Ausrüstung darf nicht aus manuellen Werten
abgeleitet werden.

`tools/uf_equipment_roster_view.py` bounds and validates projection shape, menu
choices, summary consistency and monotonic revisions. Its local consistency key
is **not** authentication or an independent native plan/resource verification.
A valid projection continues to require `runtime_ready: false`; the UI labels
selection confirmation separately from equipment application.

Der Anzeigeadapter prüft Form, Originalauswahl, Zusammenfassungen und
aufsteigende Stände. Er ersetzt keine Authentifizierung und keine native
Plan-/Ressourcenprüfung. Auch ein gültiger Anzeigestand verlangt weiterhin
`runtime_ready: false`. Bestätigte Auswahl und übernommene Ausrüstung werden in
der Oberfläche ausdrücklich unterschieden.

## Refresh and recovery / Aktualisierung und Wiederherstellung

World, kit or membership changes create a new revision and clear all readiness
in the authoritative contract. The view replaces the complete participant list;
it never carries confirmation flags into a new plan. Same-revision changes to
world, members, kits, resource unions or plan identity are rejected.

Rejected data hides the group view while retaining the previous revision guard,
so replaying stale data cannot restore it. Call
`Launcher.clear_authoritative_roster()` for a genuinely new authenticated
session/epoch. Use `unavailable=True` for an interrupted feed within the same
session; this preserves the replay guard. Existing folder changes, session
endings and campaign restarts clear the presentation. No ready/start action is
sent by the read-only dialog.

Welt-, Ausrüstungs- und Gruppenänderungen erhöhen den Stand und löschen alle
Bestätigungen. Ungültige Daten blenden die Übersicht aus, behalten aber die
Prüfung gegen veraltete Stände bei. Nur eine tatsächlich neue authentifizierte
Sitzung setzt diese Prüfung zurück. Die Übersicht versendet weder Bereit- noch
Start-Aktionen und verändert keine persönlichen Einstellungsdateien anderer
Spieler.

## Packaging / Paketierung

Source staging includes the preference adapter, roster-view adapter and catalog
beside `coop/launch-gui.py`. Frozen bundles include the catalog as
`_MEIPASS/uf_equipment_catalog.json`; static imports collect the adapters.
The protocol9 async workers include this graph; their hashes and actual checks are in
`run/worker9-async-handoff.json`. The native lobby capability remains absent,
so bundling the dialog does not grant ready/start or apply anyone's kit.
Die neueren gebündelten Protokoll9-Worker enthalten Katalog und Anzeigeadapter.
Die native Lobby-Freigabe fehlt weiterhin; die enthaltene Oberfläche bestätigt
keinen Missionsstart und übernimmt keine Ausrüstung.
