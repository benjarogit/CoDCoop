# CoDCoop 0.6 handoff / Übergabe

Date / Datum: 2026-11-22. Development branch: `feat/0.6.0-coop-suite`.
Starting point: `801dfd4` (published v0.5.4 assets are unchanged).
Local source checkpoints: `4a6d36f`, `3288c23`, `7b1428f` (WIP, not pushed or released).

## Latest state / Neuester Stand — protocol9, dev.6

This section supersedes the historical checkpoints below. / Dieser Abschnitt
ersetzt die älteren Standangaben weiter unten. Development is unfinished;
published v0.5.4 binaries have not been replaced.

### Current checkpoint / Aktueller Zwischenstand

#### November22 addendum / Ergänzung 22. November

This addendum supersedes pending statements below. Nothing has been published.
/ Diese Ergänzung ersetzt ältere Offen-Angaben unten. Nichts wurde veröffentlicht.

- **M0 Noville diagnosis checkpoint / M0-Diagnose Noville:** local commits
  `3cd492e` (owned-process write watchpoint), `bf2dbb8` (QA all-weapon-media
  path and four-receipt gate) and `67fe3f3` (module+RVA resolution). Nothing
  pushed or published. The watchpoint fixture passes 9/9 under Wine
  (`watch.exe` sha256
  `7ddc8a2baaa37f4d3526f43f8de2d204734eeb007b92f647084cc17a7de9d71c`,
  `fixture.exe` sha256
  `04b80b011d0d07563a65d9903c19fb3d99fa403f0197c8ffd8e88a222c191c5e`) and
  never selects a game. `./build.sh` passes; `python3 -m unittest discover -s
  tests` reports 378 tests OK with 46 environment skips (`run/unit-m0.log`).
  `CODCOOP_QA_ALL_WEAPON_MEDIA` registers every existing native definition
  before GSC on both sides; it requires QA, deferral, UO and the United Fronts
  variant and grants no inventory. The Noville experiment with that flag is
  kept in `run/qa-noville-m1-awm1*`; no result is claimed before it completes.
  / Drei lokale Commits, nichts veröffentlicht; Fixture 9/9, Build und
  Regressionstests grün.
- **M1 planned kit union / M1 geplante Kit-Union:** local commits `237b4c3`
  (plan-scoped union) and `1802cab` (trace pid, `--min-nodes`). The four-player
  Noville run `run/qa-noville-m1-union7` PASSes with
  `--experimental-gmi-loader --experimental-plan-union-media
  --experimental-borrow-trees`: the host declares 15 planned definitions
  (14 kit weapons plus the map-registered `thompson28`), the export stays at
  347 models/119 weapons, all three joiners verify the strict native
  index/name/registered mapping, and the four fresh kits pass. No `MT_AllocIndex`
  failure occurs with borrowed trees. `MatchWeapons`, registration guards,
  ID order and capacity are unchanged; the union and the map-scoped extra are
  QA-only, and catalog enum numbers are resolved to native definition names.
  This is not native Windows/Steam acceptance and not a production registry fix.
  / Zwei lokale Commits, nichts veröffentlicht. Noville-Vier-Spieler-Lauf
  `union7` besteht mit geplanter Union und geliehenen Bäumen; Host deklariert
  15 Definitions, Export bleibt 347/119, alle drei Joiner bestehen das strikte
  Mapping, vier frische Kits bestehen, kein `MT_AllocIndex`-Fehler. QA-only,
  keine Produktionslösung und keine Windows/Steam-Abnahme.
- **M2 watch negative / M2-Watch-Negativ:** local commit `9e39e60` adds
  `--duration` so the departure fits the watchpoint cap. In
  `run/qa-noville-m1-watch3` all three joiners attach and arm on the shared
  988-node definition (`definition+4`, expected 988), the four-player scenario
  PASSes, and every watcher reports `hit:false` with a clean detach after the
  process exits. No game thread writes that field during a clean departure in
  the borrow configuration. The earlier `0xff000000` corruption
  (`run/qa-cod1-four/history/1795329148842541172/453995-native-crash-stop.json`,
  entity341, 988 nodes) therefore predates or bypasses the borrowed-tree path;
  it remains an own-free/ownership defect, not a native write. This is a
  negative observation, not a safety proof for other leave paths (reload,
  disconnect/rejoin) and not a production fix.
  / Lokaler Commit `9e39e60`; Watch `watch3` meldet für alle drei Joiner
  `hit:false` auf `definition+4` (988 Nodes) bei sauberem PASS. Kein nativer
  Schreibzugriff; die frühere Korruption bleibt ein Defekt des eigenen
  Free-/Ownership-Pfads. Kein Beweis für Reload/Disconnect und keine
  Produktionslösung.
- **M3 reload/rejoin and writer / M3 Reload/Rejoin und Writer:** local commit
  `5cbf05a` adds the native checkpoint roundtrip to the four-role scenario and
  re-arms the tree watch per map generation. `run/qa-noville-m1-reload2`
  PASSes: real host `savegame`/`loadgame`, all three joiners rejoin the restored
  world, move 105.9/209.1/250.8 units, no allocator failure and a clean
  shutdown. `run/qa-noville-m1-reload-watch1` PASSes and identifies the writer:
  on generation 1 all three joiners hit `definition+4` with `0xFFFFFFFF`,
  written by the engine `memset` at RVA `0x2C460` (store IP RVA `0x2C49B`);
  generation 2 has no hit. The engine poisons the shared XAnim definition
  during map teardown. An own tree freed after that teardown reads the poisoned
  node count, which is the earlier `0xff000000` free-entry corruption. Borrow
  avoids it because no own tree survives the teardown. This is a causal
  diagnosis, not a production fix; promoting borrowing still needs native
  Windows/Steam and further map coverage.
  / Commit `5cbf05a`; Reload `reload2` besteht (drei Joiner zurück, Bewegung,
  kein Alloc-Fehler, sauberer Shutdown). Watch `reload-watch1` findet den
  Writer: Engine-`memset` RVA `0x2C460` schreibt `0xFFFFFFFF` auf
  `definition+4` beim Map-Teardown (Generation 1), Generation 2 ohne Treffer.
  Eigener Baum nach dem Teardown liest die vergiftete Node-Zahl → frühere
  `free-entry`-Korruption. Borrow vermeidet das. Kausale Diagnose, keine
  Produktionslösung; Windows/Steam und weitere Karten fehlen.
- **M4 stale-tree free guard / M4 Guard für veraltete Bäume:** the own-tree free
  path now records the node count at creation and skips the free when the
  shared definition reports a different count (the teardown `0xff` fill).
  `run/qa-noville-m1-reload3` PASSes with borrow (185.4/146.1/223.7 units after
  the reload, no guard hit, no allocator failure). `run/qa-brecourt-m4-guard1`
  PASSes without borrow (165.5/181.1/208.3 units, reload, no allocator failure);
  the guard did not trigger there because Brecourt does not reach the Noville
  teardown path. The exact Noville non-borrow path is still blocked by the
  7918-byte join allocation, so the guard is a conservative crash guard, not a
  proven production fix, and it deliberately leaks a stale block until the pool
  reset instead of freeing with a poisoned size.
  / Eigener Free-Pfad merkt sich die Node-Zahl beim Erzeugen und überspringt den
  Free, wenn die geteilte Definition eine andere Zahl meldet (Teardown-`0xff`).
  `reload3` besteht mit Borrow, `brecourt-m4-guard1` ohne Borrow; der Guard
  wurde dort nicht ausgelöst, weil Brecourt den Noville-Teardown-Pfad nicht
  erreicht. Der exakte Noville-Ohne-Borrow-Pfad bleibt durch die
  7918-Byte-Join-Allokation blockiert. Konservativer Crash-Guard, kein
  bewiesener Produktionsfix; veralteter Block wird bis zum Pool-Reset bewusst
  nicht freigegeben.
- **M5 production native-tree adoption / M5 Produktions-Übernahme nativer Bäume:**
  UO joiners now reuse the engine's own animation tree instead of freeing the
  DObj and allocating a duplicate. Ownership is captured before the host
  attaches (while the entity type is still intact), validated against the
  native owner slot and tracked in the shared native-reference table, so
  `JoinerAdvanceAnims`, leave and free paths treat it as Game-owned. No
  `CODCOOP_QA_DEFER_MODELS`/borrow gate; the QA borrow remains available.
  `run/qa-noville-m5-adopt5` PASSes four-player Noville without borrow with the
  native checkpoint reload: 68/49/49 adoptions, all joiners rejoin and move
  (144.7/212.2/269.0 units), no `MT_AllocIndex` failure, no guard hit and a
  clean shutdown. Remaining own trees are limited to entities without a
  pre-attach native owner (late-spawned tanks/humans, `owner=0`); the M4 guard
  stays the backstop for those. Evidence secured in
  `run/qa-noville-m5-adopt5/evidence/`. Native Windows/Steam and further map
  coverage remain open.
  / UO-Joiner übernehmen jetzt den nativen Animationsbaum des Motors, statt den
  DObj zu leeren und einen zweiten Baum zu allokieren. Die Ownership wird vor
  dem Host-Attach erfasst (Entity-Typ noch intakt), gegen den nativen
  Owner-Slot geprüft und in der gemeinsamen Native-Referenztabelle geführt;
  Advance-, Leave- und Free-Pfad behandeln sie als Game-eigen. Kein
  QA-Deferred-/Borrow-Gate nötig, QA-Borrow bleibt verfügbar. `adopt5` besteht
  vier Spieler Noville ohne Borrow inklusive Checkpoint-Reload (68/49/49
  Übernahmen, Bewegung 144.7/212.2/269.0, kein Alloc-Fehler, kein
  Guard-Treffer, sauberer Shutdown). Verbleibende Eigenbäume nur für Entities
  ohne vorab erfassten Native-Owner (spät gespawnte Panzer/Menschen,
  `owner=0`); der M4-Guard bleibt Backstop. Windows/Steam und weitere Karten
  offen.
- **M6 join recovery after a load stall / M6 Rejoin nach einem Ladestock:**
  Foy exposed a reconnect loop. A joiner whose verified native world was already
  prepared answered the timeout-recovery `M_MAP` through `QueueJoinerMap`, but
  `BootInterceptMap` returned `true` before the recovery state was cleared, so
  the joiner neither reloaded nor rejoined; the host then freed the slot after
  8 s of silence and the joiner repeated the loop every second. `QueueJoinerMap`
  now ends recovery before the boot interception and, when the prepared native
  world is current (`BootNativeWorldReady`, one source for that condition),
  unfreezes the local server and rejoins that world without a reload — the same
  attach path the first join uses, including `M_WORLD_READY`. Negatives:
  `run/qa-foy-m5-adopt1` (no fix, host drops slot 1) and
  `run/qa-foy-m5-adopt2` (recovery ends, but `frozen` still blocked
  `JoinerHijack`, so `joined` never became true). The QA liveness gate measured a
  single 2-second window and reported a false stall while three Foy clients were
  still loading; `qa.wait_liveness` keeps the strict predicate (host advancing,
  every remote active with an advancing command clock) and allows a bounded
  20-second window instead. `run/qa-foy-m5-adopt4` then caught a harness bug in
  that helper (it indexed a transiently incomplete connect state instead of
  waiting for it); the helper now treats an incomplete state as "not yet".
  `run/qa-foy-m5-adopt5` passed connect and liveness and exposed the next
  Foy-specific fact: a peer that reaches the host before its own map is ready is
  dropped during that load (host slot timeout 8 s) and rejoins into the
  `PRESERVED` disposition of the same native identity. The fixture accepts
  `FRESH` or `PRESERVED` for the same identity and still proves the current-epoch
  kit through `coop_qa_kit_applied_N` plus the concrete per-slot inventory check.
  / Foy hat eine Reconnect-Schleife aufgedeckt. Ein Joiner, dessen verifizierte
  native Welt bereits vorbereitet war, beantwortete das Recovery-`M_MAP` über
  `QueueJoinerMap`, aber `BootInterceptMap` gab `true` zurück, bevor der
  Recovery-Zustand gelöscht war: kein Reload, kein Rejoin, Host gibt den Slot
  nach 8 s Stille frei, Schleife im Sekundentakt. `QueueJoinerMap` beendet die
  Recovery jetzt vor der Boot-Interception und nutzt bei aktueller vorbereiteter
  Welt (`BootNativeWorldReady`) den normalen Attach-Pfad ohne Reload, inklusive
  `M_WORLD_READY`. Negative: `qa-foy-m5-adopt1` (ohne Fix, Host gibt Slot 1
  frei) und `qa-foy-m5-adopt2` (Recovery endet, aber `frozen` blockierte
  `JoinerHijack`, `joined` wurde nie wahr). Das Liveness-Gate maß zusätzlich nur
  ein starres 2-s-Fenster und meldete einen falschen Stall, während drei
  Foy-Clients noch luden; `qa.wait_liveness` behält die strenge Bedingung und
  erlaubt ein begrenztes 20-s-Fenster. `qa-foy-m5-adopt5` passierte Connect und
  Liveness und zeigte den nächsten Foy-Effekt: Ein Peer, der den Host erreicht,
  bevor seine eigene Karte fertig ist, wird während dieses Ladens gedroppt
  (Host-Slot-Timeout 8 s) und kommt danach in der `PRESERVED`-Disposition
  derselben nativen Identität zurück. Die Fixture akzeptiert `FRESH` oder
  `PRESERVED` bei gleicher Identität und belegt das Kit der aktuellen Epoche
  weiterhin über `coop_qa_kit_applied_N` plus die konkrete Inventarprüfung je
  Slot.
- **M7 Foy own-tree ceiling, capture merge / M7 Foy-Eigenbaum-Grenze und Capture-Zusammenführung:**
  `run/qa-foy-m5-adopt6` reached the checkpoint reload and failed inside the
  joiner with `MT_AllocIndex: failed allocation of 45 bytes for script usage`.
  The pool was not exhausted by adoptions (`active 16`) but by own trees
  (`own_trees` 189/91/77); join1 carried the most because its recovery rejoin
  re-ran `QACaptureNativeTrees`, which cleared the table and therefore lost the
  ownership captured before the first attach, so every soldier it met again
  became an own tree. `QACaptureNativeTrees` now keeps each owner whose slot
  still points at the captured tree in the same world generation and only drops
  what the slot no longer confirms (a real reload still clears everything
  through the generation change). This is the same diagnosis upstream fixes in
  `1435a93` by moving own trees to the heap; M9 closes the pool ceiling by
  moving joiner own trees and host body trees to the heap, so Foy is the map
  that needed them.
  / `run/qa-foy-m5-adopt6` erreichte den Checkpoint-Reload und scheiterte im
  Joiner mit `MT_AllocIndex: failed allocation of 45 bytes for script usage`.
  Der Pool war nicht durch Übernahmen (`active 16`), sondern durch Eigenbäume
  erschöpft (`own_trees` 189/91/77); join1 hatte die meisten, weil sein
  Recovery-Rejoin `QACaptureNativeTrees` erneut ausführte, die Tabelle leerte
  und damit die vor dem ersten Attach erfasste Ownership verlor — jeder erneut
  getroffene Soldat wurde zum Eigenbaum. `QACaptureNativeTrees` behält jetzt
  jeden Owner, dessen Slot in derselben Weltgeneration noch auf den erfassten
  Baum zeigt, und verwirft nur, was der Slot nicht mehr bestätigt (ein echter
  Reload leert weiterhin alles über den Generationswechsel). Es ist dieselbe
  Diagnose, die Upstream in `1435a93` mit Heap-Bäumen behebt; M9 schließt die
  Pool-Grenze mit Heap-Bäumen für Joiner-Eigenbäume und Host-Körper, Foy war
  die Karte, die sie braucht.
- **M8 Brecourt four-player pass / M8 Brecourt mit vier Spielern:**
  `run/qa-brecourt-m5-adopt1` PASSes on the first attempt with the same flags as
  Foy: four players, no borrow, `active 15` adoptions per joiner, 11 own trees
  each, no `MT_AllocIndex` failure, no guard hit, checkpoint reload restored the
  world for all three joiners (movement 106.2/50.3/170.0 after the reload,
  268.6/177.7/120.3 in the observation phase) and every process shut down
  cleanly. It ran the pre-M7 binary (`build/codcoop_core.dll` 677376 B), so the
  capture merge and the heap trees are not part of this pass.
  / `run/qa-brecourt-m5-adopt1` besteht im ersten Versuch mit denselben Flags wie
  Foy: vier Spieler, kein Borrow, `active 15` Übernahmen je Joiner, je 11
  Eigenbäume, kein `MT_AllocIndex`-Fehler, kein Guard-Treffer, der
  Checkpoint-Reload stellt die Welt für alle drei Joiner wieder her (Bewegung
  106,2/50,3/170,0 nach dem Reload, 268,6/177,7/120,3 in der Beobachtungsphase)
  und alle Prozesse fahren sauber herunter. Er lief mit der Binärdatei von vor
  M7 (`build/codcoop_core.dll` 677376 B), Capture-Merge und Heap-Bäume sind also
  nicht Teil dieses Laufs.
- **M9 Foy four-player pass, keep-alive in the packet pump / M9 Foy-Vier-Spieler-PASS, Keep-Alive im Paket-Pump:**
  `run/qa-foy-m9-keepalive1` PASSes four-player Foy with the full 0.6 path:
  production native-tree adoption, heap own trees, heap host bodies and the
  upstream ports. Every gate passes (real connect, liveness, four
  FRESH/PRESERVED kits, movement, own-ammo fire, authoritative body scope,
  MG/bazooka and pistol/binocular selection, native checkpoint reload, clean
  shutdown). 32 adoptions per joiner (16 per attach) and 7 own trees each after
  the reload; no `MT_AllocIndex` failure and no `ERROR:` line in any of the four
  consoles. Host bodies: 19 created, 11 replaced; the `9494 bytes` checkpoint
  failure needed heap host bodies, not only joiner trees. Checkpoint reload:
  joiners free 43/38/34 old trees, rejoin at 09:53:05-08 with restored
  pose/health/inventory and then move 306.7/239.7/279.9 units (observation
  110.5/178.2/378.3); `QACaptureNativeTrees` logs `0 kept from the previous
  capture`, so the reload really rebuilt the world. The decisive liveness fix:
  Foy's native load leaves the joiner's cgame at 0 frames/s for ~10-20 s while
  `M_PING` was sent only from `Coop_FrozenFrame`; the host freed the slot after
  8 s, the joiner recovered and the loop repeated (`qa-foy-m8-heapbody1`: drops
  at 09:41:25/32, `host silent for 15005 ms`, liveness gate failed). The ping now
  also runs from `Coop_GetPacket`, the packet pump that keeps running while the
  client frame is stopped; in m9 no joiner logs `host silent` and all three stay
  attached through the loads. Unit tests 382 OK / 46 skips; build 679936 B.
  Evidence `run/qa-foy-m9-keepalive1/evidence/` (8.3 MB), runtime copies deleted.
  The same build then passed the two earlier maps: `run/qa-noville-m10-keepalive1`
  (44/46/47 adoptions, 17 old trees per joiner, reload movement
  98.9/203.0/157.6, 0 `failed allocation`, 0 `ERROR:`, no `host silent`) and
  `run/qa-brecourt-m10-keepalive1` (30 adoptions each, 11 old trees, reload
  movement 126.3/132.1/130.7, same clean result).
  / `run/qa-foy-m9-keepalive1` besteht vier Spieler auf Foy mit dem vollen
  0.6-Pfad: Produktions-Übernahme nativer Bäume, Heap-Eigenbäume,
  Heap-Host-Körper und die Upstream-Ports. Alle Gates bestehen (echter Connect,
  Liveness, vier FRESH/PRESERVED-Kits, Bewegung, eigener Munitionsverbrauch,
  autoritativer Körperumfang, MG/Bazooka- und Pistole/Fernglas-Auswahl,
  nativer Checkpoint-Reload, sauberer Shutdown). 32 Übernahmen je Joiner
  (16 pro Attach), je 7 Eigenbäume nach dem Reload; kein `MT_AllocIndex`-Fehler
  und keine `ERROR:`-Zeile in einer der vier Konsolen. Host-Körper: 19 erzeugt,
  11 ersetzt; der `9494-Byte`-Checkpoint-Fehler brauchte Heap-Host-Körper, nicht
  nur Joiner-Bäume. Checkpoint-Reload: Joiner geben 43/38/34 alte Bäume frei,
  kommen 09:53:05-08 mit Pose/Leben/Inventar zurück und bewegen sich danach
  306,7/239,7/279,9 Einheiten (Beobachtung 110,5/178,2/378,3);
  `QACaptureNativeTrees` meldet `0 kept from the previous capture`, der Reload
  hat die Welt also wirklich neu aufgebaut. Entscheidender Liveness-Fix: Foys
  nativer Ladevorgang lässt das cgame des Joiners ~10-20 s bei 0 Bildern/s,
  während `M_PING` nur aus `Coop_FrozenFrame` kam; der Host gab den Slot nach
  8 s frei, der Joiner erholte sich, die Schleife wiederholte sich
  (`qa-foy-m8-heapbody1`: Freigaben 09:41:25/32, `host silent for 15005 ms`,
  Liveness-Gate scheiterte). Der Ping läuft jetzt auch aus `Coop_GetPacket`,
  dem Paket-Pump, der weiterläuft, während der Client-Frame steht; in m9 meldet
  kein Joiner `host silent` und alle drei bleiben durch die Ladevorgänge
  verbunden. Unit-Tests 382 OK / 46 Skips; Build 679936 B. Evidenz
  `run/qa-foy-m9-keepalive1/evidence/` (8,3 MB), Laufzeitkopien gelöscht.
  Derselbe Build bestand danach die beiden früheren Karten:
  `run/qa-noville-m10-keepalive1` (44/46/47 Übernahmen, 17 alte Bäume je
  Joiner, Reload-Bewegung 98,9/203,0/157,6, 0 `failed allocation`, 0 `ERROR:`,
  kein `host silent`) und `run/qa-brecourt-m10-keepalive1` (je 30 Übernahmen,
  11 alte Bäume, Reload-Bewegung 126,3/132,1/130,7, gleiches sauberes
  Ergebnis).
- **M11 campaign coverage, bastogne1 rejoin renderer / M11 Kampagnenabdeckung, Bastogne1-Renderer beim Rejoin:**
  `run/qa-bastogne1-m11-coverage1` FAILs at the first movement after the native
  checkpoint reload, although everything before it passes: four kits, own ammo,
  authoritative bodies, MG/bazooka and pistol/binoculars selection, 5.4 MB of
  observations and screenshots. The reload itself works (save 19:12:56, load
  19:13:02, the three saved ghosts disconnected 19:13:04, all three joiners back
  PRESERVED at 19:13:40-50) and the host keeps receiving their commands
  (`ctrl=729` per five seconds). The joiners are simply still catching up:
  `snaps=0` for the first five seconds after the rejoin and only 2 frames/s, so
  `+forward` cannot reach the host inside `move_remote`'s fixed ten-second
  window. bastogne1 is the widest map so far (303 models) and its rejoin takes
  about 40 s instead of the few seconds on Foy. The fixture now waits for
  `restored_world_rendered`: every joiner must advance `snapshot_num` and
  `snapshot_time` beyond its rejoin state before input is injected. That is a
  stronger precondition instead of a wider movement window; a joiner that never
  renders still fails, with a precise reason. `run/qa-bastogne1-m12-render1`
  then passed that precondition and failed the same gate for a second, unrelated
  reason: the host recorded `forward=127` for the peer and the player moved 0.18
  units. The restored pose is exactly where the pre-reload walk had stopped —
  the spawn faces an obstacle and the 160-unit walk ended against it — so
  `+forward` cannot move again. The fixture now probes the four walk directions
  (`move_with_room`) and keeps the strict per-direction oracle (`forward>0` or
  `back<0`, an advanced command clock and more than five units); only a peer
  that moves in none of the four fails, with the list of blocked keys. The same
  m12 run also shows the `52dd2bc` module-load port working before any session:
  `modulo de juego cargado en 20000000` and `checkpoint: carga tambien a los
  remotos guardados` at 05:15:57, minutes before the host connected.
  / `run/qa-bastogne1-m11-coverage1` scheitert an der ersten Bewegung nach dem
  nativen Checkpoint-Reload, obwohl alles davor besteht: vier Kits, eigener
  Munitionsverbrauch, autoritative Körper, MG/Bazooka- und
  Pistole/Fernglas-Auswahl, 5,4 MB Beobachtungen und Screenshots. Der Reload
  selbst funktioniert (Speichern 19:12:56, Laden 19:13:02, die drei
  gespeicherten Geister 19:13:04 getrennt, alle drei Joiner 19:13:40-50 als
  PRESERVED zurück) und der Host empfängt ihre Kommandos weiter (`ctrl=729` pro
  fünf Sekunden). Die Joiner holen nur noch auf: `snaps=0` in den ersten fünf
  Sekunden nach dem Rejoin und nur 2 Bilder/s, deshalb erreicht `+forward` den
  Host nicht im festen Zehn-Sekunden-Fenster von `move_remote`. Bastogne1 ist
  die bisher größte Karte (303 Modelle) und der Rejoin dauert rund 40 s statt
  weniger Sekunden wie auf Foy. Die Fixture wartet jetzt auf
  `restored_world_rendered`: jeder Joiner muss `snapshot_num` und
  `snapshot_time` gegenüber seinem Rejoin-Stand erhöhen, bevor Eingaben
  injiziert werden. Das ist eine strengere Vorbedingung statt eines weiteren
  Bewegungsfensters; ein Joiner, der nie rendert, scheitert weiterhin, mit
  präzisem Grund. `run/qa-bastogne1-m12-render1` besteht diese Vorbedingung
  danach und scheitert am selben Gate aus einem zweiten, unabhängigen Grund:
  Der Host verzeichnet `forward=127` für den Peer, und der Spieler bewegt sich
  0,18 Einheiten. Die wiederhergestellte Pose ist genau dort, wo der Lauf vor
  dem Reload endete — der Spawn zeigt auf ein Hindernis, der 160-Einheiten-Lauf
  stieß dagegen —, deshalb bewegt `+forward` nichts mehr. Die Fixture probiert
  jetzt die vier Laufrichtungen (`move_with_room`) und behält das strenge Orakel
  je Richtung (`forward>0` bzw. `back<0`, fortgeschrittene Kommandouhr und mehr
  als fünf Einheiten); nur ein Peer, der in keiner der vier Richtungen läuft,
  scheitert, mit der Liste der blockierten Tasten. Derselbe m12-Lauf zeigt auch
  den `52dd2bc`-Modul-Port vor jeder Sitzung:
  `modulo de juego cargado en 20000000` und
  `checkpoint: carga tambien a los remotos guardados` um 05:15:57, Minuten vor
  dem Verbinden des Hosts.
- **M12 campaign sample coverage / M12 Kampagnen-Stichproben:** `run/qa-bastogne1-m13-wall1`
  PASSes four-player bastogne1 with the widened fixture: 14 native-tree
  adoptions per joiner, 3 own trees each, 19 host bodies, initial movement
  166.6/166.7/130.4 and post-reload movement 156.6/187.8/124.0 through `+back`,
  0 `failed allocation`, 0 `ERROR:` line, no `host silent` event and a clean
  shutdown. Evidence in `run/qa-bastogne1-m13-wall1/evidence/`; runtime copies
  deleted. The per-chapter sample program is US `carride` (truck intro), desert
  `afrika2`, British `arnhem`/`pegasusnight`, Soviet `pavlov`/`redsquare`,
  snow/urban `bastogne1` (done) and vehicles `bizerte` (see below), each with
  the four-role fixture; CoD1, UO and SP Improved get one smoke each. The
  coverage status is recorded per map, not as a campaign playthrough claim.
  `run/qa-bizerte-m14-sample1` is the first documented content exception:
  bizerte loads only `character_german_dakA/C/E/F` (273 exported models, no
  allied character model; its GSC has the `character\...::precache()` lines
  commented out), so `HostCreateBody` reports `cuerpo 0: el nivel no cargo
  modelos de soldado aliado` and no coop body can exist on either side.
  Movement (156.2/164.9/244.6), kits, ammo and command clocks all pass; only
  the body gate fails, and it fails because the level has no model to build a
  body from, not because of a coop defect. Per the agreed policy (per-map rules
  instead of silently relaxed gates) bizerte stays a named limitation and
  `afrika2`, which precaches `character\airborne1f_garand` and
  `character\airborne1w_garand`, is the desert sample instead.
  / `run/qa-bastogne1-m13-wall1` besteht Bastogne1 mit vier Spielern und der
  erweiterten Fixture: 14 native Baum-Übernahmen je Joiner, je 3 Eigenbäume,
  19 Host-Körper, Anfangsbewegung 166,6/166,7/130,4 und Bewegung nach dem Reload
  156,6/187,8/124,0 über `+back`, 0 `failed allocation`, 0 `ERROR:`-Zeile, kein
  `host silent`, sauberer Shutdown. Evidenz in
  `run/qa-bastogne1-m13-wall1/evidence/`; Laufzeitkopien gelöscht. Das
  Stichprobenprogramm je Kapitel ist US `carride` (Truck-Intro), Wüste
  `afrika2`, Britisch `arnhem`/`pegasusnight`, Sowjet `pavlov`/`redsquare`,
  Schnee/Stadt `bastogne1` (erledigt) und Fahrzeuge `bizerte` (siehe unten),
  jeweils mit der Vier-Rollen-Fixture; CoD1, UO und SP Improved bekommen je
  einen Smoke. Der Abdeckungsstand wird pro Karte festgehalten, nicht als
  behaupteter Kampagnendurchlauf. `run/qa-bizerte-m14-sample1` ist die erste
  dokumentierte Inhaltsausnahme: Bizerte lädt nur
  `character_german_dakA/C/E/F` (273 exportierte Modelle, kein alliiertes
  Spielermodell; die `character\...::precache()`-Zeilen im GSC sind
  auskommentiert), deshalb meldet `HostCreateBody`
  `cuerpo 0: el nivel no cargo modelos de soldado aliado`, und auf keiner Seite
  kann ein Coop-Körper entstehen. Bewegung (156,2/164,9/244,6), Kits, Munition
  und Kommandouhren bestehen; nur das Körper-Gate scheitert, und zwar weil dem
  Level das Modell fehlt, nicht wegen eines Coop-Fehlers. Nach der vereinbarten
  Regel (Pro-Karte-Regeln statt still aufgeweichter Gates) bleibt Bizerte eine
  benannte Einschränkung, und `afrika2`, das
  `character\airborne1f_garand` und `character\airborne1w_garand` vorlädt, ist
  stattdessen die Wüstenstichprobe.
- **U1 upstream comparison TheTiranix/CoDCoop / U1 Upstream-Abgleich:**
  `upstream/master` = `52dd2bc` (fetched read-only), merge base `21eae10`;
  upstream has 8 commits we do not, we have 78 it does not. Verdicts:
  `1435a93` heap own trees — **PORT (highest value)**: identical diagnosis
  (pool exhausted after the Bastogne jeep), it replaces the two
  `g::XAnimCreateTree` call sites in `src/core.cpp` with `calloc`/`free` and
  keeps `FreeTreeInfos` behind an `XAnimLoaded` check; our M4 guard stays in
  front of that call because it is the proven backstop. `3386c4f` crash/error
  logs — **ADOPT** (`src/crashlog.h` does not exist here; touches `loader.cpp`,
  `cod2.cpp`, installers, isolated from the coop paths). `c1da93f` coop save
  load + host-only triggers — **PORT SELECTIVELY** (`Hook_LoadGame`,
  `SaveLocalStates`, `Hook_Trigger`, `RemoteActivator`, `PlaceJoined`,
  `InJoinGrace`, `MoveRemote` are all absent; we already have our own `HookLoad`
  with the mis-match skip and ghost cleanup, so the 451-line commit does not
  cherry-pick). `fa87f10` leave vehicles at the host + revive protection —
  **PORT SELECTIVELY** (35 lines, independent of adoption). `c827372` host
  weapon in vehicles / late models / body interpolation — **EVALUATE** (its
  late-model part is superseded by `BootPeerModelAllowed` and the plan-scoped
  union media). `1ab6391` smoother joiner animations — **ADOPT** (5 lines,
  frozen joiner frametime). `ab6cd25` joiners load host models —
  **REJECT AS-IS**: it disables `r_errorOnConflicts` globally for the attach,
  which would bypass our plan-scoped model policy; only the strictness knob is
  reusable if a plan-approved model is genuinely missing. `52dd2bc` solo save
  load — **EVALUATE** (our `HostDropGhosts()` has no `wait` parameter and no
  non-coop path yet). Order: `1435a93` → `3386c4f` → `1ab6391` → the
  `fa87f10`/`c1da93f` fragments, each with unit tests plus a four-player run.
  / `upstream/master` = `52dd2bc` (nur lesend geholt), Merge-Basis `21eae10`;
  Upstream hat 8 Commits, die wir nicht haben, wir 78, die es nicht hat.
  Der Abgleich ist ein expliziter Schritt: `tools/upstream_check.sh` holt
  `upstream/master` lesend und listet die fehlenden Commits samt Dateistatistik
  (`--log` zeigt die Betreffzeilen). Es gibt keinen Automatismus und keinen
  Hintergrunddienst dafuer; Orqen hat fuer CoDCoop keinen Adapter und beobachtet
  keinen Upstream, die Entscheidung bleibt beim nativen Harness.
  Bewertung: `1435a93` Heap-Eigenbäume — **PORTIEREN (höchster Nutzen)**:
  gleiche Diagnose (Pool nach dem Bastogne-Jeep erschöpft), ersetzt die beiden
  `g::XAnimCreateTree`-Aufrufstellen in `src/core.cpp` durch `calloc`/`free` und
  legt `FreeTreeInfos` hinter eine `XAnimLoaded`-Prüfung; unser M4-Guard bleibt
  davor, weil er der bewiesene Backstop ist. `3386c4f` Crash-/Fehlerlogs —
  **ÜBERNEHMEN** (`src/crashlog.h` fehlt hier; betrifft `loader.cpp`,
  `cod2.cpp`, Installer, unabhängig von den Coop-Pfaden). `c1da93f`
  Coop-Save-Laden + Trigger nur vom Host — **SELEKTIV PORTIEREN**
  (`Hook_LoadGame`, `SaveLocalStates`, `Hook_Trigger`, `RemoteActivator`,
  `PlaceJoined`, `InJoinGrace`, `MoveRemote` fehlen alle; unser eigener
  `HookLoad` mit Mis-match-Skip und Ghost-Cleanup existiert schon, daher kein
  Cherry-Pick der 451 Zeilen). `fa87f10` Aussteigen am Host +
  Revive-Schutz — **SELEKTIV PORTIEREN** (35 Zeilen, unabhängig von der
  Übernahme). `c827372` Host-Waffe im Fahrzeug / späte Modelle / Körper-
  Interpolation — **PRÜFEN** (der Modell-Teil wird von `BootPeerModelAllowed`
  und den plan-gebundenen Union-Medien abgelöst). `1ab6391` weichere
  Joiner-Animationen — **ÜBERNEHMEN** (5 Zeilen, Frametime des eingefrorenen
  Joiners). `ab6cd25` Joiner laden Host-Modelle — **NICHT SO ÜBERNEHMEN**: es
  schaltet `r_errorOnConflicts` für den Attach global ab und würde unsere
  plan-gebundene Modellpolitik umgehen; nur der Strictness-Schalter ist
  wiederverwendbar, falls ein plan-freigegebenes Modell wirklich fehlt.
  `52dd2bc` Solo-Save-Laden — **PRÜFEN** (unser `HostDropGhosts()` hat keinen
  `wait`-Parameter und keinen Nicht-Coop-Pfad). Reihenfolge: `1435a93` →
  `3386c4f` → `1ab6391` → die Fragmente aus `fa87f10`/`c1da93f`, jeweils mit
  Unit-Tests plus Vier-Spieler-Lauf.
- **U1 update after M9 / U1-Nachtrag nach M9:** landed with `./build.sh` and the
  382-test suite (46 environment skips): `1435a93` joiner own trees **and**
  host body trees on the heap (`CreateOwnTree`/`FreeOwnTree`, `calloc`/`free`;
  `TreeBytes` uses the per-game `TREE_INFO`; host-body ledger records `heap=1`
  and frees heap entries by pointer, script-pool entries still through
  `MT_FreeIndex`); `1ab6391` `sv_animFrametime` from the client clock advance;
  `c827372` body interpolation (`HostAnimateBodies(dt)` only on server frames)
  and the vehicle loadout (`hostArmed` plus `GiveHostLoadout`); `fa87f10` 3 s
  revive grace (`FL_NOTARGET`), per-player damage log and the vehicle exit at
  the host's spot; `52dd2bc` the saved-remote patch applied on the game-module
  load notification (`LdrRegisterDllNotification`) instead of only when hosting,
  plus the solo ghost drop without a coop socket; and part of `3386c4f`
  (`CodeAddress` for every module including UO below `0x10000000`,
  build version from `git describe`, previous session as `*_previous.log`).
  One deliberate divergence from `52dd2bc`: our ghost drop disconnects a saved
  remote player immediately instead of waiting 8 s for it to reclaim the seat,
  because a rejoining peer rebuilds its body from the preserved inventory; the
  module-load patch is in place but loading a coop save while playing alone has
  not been exercised in this environment yet. Still open: the full `3386c4f`
  `crashlog.h` refactor and the selective `c1da93f` fragments (native
  trigger/activator placement, join grace). `ab6cd25` stays rejected as-is. The
  next `tools/upstream_check.sh` run decides whether anything newer than
  `52dd2bc` changes these verdicts.
  / Mit `./build.sh` und der 382-Test-Suite (46 Umgebungs-Skips) umgesetzt:
  `1435a93` Joiner-Eigenbäume **und** Host-Körperbäume im Heap
  (`CreateOwnTree`/`FreeOwnTree`, `calloc`/`free`; `TreeBytes` nutzt das
  spielspezifische `TREE_INFO`; das Host-Körper-Ledger speichert `heap=1` und
  gibt Heap-Einträge per Zeiger frei, Script-Pool-Einträge weiter über
  `MT_FreeIndex`); `1ab6391` `sv_animFrametime` aus dem Clientuhr-Fortschritt;
  `c827372` Körper-Interpolation (`HostAnimateBodies(dt)` nur in
  Server-Frames) und Fahrzeug-Loadout (`hostArmed` plus `GiveHostLoadout`);
  `fa87f10` 3-s-Revive-Grace (`FL_NOTARGET`), Schadenslog je Spieler und
  Aussteigen am Host; `52dd2bc` der Remoten-Patch schon beim Lade-Aviso des
  Spielmoduls (`LdrRegisterDllNotification`) statt erst beim Hosten, dazu der
  Solo-Ghost-Drop ohne Coop-Socket; und ein Teil von `3386c4f` (`CodeAddress`
  für jedes Modul, auch UO unter `0x10000000`, Build-Version aus
  `git describe`, voriger Lauf als `*_previous.log`). Eine bewusste Abweichung
  von `52dd2bc`: Unser Ghost-Drop trennt einen gespeicherten Remote-Spieler
  sofort statt 8 s auf seine Rückkehr zu warten, weil ein zurückkehrender Peer
  seinen Körper aus dem erhaltenen Inventar neu aufbaut; der Modul-Patch ist
  gesetzt, das Laden eines Coop-Spielstands im Solo-Betrieb wurde in dieser
  Umgebung aber noch nicht ausgeführt. Offen: der volle
  `3386c4f`-`crashlog.h`-Umbau und die selektiven `c1da93f`-Fragmente (native
  Trigger-/Aktivierer-Platzierung, Join-Grace). `ab6cd25` bleibt so abgelehnt.
  Der nächste `tools/upstream_check.sh`-Lauf entscheidet, ob etwas nach
  `52dd2bc` diese Bewertung ändert.
- **Latest worker checkpoint / Neuester Worker-Stand:** local source `277fc47`
  fixes actual Windows/Wine atomic-replace sharing failures and physical-link
  rejection. Fresh immutable worker source graph
  `8f7e3a4d000abc755813a3af44dddee9243b23c1a3e27b159c0d2e035c0e5de5`
  at `run/worker9-dev6-win-io/` passes strict embedded-provenance/crypto probes,
  tiny synthetic suite seal/check/prepare, legacy protocol rejection and personal
  file preservation. Linux signed-worker suite:11 passed; Windows/Wine:10 passed,
  one unavailable compiler case skipped. Actual300 challenge/ACK cycles and a
  separate abrupt four-party worker restart preserve the required identity/plan
  semantics. Executable hashes: Linux
  `63619c9fc00950e69af67dbc287f2c95aeb3fbca8126274e0f1b5c68918d8623`,
  Windows `df6030662bcda46acf5f65107aa8265b4cc517f30c84e9d1ad27a395f77e647c`.
  Exact handoff SHA256 `f46541fba4cb1be66ca828fd2149669c1d5f5fa0f4480db4fae8658f3b8d2687`:
  `run/worker9-dev6-win-io/handoff.json`. These are real frozen workers but NOT
  native game owner/kit binding, full suite setup/AppImage or physical Windows.
  Older statements about the missing fresh-worker positive are superseded.
- **Current source regression / Aktuelle Quellregression:** after the Windows
  file-exchange fix and new UF observer fixtures, `/usr/bin/python3 -m unittest
  discover -s tests` discovers361 cases:325 pass,36 environment-dependent native
  cases skip (`run/unit-after-worker-io.log`,68.578s). The ordinary `./build.sh`
  passes (`run/build-after-worker-io.log`), build-path Core
  `f69052402e428b3f004fd9f47e9c05b2c0a4d431a9728414c5c3a56fa7cdb086`.
  This includes the experimental visible-body first-use and QA observer source;
  it does not replace the exact6c726 native-tested installer candidate above.
- **UF four-owner investigation / UF-Vier-Spieler-Untersuchung:** local Core
  checkpoints `2ff61c1` and `17c362b` keep the work QA-only. Actual four-instance
  Brecourt with experimental defer, default255 slots and no borrowed trees
  receives four distinct kits, matching own CG and real independent movement.
  The first06cf body test fails on missing late frozen-SV model mappings;
  archive `run/qa-cod1-four/history/1795319400630017697/`, proof
  `3969fafbba80af65bb35b0e491d2df442b13106e99a2e7cda7a9af79d01deaf9`.
  The232d shadow prototype then exposes an overly strict case comparison:
  all player bodies are rejected on `gear_us_helmet` versus native
  `gear_US_helmet`. That FAIL remains at `1795319617626340645/`, proof
  `aa8b179ba45a5a6df144afae4aa3b149242457c705ba94a3206193db447ac577`.
  A read-only255-slot diagnostic further shows native cache `gear_us_moody`
  at the same helmet CS ID; matching CS names alone do not prove correct media.
  Diagnostic a8bb stopped after the first witnessed WAIT, explicitly NOT PASS,
  archive `1795319859267421478/`. Candidate
  `bb02a762ee0fd4bcfd88fe9e916b27f35fd606c9bc9ec1b137a78ceda0d73422`
  at `run/uf-live-shadow-casefold/` uses native ASCII case identity and verifies/
  repairs the approved same-ID native cache. ASan/UBSan and strict compiler
  tests pass; actual four-player retest is pending. Every tested body component
  must match actual XModel, negative ID, native client CS, frozen SV CS AND
  native model cache. First-person own-body absence is recorded separately;
  it never excuses a missing other-player body. No saved-game, native signed
  equipment binding, special-weapon deployment or campaign acceptance is claimed.
- **Brecourt four-role PASS / Vier-Rollen-Nachweis Brecourt:** exactbb02 above
  passes the strengthened fresh-only four-instance scenario with native255 IDs,
  no borrowed trees and no offline peer media/plan injection. The real initial
  resource-bootstrap v2 path precedes each peer's native attach. Actual arrival
  order is Host0/join1→2/join2→1/join3→3 and all owner checks use those real slots.
  Independent input moves all three remotes; real four-owner firing changes
  clips30/5/20/8→29/4/15/7. Normal primary and pistol selection displays MG/
  bazooka and pistol/binocular assets. Every tested body component matches
  actual XModel, negative ID, actual client CS, frozen SV CS and native cache.
  All four quit0. Archive `run/qa-cod1-four/history/1795320305470444441/`;
  proof SHA256 `ca9d08ad51602cb40f0fe0aeff9b65ce33c05b42e996ed6300bacff0ebc24705`.
  Root spot-checks owner2 bazooka and owner0 binocular images; the campaign QA
  observer separately reviews all8 captures. No deployment/airstrike, save/load,
  signed-GUID binding or mission-completion claim. Noville is the next native
  gate. Setup I/O overlapped initial Brecourt loading, so no performance claim;
  subsequent dense-map runs are coordinated with the installer tests.
- **Noville FAIL / Noville fehlgeschlagen:** bb02's four-instance case is NOT
  accepted. Joiner1 crashes at native45fd50 while freeing tree95d400; exact
  archive `run/qa-cod1-four/history/1795320581657023310/`, proof SHA256
  `f3d8a087904e92299bf36a452a43c95f9c77bd7aa157314f29c6d3300aaea6fa`.
  A separate symbolic rebuild has a byte-identical whole.text section to bb02
  and attributes returnRVA0xbcdc to non-borrow JoinerFreeDObj→XAnimFreeTree
  after FreeTreeInfos. Read-only findings: `run/noville-tree-free-re/FINDINGS.md`
  and `run/bb02-caller-attribution/FINDINGS.md`. Native DObj detach does NOT
  itself free the tree block; a double-free cause is not established. The free
  size derived from the definition is invalid. Root's trace-only candidate
  `9f86261d3248808acd755080e8699093e31492d5cdef14378f72dfe0235edf23`
  at `run/uf-tree-free-trace/` logs create/free/detach/sync/info boundaries
  without changing free semantics; causal native rerun is pending. Its initial
  notify diagnostic reads a pool-relative field16 bytes before the actual
  native notify handle; do not interpret that field as an SL handle.
  Independently, Noville AND Foy use `_load_gmi.gsc`, bypassing the classic
  loader's kit/common-init adapter. Old Noville has no valid distinct-kit
  receipt and repeats fallback equipment. A separately pinned QA-only GMI
  transformation is default OFF and preserves the old failing payload byte
  for byte; it is not a native fix or production integration yet. Foy4 was
  deliberately not started after the Noville failure.
- **Trace retry / Wiederholung mit Protokollierung:** 9f's unchanged Noville
  payload does not reproduce the native crash, but FAILs four-owner connectivity.
  Only join3 attaches and produces complete normal create/detach/info/free
  sequences; join1 and join2 fail strict native registered-weapon comparison
  (Springfield98 / Thompson28 index111 extra local registration). No four-kit
  or crash-fix acceptance. Archive
  `run/qa-cod1-four/history/1795328672428275680/`, proof SHA
  `0020a28400818cc7e753be3236be5889cfdfa0b7c50139bf5ed994cbfe992c1f`.
  Independent bounded diagnostics:
  `run/noville9f-bootstrap-diagnostic/1795328608465252512/FINDINGS.md`.
  Hundreds of thousands of loading messages were a description→ACK→description
  feedback loop, NOT repeated native loads: each failed peer has one GAME_INIT.
  Source now replies immediately only to a genuinely advanced ACK phase, keeps
  periodic retries, suppresses failed-peer ACKs and preserves the concrete
  failure message. Registration/identity checks remain strict. The new flow
  fixture passes10000 duplicate-ACK rounds with ASan/UBSan; native feedback-fix
  runtime verification is pending. The trace notify offset is corrected in
  current source; immutable9f evidence retains its documented caveat.
- **Audited policy checkpoint / Geprüfter Richtlinienstand:** local `7da0480`
  adds the still-unwired58248-byte first-use POD policy and CI fixture. Root's
  independent strict ASan/UBSan run passes. Frozen source/evidence:
  `run/first-use-helper-freeze/23523195884bf5a369c9589b357b97a8a5d78ae373d8286391929071b968b538/proof.json`.
  Actual pinned Game9fd366 PE fingerprints for all20 callers/publication tail
  and the32-bit Windows/Wine standalone policy pass. Host physical IDs and
  temporary Peer local-load IDs are separate authorities; adoption requires
  the native detach barrier plus actual client/shadow/cache evidence. Native
  definition count is independently observed, not inferred from a partial
  table. Integration sequence: `docs/first-use-resources.md`. Core does not
  include this policy yet; resource-save manifest codec work remains separate.
- **Save codec checkpoint / Speicher-Codec:** local `1342d24` adds only the
  bounded approval-manifest codec and its CI fixture, independently reviewed
  with actual OpenSSL ASan/UBSan. Final frozen header SHA
  `ff5369d77c2df1b38c8ba23aac4eeb00d95b6d62c9cea65a465b9546bfa9e504`;
  evidence `run/resource-approval-save/freeze/ff5369d77c2df1b38c8ba23aac4eeb00d95b6d62c9cea65a465b9546bfa9e504/proof.json`.
  Same canonical bytes pass actual Windows CryptoAPI/Wine. Native save IO,
  old SVG palette migration, registry reconstruction and stable-GUID ownership
  are still unimplemented; `.coopowners` V2 is unchanged.
- **Private installer milestone / Private Installationspakete:** completed
  package tests do NOT close gameplay gates. Linux AppImage
  `run/private-dev6-state24-277/Install-CoD-Coop-0.6.0-dev.6-state24-private-Linux-x86_64.AppImage`
  SHA `7c4d9789bb2ba5ce3db6467f80e1ca2e61cca702cef110f7bf1b6f549069eabd`;
  Windows delivery ZIP
  `run/private-dev6-state24-rollback2/Install-CoD-Coop-0.6.0-dev.6-state24-private-rollback2-Windows.zip`
  SHA `46200124449df891e6160edd02d2a8636d4c115403890d8a4cde2e1ab18c2320`.
  Both retain exact native-tested6c726 runtime and graph8f workers, with NO new
  experimental Core or QA overlays. Actual offline install/check/corruption/
  repair/update/public rollback and GUI checks pass; CURRENT post-configure
  cfg/save edits are retained on both platforms. New guarded Windows Setup
  inner SHA `5baa2f373d3c115a943fc82ea52b10d6ee47b241b9be198456385c20be5d4bb9`
  corresponds to the seven-file source overlay checkpointed as `8b9399e`,
  not original277 Setup. Schema2 guards reject changed/unowned runtime/backups,
  preserve personal files, restore pre-rollback state on injected failure and
  reject legacy journals. Old0cd low-level restore rejects new schema2;
  installer README now points at guarded Setup. Installed cross-OS and EN/DE
  gameplay fingerprints match. Exact handoff
  `run/private-dev6-state24-rollback2/milestone-handoff.json`, SHA
  `c6271073ac2c6cd9682038097b8a3d0a5d0027dad81dc6639d6826676a4fbd48`.
  All installer processes are idle; no files were uploaded or published.
- **Latest source checks / Neueste Quellprüfung:** `./build.sh` passes
  (`run/build-after-bootstrap-feedback.log`); Python discovery has376 cases,
  330 passed and46 native opt-in skips (`run/unit-after-native-diagnostics.log`,
  44.618s). Explicit native installer/codec fixtures above remain separate
  positive evidence. GMI/default-output and source patch/oracle tests pass;
  nothing here certifies a complete campaign or native Windows hardware.
- **UF resource blocker / UF-Ressourcenblockade:** clean normal255-slot universal
  startup passes Brecourt250CS but fails Foy and Noville with native model overflow.
  Selected-host-only diagnostic startup passes Foy249 and Noville252; the union
  of the four chosen American roles would need259/263 respectively, so reducing
  universal helpers alone is insufficient. No selected-host test certifies the
  user's required four individual kits. A QA-only six-pure-precache-caller defer
  prototype starts all three maps at normal255, imports no old model ledger,
  retains every approved renderer asset and leaves native guards unchanged.
  Core `6ffc8fd0fd0eea1a5dedde03e47d925468122d659716b417087bba97fea8eb1a`
  at `run/uf-observer-epoch-prototype/`; evidence and exact archives are in
  `docs/campaign-compatibility.md`. This remains experimental: visible body/gun
  first use, real four-owner kit union, current peer model mappings, cumulative
  mission usage and checkpoint asset persistence still require proof and proper
  production integration. Do not enable the QA environment flag in a release.
- **Real paused UF world / Tatsächlich pausierte UF-Welt:** source-pinned,
  epoch-bound read-only diagnostics observe actual native ordered campaign/
  climate/year decisions while the original journal holds world time at300ms.
  Normal Start resumes the world. Fresh initialization was proved on the three
  maps above, with selected-only diagnostic scope where universal startup fails.
  Runtime-ready remains false. BSP-derived candidates independently match the
  compact three-map witnesses; this is not proof for all122 maps or saved games.

- **Current native candidate / Aktueller nativer Kandidat:** State24/protocol9,
  compiled APIs63. `LOCALIZED_BANNERS=32` requires the owned EN/DE text bank;
  it is not an individual-kit capability. Exact Core
  `6c726d798f862361d0079f317185330d98c89648c8daa1ae497a3f295e139781`
  at `run/banner-feature63-state24/` passes actual UO+YAP/LAA0a mixed EN/DE
  down/progress/revived UI and a separate strict Downed checkpoint/pose/vitals/
  native revival round. Both pairs quit0. Earlier Coreeea APIs31 passes all four
  engine/language directions; its initial long German hints were visually
  clipped despite native lookup success, so those old results have explicit
  failed visual-review supplements. Current owned ENbank
  `bea6ef3a24f586631569408f51efc3f9d857ee948951fd4a8b4ef3ef909c96c2`
  and DEbank `908ce0bdfdd78a95a736b23de87b56c19e72be5256f7db3fb269ec7618659741`
  respect the verified40-byte draw limit; both remain within37 text bytes after
  substituting player digits. Native screenshots/buffers confirm full hints,
  Latin1 glyphs, colors, progress and player numbers without UNLOCALIZED.
  See latest exact archives in `docs/campaign-compatibility.md`. Dev.6 mandatory
  locale installation/repair/rollback and mask63 validation pass separate source
  and actual Wine checker/installer tests. Full frozen-package rebuilding is
  pending; manual QA banks do not certify base-game mixed languages.
- **Dev.6 verification / Prüfung:** complete build passes, ordinary build-path
  Core `080d5f52aa7954400a8db5487b8535777327b3e6c8aacbe182d45638b4593d33`.
  Exact native acceptance remains on6c726 above (output-path ImageBase differs).
  Of346 discovered Python cases,312 pass and34 native opt-in cases are skipped:
  `run/unit-dev6-feature63-full.log`. Pure native-party transactions also
  pass ASan/UBSan. Locale installation has separate143 focused regressions,
  eight final bounded-file checks, a real tiny offline backend install/repair/
  public rollback, five actual feature63/legacy checker cases and Windows
  installer locale/retirement groups under Wine. Exact handoff:
  `run/dev6-locale-handoff.json`; manifest
  `fc9b44ee12e67315b11df0ec0290ccfc77d697bf639877e7aeff2ea6ca9022d7`.
  The GUI-worker source graph and crypto dependencies are pinned and tested in
  isolation, but a fresh frozen-worker positive test is not yet claimed.
- **Previous suite contract / Vorheriger Paketvertrag:** `0.6.0-dev.5`, protocol9,
  required feature mask31. Resource bootstrap is now mandatory. The unchanged
  native checker rejects protocol9 DLLs advertising only15; actual staging of
  the old602 and bac binaries fails before creating output.95 focused Python
  checks and17 opted-in Wine checker cases pass (one historical case skipped).
  Exact handoff: `run/dev5-mask31-handoff.json`. Existing private dev.4
  installers are historical artifacts and have not been rebuilt or published.
- **Merged bootstrap / Zusammengeführte Ressourcenübertragung:** State23 Core
  `6c42a85fd4e56fd9d19fcb896b1363f22b19a377399dc2397ddf6ee2ae671212`
  retains State22 explicit save roles and transfers the hash-checked resource
  contract before the first target GAME_INIT. Both actual CoD1 and UO+YAP
  guest-Downed checkpoint/rejoin/normal revival cases pass. Evidence:
  `run/merged-bootstrap-state23/evidence/`. A native DObj detach/sync barrier
  fixes the independently reproduced model-ID mapping mismatch; Game-owned
  allocation ownership remains intact. Full UF future-resource closure remains
  open; these are targeted proofs, not campaign completion.
- **Four-owner prone regression / Liegerichtungsfehler mit vier Spielern:**
  the strict mixed Alive/Alive1HP/Downed/Alive checkpoint test exposed native
  prone direction and pitch values overwritten during reconnect. Native Game
  and CGame cap view yaw at85 degrees from that separate direction, explaining
  the measured post-load error. Read-only RE: `run/prone-direction-re/FINDINGS.md`.
  State24 candidate `6bac8ba85474835f26790a7154ec5efb23fd9d8b7dce4588b4ee8aa2bf3c2e7c`
  in `run/prone-basis-state24/` preserves precisely those three finite native
  fields and restores them after native prone-entry. Six focused C++ fixtures
  pass ASan/UBSan. Strict CoD1 mixed-four-owner acceptance passes: all saved
  position/view deltas0, PS/entity health600/1/1/450, explicit roles[1,1,2,1],
  all three native prone fields equal in HostPS/current own CG snapshot and
  prediction. Actual peer3 revives downed peer2 through the normal3-second Use
  action with Host beyond revive range. All four then move and quit0. Archive:
  `run/qa-cod1-four/history/mixed-four-role-State24-CoD1-proneBasis-strictsavedPose-thirdPeerRevive-PASS-1795312133933698964`.
  The equivalent UO+YAP four-instance test also passes with all view/position
  deltas0, native prone basis[34.18396,0,0] identical across Host and own CG,
  peer3's normal revival, all four subsequent real inputs and clean exits0:
  `run/qa-cod1-four/history/mixed-four-role-State24-UO-YAP-proneBasis-strictsavedPose-thirdPeerRevive-PASS-1795312273472664884`.
  Saving in the narrow downed-before-native-prone-entry interval is not covered.
  Training is
  explicitly unarmed; this proof does not certify all four distinct weapons.
  Older failed samples remain retained; no relaxed view-angle oracle.
- **State24/dev.5 source verification / Quellprüfung dieses Zwischenstands:**288 Python cases,
  264 passed and24 native opt-in skips, `run/unit-state24-dev5.log`.
  Focused inventory, pose, vitals, saved provenance, resource-bootstrap lifetime
  and native mapping-barrier C++ fixtures pass ASan/UBSan. The two new bootstrap
  fixtures are now included in the engine-build CI job.
  The complete `./build.sh` also passes, with ordinary `build/` Core
  `e790895ad738280e549b6ad86dc4146a894b4e62c7e890f7dea081d893075e98`.
  Its source is identical to the tested6bac snapshot; MinGW's output-path-derived
  automatic ImageBase differs (0x6d000000 versus0x66980000), so these binary
  hashes are deliberately not conflated. The native evidence uses exact6bac.
- **Individual party equipment / Individuelle Gruppenausrüstung:** signed real
  UDP lobby transport and the bounded local Python bridge have their own
  positive/rejection tests. A shared Host-ready context supports parallel
  players with different addresses, while each exact socket challenge, local
  intent and source binding remains mandatory. Native producer/consumer and
  pre-mission kit binding are unfinished; actual kit launch remains disabled.
- **Narrow save boundary / Enges Speicherzeitfenster:** a QA-only read-only
  FS open/close observer was added after the State24 checkpoint commit. The
  real queued damage+save experiment already had native prone flag1 at both
  boundaries; it does not reproduce Downed-before-prone. No load acceptance
  is inferred. Exact observer Core
  `f10d9f8658946ca1f77c218fdf2c025f316b406c8ffa490e0ae9706da1974133`,
  archive `run/qa-cod1-four/history/immediate-save-f10d-CoD1-queued-native-damage-save-sourceALREADYprone-NOTREPRODUCED-1795312530513939384`.
- **World-scoped movement / Bewegung mit Weltbindung:** source inspection of
  process-global catch-up trail/timers and vehicle retry pointers led to a real
  reproduced defect: after Training→Brecourt, the stationary new-world Host was
  near[2323,-2499,8], but the remote was caught up to old Training coordinates
  [4259,-4450,-93]. Baseline observer Coref10d fails the strict stationary-world
  oracle. Candidate Core `b8c40e6e3841232ec3421ff678964e01c2bfc1c95c03f8181b86315d12ffa5ae`
  under `run/motion-scope-state24/` fences coordinates/retries by native server
  ID/VM and Coop session/world, and clears per-peer timers/retries on lease,
  spawn ticket or active-state changes. The unchanged no-stale oracle passes;
  extended actual CoD1 AND UO+YAP checks also require real peer input, no catch-up
  while the new Host is stationary, then normal current-world catch-up after
  actual Host movement and further peer input. Both games quit cleanly.
  Evidence: `run/qa-motion-epoch/` and its bounded `history/`; no mission
  completion or vehicle-specific runtime acceptance is inferred. The initial
  UO raw-copy attempt timed out at YAP's LAA prompt; only the reviewed owned-copy
  LAA0a executable is used for the passing UO case. Live files are unchanged.
- **Localization investigation resolved / Textfehler geklärt:** the actual UO
  downed screenshot exposed `UNLOCALIZED(...)`. The newer namespace/bank and
  native key/literal encoding proofs above close that targeted center-message
  defect without suppressing global warnings. Other console/debug text and
  full base-game language compatibility are separate scopes.

- **Latest parent — State22 / sidecarV2:** Core
  `fc01f8d89702af7bbf47240a0f01b49e3001adcc9b3468b567214104509e1905`
  under `run/saved-role-prototype/` adds explicit Alive/Downed ownership roles
  to the hash-bound `.coopowners` file. The SVG remains unchanged. Exact legacy
  V1 prefixes still decode without inventing a missing role. Native saved HP1
  alone never establishes Downed. Loaded Host state waits safely for a known
  returning saved teammate; normal revival starts a fresh3-second action.
  Actual CoD1 and UO+YAP guest-Downed, Host-Downed and standingAlive1HP cases
  all pass pose/camera/PS+entity health/actor eligibility, normal revival or
  ordinary post-load movement and both clean exits. Exact SVG+sidecar retained.
  Evidence under `run/qa-cod1-four/history/`:
  `downed-owner-fc01-CoD1-actuallethal-nativeCP-HP1-prone-normalUseRevive-PASS-1795310281883047058`,
  `downed-owner-fc01-UO-YAP-actuallethal-nativeCP-HP1-prone-normalUseRevive-PASS-1795310338602983641`,
  `role-fc01-CoD1-actualHOSTdown-nativeCP-GUESTnormalUseRevive-PASS-1795310559443487904`,
  `role-fc01-UO-YAP-actualHOSTdown-nativeCP-GUESTnormalUseRevive-PASS-1795310661000967671`,
  `role-fc01-CoD1-standingALIVE1HP-native599damage-nativeCP-normalinput-PASS-1795310600299534519`,
  `role-fc01-UO-YAP-standingALIVE1HP-native599damage-nativeCP-normalinput-PASS-1795310716483178300`.
  Newer mixed/four-owner role coverage, vehicles/scripted roles, cross-process
  stable-GUID resume and full campaigns are separate outstanding gates.
  The private production-bootstrap baseline3855 is now ready for logical merge;
  its State19 must become **State23** while retaining these State22 fields.

- **Latest native checkpoint — State21:** Core
  `d982970ed3bac9ef70b4068a593b044ade6656f95105dfe1bb2f5956b469caf5`
  under `run/saved-vitals-native-prototype/` preserves the returning owner's
  plain standing pose and coherent native PS/entity health/maxhealth after
  ClientConnect/Begin. The original SVG already contained the right values;
  the reconnect lifecycle discarded them. View restoration waits for a current
  native command so delta angles use the returning client's actual raw basis.
  Scope: alive, standing, unlinked, view-unlocked players; vehicle/scripted,
  crouched/prone/downed save roles remain open. Ownership/world transitions
  clear receipts, and no complete PS, script or link pointers are copied.
  Actual CoD1 and UO+YAP tests apply nonfatal native damage600→550, then save/load:
  guest PS/entity health stays550, Host600 remains unchanged, both owners'
  position and all view angles have delta0, and ammo/slots/active Game+ownCG
  choice and no-repeat equipment receipts still match. Both games quit0.
  Exact evidence under `run/qa-cod1-four/history/`:
  `pathfinderd982-CoD1-actualDamage50-strictPOSE-VITALS-nativeCP-PASS-1795308507691535724`
  and `pathfinderd982-UO-YAP-actualDamage50-strictPOSE-VITALS-nativeCP-PASS-1795308585953522895`.
  Earlier4861 preserves pose but heals550→600;1805 proves loaded health550 before
  cleanup. Those negative results remain archived. No complete checkpoint or
  campaign certification is inferred from this ordinary-player fixture.
- **Generated script precedence:** canonical mission overlay is now
  `zzzz_coop_triggers.pk3`, before both QA `zzzz_coop_campaign.pk3` and staged
  `zzzz_codcoop.pk3` under native ASCII-uppercase sorting. UF's actual old
  variant layer shadowed Pathfinder's new remote Use adapter. Renaming only
  the generated layer fixes it; authored packages are unchanged. Actual UF+YAP
  two-player arranged bag/beacon Use now passes with both native search paths
  proving the correct provider;512MiB/raw experimental resource scope remains.
  Evidence: `pathfinder7f19-UF-canonical-provider-ARRANGED-actualREMOTE-USE-PASS-1795307700843026510`.
  QA clones archive recognized obsolete overlays. Installation retires only
  unchanged old runtime-lock-owned layers with rollback; modified/unowned old
  layers fail before downloads and remain untouched. Four filesystem/rollback
  tests and the installer regression pass.
- **Actual UO joiner mouse:**
  `run/UO-YAP-23d6-real-joiner-mouse-PASS-1795308246501481986/` proves one Win32
  relative event to the validated owned foreground joiner main window. Current
  ownCGclient1 and authoritative HostPS1 yaw both change17.59461degrees; common
  two-player liveness/observation and clean exits pass. UO caption/class is
  `CoD:United Offensive`; the old test helper wrongly required `Call of Duty`.
  Host mouse has a separate earlier positive, not this same run. Physical mouse
  hardware is not claimed. Prior focus/surface, observer-index and occupied-port
  harness failures are retained in `run/input-window-investigation/`.
- **Worker bridge checkpoint:** local source `e0692dc` implements the Python
  half only; real worker UDP/file transactions and native C++ resource-encoder
  parity pass54 focused checks. Native files are emitted by a test program;
  actual Native slot/owner/kit binding is still unimplemented. Current draft
  nonce policy now uses three per-pending-index monotone uint64 serial fences,
  replacing the256 lifetime cap. Actual two-worker300-request transactions
  preserve party/GUIDs;1100 replay/expiry/out-of-order/clock cases and55 focused
  checks pass. Native producers/consumers remain test programs. See
  `run/party-native-serial-handoff.json`; Native still must consume/expire its
  own POD challenge before slot allocation.
- **Four actual players:**
  `run/qa-cod1-four/history/four-owner-d982-training-distinct-yaw-saved-not-latest-pose-vitals-nativeCP-PASS-1795309048301166085/`
  passes real input-separated positions and distinct saved yaw for four owners,
  health600/550/500/450, then extra movement/look and guest2damage to490 after
  saving. Native load restores saved500, not latest490; all four pose/view deltas
  are0, ownCGclient0..3/cameras and inventory match, all four move afterwards
  and quit0. Training is unarmed and is not campaign completion. Earlier yaw
  fixture with coincident directions is retained as the narrower first proof.
- **Still required for save acceptance:** downed/special-role snapshots, actual
  host-process stop/restart/resume with authenticated stable member identity,
  and saved guest mapping independent of arrival order. Current sidecar VERSION1
  is bound to session/lease/endpoint, not stable GUIDs; same-process cold A→B→A
  proof does not establish resume on another game-process lifetime.

- **Inactive-owner departure:** frozen Core
  `23d6cb34b3dfcfd3a86cd1440efeb454401b7bf25b2f3a6a73979ab8a995dfcf`
  now passes actual CoD1 and UO+YAP timeout→Leave→fresh-rejoin checks. Temporary
  timeout retains the seat and expected party2; intentional Leave clears only
  its current-world owner lease and reduces expected party to1 exactly once.
  The host keeps running; a separately requested fresh join acquires lease2
  instead of the old lease1, restores party2 and passes normal all-player clock,
  observation and clean-shutdown checks. No inactive native player is disconnected
  a second time. Evidence:
  `run/reserved-departure-23d6-COD1-PASS-1795305822476913237/` and
  `run/reserved-departure-23d6-UO-YAP-PASS-1795305936022075076/`.
  Old602 fails this same departure predicate; that negative is preserved. Earlier
  functional positives rejected by terminal-party/log oracles remain FAIL records.
  The scenario now explicitly rejoins before common liveness checks and declares
  exactly one localized native disconnect banner, requiring its preceding Leave
  marker; crashes, other errors, missing/extra banners and exit failures still fail.
  Reproduce with `tools/qa_reserved_departure.py --source OWNED_GAME --run NEW_QA
  --runtime-dir FROZEN_RUNTIME --variant cod1|uo --port UNUSED_PORT`.
  UO requires the pinned YAP plugin/extras and reviewed LAA executable in the
  isolated copies; the initial missing-plugin preflight correctly failed.
- **New private installer artifacts:** exact602/98de830 Linux AppImage
  `run/Install-CoD-Coop-0.6.0-dev.4-combined602-Linux-x86_64.AppImage`, SHA256
  `ced5af3d1baef31d5b9b3c0479f6669e3792c404bce4c9b430f1905d9be14b53`;
  Windows folder `run/combined602-windows-private-98de830/`, EXE SHA256
  `0230005558a00f725aa72fc99647f21456fdae6413d05f568ea42a0ee08d7b88`.
  The Windows EXE requires its complete sibling suite directory; it is not a
  standalone3MB suite download. Actual AppImage GUI and both backend entry paths,
  all embedded bytes, old-Core rejection and GLIBC≤2.35 checks pass. Windows
  resources/sidecar bytes pass; no native Windows GUI/hardware test is claimed.
  `run/combined602-packages-handoff.json` records exact frozen source and limits.
  These artifacts predate23d6 and the ongoing bootstrap/party work below.
- **Active integration, not accepted runtime:** production-bootstrap private
  work starts from98de830 under `run/production-bootstrap-private/`, aiming at
  durable State19/resource-capability-v2 ownership. Launcher party transport,
  stable installation identities and individual signed equipment choices are
  being implemented separately; native per-member roster/plan ACK and actual
  pre-mission kit application remain required before enabling that launch path.
- **Signed launcher lobby milestone:** actual two-/four-process UDP parties,
  controlled loss/reordering, forgery/stale/conflict negatives, stable identity
  through a worker restart, heartbeat waits without party shrinkage and genuine
  bilingual GUI worker connections pass. Source includes `coop_party.py`,
  `party_gui.py`, `party_binding.py` and supervisor/freezer/staging dependencies;
  cryptography50.0.2 is pinned. Private installation keys stay outside the game
  tree and are never part of public snapshots. This confirms equipment choices,
  not Native readiness; its launch action stays disabled until actual owner,
  roster, plan and resource ACKs exist. Exact source/proofs:
  `run/party-transport-milestone.json`. No packages were rebuilt for this change.
  Full current source run:263 Python cases,240 passed,23 opt-in native skips,
  `run/unit-party-45858-current.log`;47 focused party/GUI/session cases pass.
- **New checkpoint acceptance gap:** the arranged Pathfinder interaction tests
  pass remote bag/beacon actions and numeric inventory restoration in CoD1,
  UO+YAP and SPI+YAP. They do not preserve the guest's saved position/look;
  the guest respawns at the map start while the host pose is correct. This is
  the historical bug corrected by the newer State21 ordinary-player fixture
  above, not full checkpoint acceptance. Root's read-only trace
  Core `1805e8117c47e327b9c12fff021885621d03c76a613e1bb0fdd3ce37aef76ec7`
  under `run/saved-pose-investigation/` observes loaded native PS before ghost
  cleanup. A strict arranged-position test is pending; no pose fix is claimed.

- **Brecourt:** seven targeted native checks now pass across CoD1, UO,
  SP Improved and United Fronts. An eligible real joiner triggers the original
  post-goal Moody handoff while the host remains outside its distance gate.
  Actual downed1HP is rejected; standing1HP and the original host are accepted.
  Original objective4, explosives flag and four bomb triggers are retained.
  `run/campaign-investigation/brecourt-acceptance-summary.json` records scope:
  isolated post-goal mechanics, not NPC approach, battle or full mission.
- **Pathfinder input and inventory:** Core
  `7f19ec02b05655cd3fbdc993ae664c11576a9d1ac66958a98bd741e665b56449`
  preserves the native local client-input clock while its independent server
  simulation is frozen. Actual peer keyboard turning and owned Win32 mouse
  injection change native and own-CG yaw; this is not physical hardware testing.
  A strict near-host checkpoint restores the guest's chosen Colt28/6, all
  slots and ammunition exactly, without repeating the fresh initial kit.
  Host Colt28/7 is unchanged and no dropped Colt is introduced. Saved-ghost
  cleanup uses the signature-checked native partial-connection path before
  normal entity cleanup. Ordinary explicit disconnect/timeout drops are a
  separate open scenario. Evidence:
  `run/qa-cod1-four/history/pathfinder7f19-nearHost-Colt-nativeCP-exact-MOUSE-KEYBOARD-PASS-1795304573891484772/`.
  Natural bag/beacon use and complete Pathfinder playthrough remain pending.
  Fresh-only starting equipment excludes UF's authored individual kit path;
  checkpoint-before-earned-kit provenance remains open.
- **Rendering:** private UO proof retains native ET_PLAYER drawing for a
  precisely coincident upright teammate, removing a head intersection without
  moving either player. Downed bodies, third-person views and movement apart
  retain normal bodies. This is a conservative half-unit coordinate-equivalence
  rule, not a general proximity radius; CoD1's observed15-unit spawn case is
  explicitly unresolved. Evidence: `run/body-overlap-private/STATUS.md`.
  HEAD combines this policy with input/ghost fixes and stronger PE image bounds;
  compiled Core `602cb6af5d25fc7cf8a010e96f56e2a05095dcd30a991499b80ae08d07fa9228`
  passed fresh targeted native UO regression: both unchanged positions clear,
  downed body visible with normal Use revival, third-person retention and
  162.5units actual movement. Peer keyboard turns107.7degrees with nonzero
  local input time. UO mouse injection remains untested: both owned-window
  methods refused surface binding before injection; no mouse failure is inferred.
  Evidence: `run/combined-body-validation/STATUS.md`.
- **Private resource bootstrap:** CoD1 and UO now both pass lost-fragment
  retransmission before the peer's first GAME_INIT. UF also passes default and
  peer-first world-refresh cases with complete current weapon mappings.
  These are private QA prototypes, including raw512MiB UF; persistent lifecycle,
  complete future asset closure, host world rules and individual pre-mission
  party transport are not production-integrated. See
  `run/network-bootstrap-prototype/STATUS.md`.
- **Installation contract:** all variants now require the same two pinned visual
  patches even for slim suites. Mandatory Core feature bits15 are checked from a
  read-only PE export, separately from runtime hook readiness. Recursive save
  summaries preserve nested native saves and avoid symlinks. Current checker
  `0cd064f6d495114db2def1fecbd5cded9898c92a7c77d30083781594724637a8`
  and Linux/Windows frozen workers are recorded in
  `run/fixed-suite-api15-handoff.json`. New immutable stages still contain the
  older bac5739 Core and must be rebuilt after combined-Core validation.
  The previous cb7071 AppImage is an old private test artifact, not a current
  distribution. Actual native Windows/Steam acceptance remains unavailable.
- **Current source checks:**250 Python cases,227 passed and23 opt-in native
  skips (`run/unit-current.log`);27 C++ fixtures passed ASan/UBSan. Native
  campaign acceptance is recorded separately from these source checks.

Older checkpoints follow for traceability. / Ältere Zwischenstände zur Nachverfolgung:

- **Private network bootstrap UO PASS:** immutable experimental Core
  `caa9185bacf0b5c36f15058e8a6ec739e2226273a98a56a0b2045697e798546e`
  transfers87 models and89 ordered weapon entries (4100bytes) over real UDP
  before the peer's first GAME_INIT. A deliberately lost first fragment is
  retransmitted; normal native item/alt registration and renderer preload keep
  game modelCS81 unchanged. Complete Game/CG weapon mappings are checked before
  native-ready ACK, JOIN and ACCEPT; actual remote input moves185units.
  Both native exits and final images pass. Evidence:
  `run/mainline-credits-qa/proof-BOOTSTRAPCAA-UO-UDP-LOSS-PREINIT-PASS/`.
  This is a QA-gated private dbda-derived branch, not integrated HEAD or a
  production UF resource/lobby/full campaign pass. CoD1 counterpart is pending.
- **Legitimate native names:** the first resource probe correctly waited at a
  mismatched CG mapping for stock `rgd-33russianfrag`; the selection-only name
  reader wrongly rejected hyphens. HEAD now accepts that bounded native name
  while still rejecting command separators/whitespace/paths. ASan/UBSan and
  compilation pass; new actor-aware frozen Core
  `22e29436579d31dfe1ccf76f8b5f8c0db3ca09be5ec3d7d5a0e19d1f6115a974`
  is separate from the existing cb7071 runtime candidate and its native proofs.
- **Cleanup evidence follow-up:** new source records actual `game_stopped`
  codes/forced termination per owned process, including Retry and normal
  committed process transitions. Actual child exits7/9 remain observable and
  cannot become a zero supervisor status in the test oracle. Existing d77e/cb1c
  bundles and current AppImage candidate predate this telemetry. Earlier
  supervisor-based final-stop claims have this narrower evidence limit;
  direct qa_coop native process exit checks are unaffected. See
  `docs/session-recovery.md`.

- **State18 native save lifecycle:** frozen core
  `dbda01bc97f5fdd3ec36748d6425ce69a7ab9bc89205aff61defbb255ed7b07a`
  passes a real two-player cold A→B→saved-A load without distributing fresh
  kits over preserved inventory. Host Garand192/7 and guest Carbine240/14,
  including active hostPS/ownCG selection, survive; both fire afterwards.
  Evidence: `run/uf-script-qa/history/preservation-dbda-COLD-A-NO-REFILL-STRICT-PASS-1795296164772889368/`.
  The earlier native client-mismatch failure remains archived. The fix rearms
  the existing narrowly signature-checked saved-remote adapter before native
  deserialization, including DLL reload. Ordinary bounds checks remain active.
  Scope: isolated raw512MiB UF probe with offline resource union, not production
  bootstrap or full campaign acceptance.
- **World lifecycle:** actual CoD1 and UO solo→host, host-alone fresh map and
  fast map_restart each issue the current world/tickets once; real peer rejoin
  and movement pass. Evidence:
  `run/mainline-credits-qa/proof-COD1-DBDA-WARM-HOST-ALONE-FASTRESTART-PASS/`
  and `run/mainline-credits-qa/proof-UO-DBDA-WARM-HOST-ALONE-FASTRESTART-PASS/`.
- **Actor eligibility:** new frozen core
  `cb7071e5c92f794a91634b63cc2afba87865ba35e267507bbe5c628512528a41`
  derives script eligibility from current native identity, loaded world,
  connection, health and downed state. Standing1HP remains eligible; downed1HP
  does not. Pure ASan/UBSan test and MinGW build pass; real Brecourt handoff
  probe is pending. Exact source: `run/actor-eligibility-prototype/`.
- **Delayed switch:** actual two-player CoD1training→UOtraining passes at256MiB
  with130s background verification, visible native waiting and one explicit
  Retry. Invalid content cancels safely after the deadline; a synthetic new
  JOIN is rejected before slot allocation while the two real players remain
  active. Immutable source-mode evidence:
  `run/switch-delayed130-source-pass-1795297970968175765/` (486 files plus
  SHA256 index). This is a process transition, not a campaign
  playthrough. The frozen source graph in the result defines exactly what ran.
- **Launcher follow-ups:** launch now sets the original difficulty/maximumHP
  pair (1200/600/300/200); both native engines passed hard training with
  deliberately poisoned prior HP configuration. Source recovery Retry now
  restarts an owned committed-recovery process using the validated same session
  specification. Source tests pass; native committed recovery and new frozen
  gameplay validation remain pending. New frozen Linux worker
  `d77e43f154066e50838f0b6f487af2ae127b5b28e65da99a4ef7240516aa72e7`
  and Windows worker
  `cb1c2b3b27a7445a83b03bef760eff07aa6ed97b00601fc4b6abc14bb29c795d`
  contain both fixes:63 focused source tests and10 actual frozen seal/prepare/
  read-only/protocol-rejection operations pass. Exact bundles and source graph:
  `run/worker9-recovery-handoff.json`. This does not certify native Windows
  gameplay. See `docs/session-recovery.md`.
- **Native package selection:** source inventory now matches verified ASCII
  uppercase native PathCmp ordering; CoD1 `sp_`/`zz_` aliases are handled
  separately from UO. Regeneration changed metadata order only: no shipping
  script provider or map count changed. Actual QA search-path evidence exposed
  a previously shadowed Brecourt test overlay; its aborted/timeout runs are not
  mission passes. See `docs/development-0.6.md` for addresses and reproduction.
  Production overlay names were not changed on speculation.
- **Current default tests:**218 cases,198 pass and20 opt-in native skips:
  `run/unit-protocol9-native-order.log`;24 pure C++ fixtures additionally pass
  ASan/UBSan. Passing Python tests do not replace the
  outstanding mission/platform acceptance matrix.

- **User decision / Nutzerentscheidung:** every UF player chooses their own
  equipment; the group plans distinct roles before mission start. Host authority
  does not mean choosing another player's kit. Only this Linux machine is
  available; native Windows10/11, mixed systems and separate-account Steam are
  still external acceptance gates.
- **Wire format:** source is `0.6.0-dev.5`, protocol9. All ordinary engine and
  Coop packets carry a session/world generation. Genuine old-world replay was
  rejected by type in both directions, followed by real current-world input:
  `run/qa-world-replay/history/1795285718014202522/`, core
  `22a3d14290f2ce6d7d8491b4b402c49767da26e24b86441f15b3101eb1c1a205`.
  Both directions of protocol8/9 rejection were checked before native player
  allocation. Reliable reload, cancellation during loading and a measured
  20-second connection outage have separate real-instance proofs. Historical
  protocol7/8 statements below describe their own binaries, not current source.
- **Native lifetime:** UO actor/corpse cache trees are HUNK allocations; ordinary
  script/Core replacement trees use the separate 512KB MT pool. Never free a
  native HUNK tree through MT. The current ownership ledger survives DLL reload,
  binds allocations to native MT epochs and releases owned remote-body trees
  before checkpoint reinitialization. Five real loads plus active hot reload
  passed in ordinary UO and in genuine protocol9 prepared EN/DE installations.
  Prepared proof: core
  `6b84be2ab6a185d4aefbe878c847df653df30f6ce25b822cfaa373229327dd99`,
  `run/prepared9-policy-qa/proof-PREPARED9-ENDE-6b84-AUTOPOLICY-HOTRELOAD-FIVELOAD-PASS-1795290073423710388/`.
  This used the prepared automatic policy, without the raw host-GC override.
  Personal files were restored and independently verified in
  `run/prepared9-post-game-restoration-verified.json`.
- **Historical inventory failure / Historischer Inventarfehler:**
  the first four-role probe preserved numerical inventory but lost Springfield
  and BAR active selection. This is fixed by the later strict selection proofs
  below. The original numerical PASS report
  is retained with a supplemental active-weapon FAIL audit in
  `run/qa-cod1-four/history/four-role-ammo-PASS-activeweapon-FAIL-1795289399920232132/`.
  Do not call this a complete four-role checkpoint or rendering pass.
- **Selection fix / Waffenwahl:** native SP GSC
  `switchToWeapon` writes the host's global cgame selection; it has no actor
  parameter. A targeted, reliable, ticket-bound selection bridge and a one-time
  checkpoint selection seed are implemented in State16. Selection waits for the
  actual own-player snapshot and registered weapon definition; early commands
  must not overwrite the restored weapon with zero. Native usercmd weapon is
  byte+6, not the older comment's high byte+7. Normal user switching must resume
  after acknowledgement. First strict two-role PASS, core `e9820fae…`, in
  `run/uf-script-qa/history/selection-e982-two-STRICT-PASS-1795292190790199867/`:
  Garand/Carbine, exact ammunition and active names in host PS plus actual local
  cgame desired/predicted/current own snapshot, real shots before and after CP,
  final weapon/HUD images inspected. Latest selection-only frozen core:
  `ddc1a6d301b61651e827835368d6d90d35a9458b1c62a71ed08281a3e0cb790b`
  in `run/selection-prototype/`; it additionally checks the actual CG weapon
  definition table, bounds unterminated names and avoids redundant Cvar writes.
  Four-role strict PASS on `ddc1…`:
  `run/qa-cod1-four/history/four-selection-ddc-STRICT-PASS-1795292654322543580/`.
  Thompson270/25, Springfield55/4, BAR200/17 and Garand192/7 survived native
  save/load with matching active hostPS and own cgame names; all four consumed
  ammunition through real post-load firing and final weapon/HUD images were
  inspected. Scope: original non-LAA EXE,512MiB raw QA and an offline approved
  resource union. It does not certify the production256MiB/bootstrap path.
  Ordinary user-switch/replay follow-up also PASS:
  `run/uf-script-qa/history/selection-ddc-USERCHOICE-NEGATIVES-CP-PASS-1795292850597022590/`.
  The remote selected Greaser normally; duplicate Carbine selection, wrong
  ticket/session/world and independent invalid host requests did not overwrite
  it. Greaser270/30 and previously fired Carbine240/14 survived native CP;
  post-load firing produced Greaser270/28. Final images were inspected. An
  earlier runner stopped on its own repeated-status-log oracle, not a native
  failure; the corrected runner checks persisted status plus fresh matching ACK.
  Root now owns Core; agent native probes use immutable
  snapshots. **Correct native snapshot pointer:** CURRENT UO `cg+259548`, NEXT
  `cg+25954c` (the native promotion instruction proves this); the older Stats
  comments were reversed and are fixed in current source.
- **Save ownership / Spielstand-Zuordnung:** State15 records completed native
  save-file SHA256 plus bounded owner sidecars through the existing GVM syscall
  observer. Session, endpoint lease, slot and spawn ticket prevent a replacement
  player from inheriting the previous occupant's equipment. Native CoD1 and UO
  Alice→Bob→old-save/own-save/corrupt-sidecar scenarios passed on frozen source.
  Latest pre-selection snapshot:
  `run/inventory-prototype/0f68ffe10ae3b40c785043f1b09ee6ba738056b22b79fc75244ae7459d44eddf/`.
  State18 cold/cross-map load intent and fresh-ticket timing now have the
  concrete proofs in the current checkpoint above. Only numerical
  loadout data is preserved; this does not certify script-owned mines, HUD or
  mounted-weapon state across loading.
- **Resource bootstrap remains blocking / Ressourcenabgleich bleibt offen:**
  model first-use allocation, native-tree borrowing and the DObj mapping barrier
  have isolated positive/negative evidence but remain QA-gated. Kit probes use
  an offline approved ledger, not a production lobby transfer. A missing
  `gear_US_carbinebelt` after an ordinary UO reload demonstrates that bootstrap
  also matters outside UF. `src/asset_bootstrap.h` tests bounded, canonical
  resource reassembly, including the complete ordered native weapon-index/name
  table and item-registration flags. Same names with different indices are
  explicitly rejected by its matching contract. This is not integrated and
  does not prove that native peer registration actually matches. Production requires
  approved models, native weapon/item/alternate definitions and host gameplay
  settings before peer map initialization, with an actual ready/acknowledge gate.
- **Installer coherence / Installer-Konsistenz:** Core exports readonly DATA
  `Coop_Protocol`. Both Python and native validators check the bounded PE export
  without loading the DLL and reject stale or malformed runtimes even with a
  re-pinned receipt. Staging compares Core, checker and manifest protocols.
  Metadata-enforced Linux and Windows frozen protocol9 workers and complete
  prepared EN/DE clones passed interoperability checks. Native checker13 cases
  passed separately under Wine. `run/prepared9-readonly-interop.json` records
  genuine frozen-worker/native checks. Final full installers/AppImage and public
  packaging are held until the native equipment/resource pipeline is accepted.
- **New real switch failure / Neuer echter Wechselfehler:** the frozen bundled
  protocol9 supervisor on core `6b84…` blocked its heartbeat/control loop while
  hashing a cold installation. The peer correctly found the deliberately
  unreceipted PK3, but Native SwitchTick's120-second early return stopped reading
  its late negative ACK; the cancellation gate failed. Preserved negative:
  `run/switch-protocol9-bundled/history/1795292887895856700/result.json` and exact
  frozen runner/provenance.
  Both QA games/supervisors were stopped cleanly; prepared source copies were
  read only. Do not relabel this as a successful campaign switch.
- **Switch fix / Wechselkorrektur:**
  one bounded read-only verifier runs off the supervisor loop. Cancelled or
  replaced work cannot ACK a later transaction, heartbeat/Stop remain responsive,
  unexpected worker errors fail closed, and no commit is permitted before the
  exact verification succeeds. Native timeout still exposes a wait, but reads
  late negative ACKs. Explicit retry rounds resume every peer and reject old
  READY/COMMIT controls without skipping participants. Native runtime-state
  projects waiting to a bilingual launcher Retry/Cancel state. Frozen core
  `a9079cf51b1d124ca5f12b5908826b0a1aefdb350e13cd4fb9efa73726a1b122`
  and exact source are in `run/switch-wait-prototype/`.15 focused supervisor
  tests passed (`run/session-async-unit.log`). Actual source-supervisor CoD1→UO
  process restart PASS at256MiB, including the genuine altered-client negative,
  fresh host save, automatic target startup/reconnect, live commands, actual
  difficulty/memory queries and clean exits. Exact preserved evidence:
  `run/switch-source-pass-a907-1795293734216938069/` (438 evidence files plus
  archive SHA index). This run did not require a timeout/retry, so it does not
  certify the new retry-round path. Source staging is in
  `run/switch-wait-final-overlay/` (not public packaging). A new bundled repeat
  uses `run/switch-bundled-6101-overlay/`; it remains pending.
- **New frozen workers / Neue gebündelte Worker:** source GUI/session graph
  is frozen in `run/worker9-async-proof/{linux,windows}/` with complete tree
  manifests in `run/worker9-async-handoff.json`. Linux entry SHA:
  `6101ecb5b80d9b45aa4d4259c078cb218ee0bf8f79fd953f5051c813a46174b4`;
  Windows entry SHA:
  `38cea7ea1f7c02554a72a5b8e1b67e2669a7d1d03eb24e8c27134a48b61df0d2`.
  Both actual workers passed seal/prepare/read-only preservation and explicit
  old7/8 rejection on isolated small PE fixtures.34 focused GUI/session tests
  passed;189 Linux ELFs require at most GLIBC2.35. No AppImage/setup release
  was built. The previous entire bundles are retained, not overwritten in proof.
- **Downloads and offline repair / Downloads und Offline-Reparatur:**
  `run/installer-download-qa/result.json` records10 genuine loopback TCP cases
  (5Python,5production WinINet under Wine),18 backend regressions and read-only
  checks of all three pinned GitHub assets (HEAD,Range,total,size/SHA digest).
  Full Content-Range bounds and declared response lengths are now validated.
  An isolated network namespace denied external TCP; the actual CLI repaired a
  deliberately damaged Core and owned UO overlay from the offline payload,
  passed complete verification and preserved8 genuine settings/save files plus
  their live read-only source hashes. The interrupted earlier driver and its
  resumed checkpoints are preserved. Native probe SHA:
  `d9032610309071f6ecf0a20ab43b0addd7d54b766f844a1409e31dbddbc5beee`.
  CI now builds that production-code probe and runs it directly on Windows;
  this is still not native Windows gameplay certification.
- **Remaining acceptance / Offene Abnahme:** native pre-mission equipment lobby,
  production resource bootstrap, full active-kit checkpoint behavior, cold-save
  ownership, complete mission playthroughs and natural campaign transitions,
  installer finalization, Windows hardware and separate-account Steam tests.
  Neither loading maps nor the isolated mechanics proofs count as campaign
  completion. No stable0.6 release is authorized by the current evidence.
- **Latest source checks / Letzte Quellcode-Prüfungen:** Python discovery200
  cases,180 passed,20 explicitly opted-out native cases skipped
  (`run/unit-protocol9-switch-async.log`, before the pending preservation patch).
  This count is not native acceptance:
  checker interoperability has its separate13-case Wine run. The six new C++
  fixtures for host ownership/policy, numerical inventory, save provenance,
  spawn tickets and bounded resource transfer passed ASan/UBSan locally and are
  now included in the development CI. Re-run after the pending selection patch.

## Current checkpoint / Aktueller Arbeitsstand

This section supersedes older “current” counts and mutable run-directory paths
below. Source is still in development; no stable release has been published.

- Frozen reproducible runtime: core
  `1a0bc53fb1fb01b09409b654f6bf8e4073d4bb548a43b07db5ac2fbcd17c100d`,
  loader `85fc865c0ccb50e277b3ccaa0cf16b846c740ac1c1b826eebaaef56900dd4c69`.
  Exact source, binaries, hashes and rebuild instructions are preserved in
  `run/runtime-archive-final/`. Current Core source also contains explicitly
  gated QA model experiments; do not attribute frozen-runtime results to them.
- Protocol7 synchronizes the reviewed YAP sprint/jump rules, including typed
  validation, acknowledgements, live corrections and restoring personal values
  on leave. A native config-writer hook also preserves original archived values
  when a player quits directly while connected. Actual writeconfig, direct quit,
  subsequent standalone startup and rejoin/input passed on the frozen core:
  `run/mainline-credits-qa/proof-archive-rules-1a0b-PASS-1795277060720289776/`
  and `proof-host-rules-1a0b-PASS-1795277126070468178/`.
- Stock UO Bastogne opening/Jeep scenario: two real instances, 153.5 units of
  remote movement, two genuine checkpoint reloads, stable observation and clean
  exits PASS on the frozen core (`run/qa-checkpoint/`). This is a targeted test,
  not a complete mission or blanket resolution of all allocator failures.
  Earlier CoD1 checkpoint evidence is archived under
  `run/qa-checkpoint/history/1795276128600133246/`.
- Four real CoD1 players plus a genuine checkpoint reload PASS on core `efbf`
  (`run/qa-cod1-four/`); all three remotes moved independently and rejoined.
  The older `1de73345` four-player proof is in its
  `history/1795275259442448296/` directory.
- UF actual remote mechanics have separate preserved evidence: MG placement
  through normal alternate-fire/ADS and clip consumption
  (`run/uf-script-qa/history/mg-itemcache-efbf-pass-1795276036315976145/`);
  one smoke-funded P47 call with original impacts
  (`airstrike-itemcache-final-pass-1795276234515570026/`); binocular artillery,
  20 owned native missiles and the original 180-second refill
  (`artillery-180s-pass-1795277774811289618/`). These used 512MB hunk memory;
  the final installer-default 256MB run remains a gate.
- Source includes a local individual-equipment chooser and verified original
  menu/asset catalog. It currently saves preferences only. Current protocol7
  does not yet apply independent kits or publish a ready lobby; the UI correctly
  refuses to advertise that missing capability. Frozen GUI bundles predate this
  chooser and must be rebuilt after native integration.
- Packaging is deliberately held: universal resource precaching exceeds the
  native 255-model limit in dense UF maps. Selected fixed-kit runs fit, but a
  valid four-role union reaches 262/258/259 entries on Noville/Foy/Tropez and
  cannot fulfill the individual-kit requirement with the old policy.
- QA-only renderer-cache preload has actual positive/negative two-peer proof:
  the missing aircraft renders with no new world-model IDs. A deferred-first-use
  registry now tests allocating IDs only when native callers consume them.
  Noville showed capacity progress; Foy exposed a 9494-byte animation-tree
  allocation failure. Tropez reached 175.3 units of actual peer movement but
  checkpoint reconstruction failed; an attempted preload timing change also
  caused a renderer access violation. All are unresolved experiments, retained
  as failures. No ID recycling, capacity widening or disabled native guards is
  accepted as a fix. Native tree ownership and save/cache reconstruction are
  the immediate investigation targets.
- Follow-up first-use proof PASS on Pathfinder, core
  `01efbe99493cc89c5ae67bf21818135ecfa4d54acb423c1d7bb3386a1ddd6dae`:
  real peer movement (170.3 units), native checkpoint/load, reconnection,
  advancing commands, stable observation and clean exits. The preload includes
  the catalog-derived 39-media-model union of four legal distinct kits; actual
  independent kit application is not implemented by this proof. Immutable
  evidence is in
  `run/mainline-credits-qa/proof-deferred-PATHFINDER-FOUR-KIT-CHECKPOINT-PASS-1795281672369739291/`;
  exact source is in `run/deferred-first-use-prototype/01efbe99493cc89c5ae67bf21818135ecfa4d54acb423c1d7bb3386a1ddd6dae/source/`.
  Foy/tree allocation and dense-map acceptance remain open.
- The full mission playthrough matrix, native Windows10/11, mixed systems and
  separate-account Steam acceptance remain open. Only this Linux machine is
  available. Do not label a Wine installer run as native Windows acceptance.
- Current parent Python discovery: 147 cases, 135 passed and 12 opt-in native
  cases skipped (`run/unit-current.log`). The native identity and checker runs
  have separate evidence; the skip count is not a substitute for those runs.
  Two additional packet-evidence oracle tests passed separately. Later roster
  additions require a new full count before source freeze.
- Individual roster contract now exists in `tools/uf_equipment_roster.py`:
  only the owning slot submits its kit, host owns world/membership, catalog and
  approved resource-plan hashes are checked, and changing kit/world/membership
  invalidates every ready acknowledgement. Nine focused contract tests passed.
  This is a validated source contract, not yet native lobby or kit-application
  evidence. Fixture: `run/uf-individual-roster-contract.json`.
- Frozen `1a0b` targeted network regression FAIL:
  `run/qa-partition/history/1795282035417881839/` records two
  real peers, training→Pathfinder, a measured 2002.394ms s2c partition and all
  three reload controls dropped. The link recovered, but the peer remained in
  the old world and disconnected after the native 15001ms host timeout.
  Repeated confirmed transition delivery is required. This first wrapper run
  predates its self-hash field; runtime hashes and the pinned relay revision are
  in the underlying provenance. The probe now also checks actual partition
  duration; do not relabel the negative as a successful recovery test.
- Development source is now `0.6.0-dev.3`, protocol8. It adds a random session
  nonce, ordered reload generations, endpoint-bound acknowledgements and
  500ms retries that survive dropping native remote slots. Duplicate controls
  are acknowledged without loading twice, including while local map startup
  is pending. Older development protocols are deliberately incompatible.
  Full old-world packet tagging and long blocking cold loads remain separate
  open network gates.
- Protocol8 repeat PASS on core
  `57f7cdad6e12e687625b26bd1eb8e37d4a14d712a980df6f0872888b57589f4e`
  in `run/qa-partition/history/1795282242007701990/`: measured 2000.286ms partition, actual reload packet
  dropped, automatic reconnection, 172.5 units of genuine remote movement,
  additional ordinary movement/stability and clean exits. No manual rejoin or
  target-mission start click was injected. Source snapshot and runtime are in
  `run/reliable-reload-prototype/`; source/model experiments remain QA-gated.
  All eight focused protocol/animation/control C++ sanitizer tests passed.
- Reverse-direction partition also PASS on `57f7`: the peer's acknowledgement
  was actually dropped, retries recovered automatically and the peer processed
  exactly one map change (`run/qa-partition/history/1795282597982890083/`). Full packet evidence is retained;
  native remote input, stable observation and clean exits passed again.
- The same `57f7` runtime passed four actual CoD1 players with two consecutive
  native checkpoint reloads (`run/qa-cod1-four/`). Native protocol8 checker
  interoperability: all11 cases PASS in162.331s
  (`run/native-protocol8-checker.log`); native identity/CryptoAPI case PASS
  in5.412s (`run/native-identity-protocol8.log`). These are Wine tests, not
  native Windows hardware acceptance.
- Known follow-up: explicitly cancelling hosting while a reload is pending
  must notify pending inactive endpoints and stop their local rejoin wait.
  This path is not yet covered by the successful delivery/recovery proofs.
- Latest complete Python discovery:169 cases,157 passed,12 opt-in native
  cases skipped (`run/unit-protocol8-final.log`). The12 native cases passed
  separately in the identity/checker runs above. Equipment/UI focused run:
  33 PASS under pinned Ubuntu22/Python3.10/PySide6
  (`run/uf-roster-ubuntu-tests.log`). Source projection remains explicitly
  capability-gated and does not claim native equipment application.
- Stronger four-player checkpoint repeat PASS on `57f7`
  (`run/qa-cod1-four/`): each of three real peers moved after each of two native
  reloads using distinct forward/back/sideways commands, in addition to advancing
  clocks and clean exits. The first screenshot had overlapping players because
  native rejoin respawned them together; the stronger probe separates them and
  the fresh joiner screenshot was inspected with clear world/player rendering.
  Exact executed runner SHA `431963e2456d3110c1a8ded6eee0255bf16f44254d002eb406087410818aa4e7`
  is preserved as `run/reliable-reload-prototype/source/tools/qa_coop-postload-proof.py`.
  Current runner additionally checks the forward/back input sign.
- Foy first-use/native-tree borrowing QA PASS on core
  `93d47274f761da07dd1ea4229b718f5ba8bf81ba7fd613d39212af044650dd0f`:
  natural truck intro,181.6-unit actual peer movement, stable snapshots and
  clean exits. Immutable evidence:
  `run/mainline-credits-qa/proof-deferred-FOY-NATIVE-BORROW-PASS-1795282593854955297/`.
  Sixteen native borrowed trees and five Core-owned humanoid replacements were
  active. Borrowing requires all explicit QA flags; it is not a production fix.
  Subsequent256MB firing/checkpoint test on `a31c4640` correctly FAILed with
  native renderer access violation `50c0d2` after deferred-tree cleanup.
- Important RE correction: the97 prepared native cache trees (911,542 bytes)
  are HUNK-backed, not MT-backed. Native traps0x58/0x59 use different allocators.
  Core replacements consume the separate512KB MT script pool. Native borrowed
  HUNK blocks must never reach MT_FreeIndex; the earlier inference that all97
  native blocks already occupied MT was wrong.
- Host cancellation now sends session-bound close notices to loading endpoints,
  stops queued automatic rejoin and clears deferred MT indices before native
  disconnect. The first oracle looked in the wrong log and was interrupted;
  the corrected test proved cancellation but then exposed a fresh-session hang
  at deferred-tree freeing. Native RE confirmed disconnect→full shutdown→MT_Init
  at45fab0 resets the allocator, invalidating those old indices. Corrected core
  `68192351789148e3a74eb47a7ecb0003d4ca0321db664632d3694ea9c719ffa8`
  passed the complete targeted repeat in `run/qa-partition/`: cancellation
  before remote-slot reallocation, authenticated host-close notice, five seconds
  with automatic rejoin stopped, explicit fresh session, real remote movement,
  stable observation and clean exits. Source/runtime are frozen separately in
  `run/reload-cancel-final/`. Earlier wrong-log oracle ABORTED evidence is in
  `history/1795282683996027911/`; the corrected-oracle fresh-session hang FAIL
  remains in `history/1795283172475386184/`. Full campaign/network acceptance is
  still open.
- Longer-outage recovery: core `68192351` correctly FAILed a real20s bidirectional
  outage across a same-map native restart (disconnect after15015ms). First
  auto-recovery prototype `e1764497` reached the map but FAILed command-clock
  advancement. Relay evidence showed old client sequence1513…1518 followed by
  fresh1…166, poisoning the newly allocated native netchan. Core
  `5a12a783109577d8b13ef83db281607b79b085bc2ca85344775e22e550116b6a`
  suppresses old-world native sends until attachment. The repeat PASSed:
  visible logical reconnect wait,20,000.339ms outage,36 actual reload messages
  dropped, normal automatic world reload,159.5-unit native remote movement,
  stable observation and clean exits (`run/qa-chaos/`). Immutable source/runtime:
  `run/reconnect-final/`. Negatives are preserved in its history
  `1795283713762113551/` and `1795284105770298508/`. Older6cbb bad-WiFi proof
  formerly at the root is now `run/qa-chaos/history/1795283608037899792/`.
- Native256MB dense-map first-use/borrow proofs now also include actual firing
  and checkpoint movement on Noville and Tropez, core `b4594765`:
  `run/mainline-credits-qa/proof-deferred-NOVILLE-256-FIRE-CHECKPOINT-PASS-1795283674959002564/`
  and `proof-deferred-TROPEZ-256-FIRE-CHECKPOINT-PASS-1795283901978398451/`.
  Final host CS counts220/198; they remain within255 without changing native guards.
- Causal mapping-invariant probe: local native DObjs retained their old model
  IDs while client-CS changed to host IDs. Delaying only post-checkpoint DObj
  packets for2s exposed15 model-name mismatches during cls2 rendering. QA-only
  detach/sync before host CS mapping on `5a12` produced zero mismatches across78
  observed render states, with265 actual DObj packets withheld,111 local DObjs
  detached, real firing/movement before and after checkpoint and clean exits.
  Proof: `run/mainline-credits-qa/proof-deferred-FOY-256-MAPPING-BARRIER-PASS-1795284283778387233/`.
  Same-DLL feature-off control is in progress. This establishes an invariant
  repair, not yet the root-cause resolution of the intermittent renderer crash.
- Native DObj destruction ABI was corrected independently: both engines read
  a stack bool that the old wrapper omitted. A real 32-bit Wine stub tested
  2000 true/false calls and stack preservation. This repair does not close the
  Foy allocation failure, which still reproduces on the corrected protocol7
  prototype. Borrowing Game-owned trees requires explicit ownership handling.

## User decisions / Nutzerentscheidungen

- Full pinned suite for every player: CoD1, UO, SP Improved1.5, United Fronts1.1beta, YAPr169.
- Up to4 players; host world authority, all players participate in suitable objectives.
- Host-owned saves; no host migration/save distribution.
- Host chooses variants, mission and difficulty; group follows with safe saving/restart.
- Confirmed equipment decision: United Fronts players select their own starting
  equipment from the mod's supported choices. Different roles are planned
  together before mission start; the host does not impose one common kit.
  The shared resource contract must include all chosen kits, readiness and
  before-start validation against the native world-model limit.
- Recommended mainline starts with CoD1 and continues seamlessly into UO, retaining AI improvements.
- Mainline uses SP Improved's UO-engine route; classic profiles and UF remain separate.
- Improved AI belongs to the recommended Coop baseline across the CoD→UO route,
  rather than requiring players to enable an unrelated singleplayer extra.
  Preserve the pinned mod's AI behavior; adapt its single-player assumptions so
  remote players participate. Do not claim that every addon contributes an AI
  upgrade without comparing its actual scripts/data/native patches.
- English default docs, equal German docs, both languages in changelog/release notes.
- Mixed German/English gameplay installations; unlocalized custom content retains original language.
- Windows10/11x64, Linuxx86_64 Wine/Proton; CoD2 experimental, outside completion target.
- Graphical Linux installer plus terminal; full suite mandatory rather than optional extras.
- Native Windows, multi-account Steam and complete campaign tests remain final acceptance gates.
- Hardware confirmed by the user: only this Linux machine is currently available.
  Windows setup executed through Wine does not close native Windows acceptance.

## Implemented foundation / Umgesetzte Grundlage

- `content/variants.json`: pinned versions, required variants/runtime/overlays and mainline definition.
- `tools/coop_suite.py` + native installer checker: full receipts, hash checks, game-content
  fingerprints independent of localization/GUI-platform files, preparation of guarded runtime profiles.
  Only reviewed language path/hash pairs are exempt from gameplay comparison;
  unknown or modified `localized_*.pk3` files contribute to the fingerprint.
- Protocol7 preflight before assigning slots. Old clients cannot feed gameplay state to new hosts.
  Development suite `0.6.0-dev.2` adds host-authoritative YAP movement/prediction
  rules; older protocol6 runtime proofs below remain explicitly version-bound.
- Same-IP routing correction: SP engine writes literal zero qport; each remote now has its own
  identifier, host resolves collisions and accepts raw datagrams only from allocated matching peers.
- Bounded control packets and atomic animation-fragment assembly (loss/reorder/duplicate tests;
  unfinished pending entries are bounded and evicted rather than starving newly visible actors).
- UO loader loads `plugins/yap/DDRAW.dll` before Coop hooks and checks prologues.
  Upstream requires uppercase basename; YAP stays loaded during core hot reload.
- Local-only reviewed script builders preserve each mod's menu and generate selected mission
  activator adaptations. UF actor-local ammo, mines and mount work is in reviewed transformations.
- UO grenade ownership is derived from proven native owner number+entity pointer, not proximity.
  Fixed-size encoded banks prevent growing one cvar for every entity index.
- Native Linux/Windows launcher GUI, difficulty/map selection and confirmed host-only switching.
  Source supervisor owns the game process, validates installations and coordinates restarts.
- Transactional setup, resumable checked downloads, preservation of personal cfg/saves,
  failed-install restoration and public rollback. Linux graphical setup/AppImage is built.
- Real-client QA adapters for native checkpoint reloads, delayed host startup and
  the pinned Co-op Anything UDP chaos relay (revision recorded in development
  commands). Retries archive results, native runtime and engine logs; stale PASS
  files are not reused. Scripts reject native runtime/snapshot errors explicitly.

## Runtime evidence / Laufzeitnachweise

All game runs used isolated copies. No game DLL, config or save in the live installation was changed.

- CoD1, two real instances: preflight, joined state, real user-command advancement, movement, clean exit PASS.
- CoD1, four real instances behind oneIP: independently controlled slots1/2/3, movement and clean exit PASS
  after the qport correction. Earlier four-player test correctly failed and exposed the bug.
- Delayed-host regression PASS: real joiner started35seconds before the host,
  then exchanged advancing user commands, moved and shut down cleanly.
  Native backward snapshot time had previously disconnected its renderer.
  Waiting joins now stop the independent local world clock; an already advanced
  local world reloads normally before attaching to older host snapshots.
  Evidence: `run/qa-cod1/result.json`, pinned runtime in its provenance.
- SP Improved + YAP + Coop: two real instances connected, snapshots and animation clocks advanced.
- United Fronts + YAP + generated overlays: two real instances, clocks, movement and clean exit PASS.
- UF mechanics fixture: separate binocular ammo bookkeeping and distinct native mount entities PASS.
  Deliberately restoring shared bookkeeping produces an actual FAIL; detector negative-control PASS.
- UF real remote grenade/mine PASS: native projectile ownership, normal placement
  without moving the host, normal pickup/ammunition restoration, a second mine's
  normal proximity detonation and actual enemy health loss. Shared AI melee now
  recognizes a remote player's stance instead of reading an AI-only field.
  Positive proof: `run/uf-script-qa/`; separate shared-stockpile negative-control
  proof: `run/uf-negative-qa/`. Mine damage to an enemy alone is not proof that AI
  independently targets and damages a remote player; that has a separate observer.
- Autonomous hostile AI→remote damage PASS: an existing enemy was positioned
  near the actual remote, farther from the host. No target/enemy/goal/accuracy
  assignments or artificial damage calls were made. Native AI chose that remote,
  and the observer verified a real damage notification from that exact enemy
  plus remote health loss. Two-client smoke and clean shutdown also passed.
  Evidence: `run/uf-ai-qa/history/1795267034608368616/`, core
  `90c2e8eb1aad20ee594687de0afbe749ec812aaa77ac14d6ed839cb1742128d7`.
  This proves that observation only. Subsequent script inspection found scripted
  one-health actors in the initial Pathfinder scene, so it is not sufficient
  evidence for ordinary healthy combat AI. A separate Brecourt test with an
  existing healthy enemy, visible targetable remote and hidden host did not
  acquire or damage the remote in fifteen game seconds. Native sentient/target
  enumeration and line-of-sight diagnosis established that native AI actually
  iterates all sentients. A later controlled Brecourt run with a verified clear
  trace reached genuine remote acquisition and damage; see the newer proof below.
  No target or accuracy assignments were used to force either result.
- Shared native scripted-film→world reload PASS on core
  `8c5f8ead031644ed4959e0e3193a76769276e72d09e6f2f128dc31b773d34026`:
  both actual UO-engine players played `cod_end.roq`, remote playback ACK arrived,
  both reached natural film end, normal host map loading rejoined both worlds,
  real remote movement/stable observation/clean exit passed. The first test
  exposed stale animation-tree cleanup after the native film had cleared the
  world; the fix forgets the freed world and suspends its state application while
  retaining party controls. Archived evidence:
  `run/uf-script-qa/history/1795269816358340004/`.
- Frozen source-supervisor group restart PASS: CoD1/training→SP Improved/pathfinder,
  both actual processes restarted, host wrote its checkpoint, both engines reported
  requested difficulty2, actual remote commands advanced, both supervisors resumed,
  clean shutdown. An added unreceipted PK3 correctly cancelled preparation while
  both players remained active. `run/switch-real-qa/result.json` records frozen tool
  hashes and core `c24a9b1d…8286194`; it is not proof for later rebuilt binaries.
- Natural original CoD credits→UO continuation PASS with two real instances on
  core `12562819b50e6ff5383680df43203c17db11e983c43b6dad3e41debbe225bdc9`:
  normal credits completion, original victory Continue action, both clients on
  `bastogne1`, rejoin, readiness-gated mission start, original Jeep introduction,
  real remote movement, stable observation and clean shutdown. Credits used4x
  engine timescale, then returned to1x; transition took99.383wall seconds.
  Evidence: `run/mainline-credits-qa/`. This is a targeted transition test, not
  a full Berlin mission or complete campaign playthrough.
- Native Windows setup executed under Wine on a3.6GB game copy; native and Python receipt checks PASS.
  All8 existing personal cfg/save files retained identical hashes. This is not native Windows hardware QA.
- Native/Python receipt interoperability, same-size corruption, eWeapons JSON, rollback and lowercase
  paths tested. Python unit tests and native protocol/fragment tests run from development commands.
- Installation sealing now prepares its initial runtime profile from the same
  freshly hashed receipt, avoiding repeated full reads in one setup operation.
  Independent check/prepare/launch still hash content again; no timestamp cache.

Evidence is under ignored `run/` directories; exact current binaries and each run's scope are in
its `provenance.json`/`result.json`. Do not attribute an older run to a later rebuilt DLL.

### Latest regression results / Aktuelle Regressionstests

- Core `19470452cdbebf4fea70eb1c5e438a2a43d03c759cc5c4b831cc217699d74641`:
  three and five consecutive real UO checkpoint reloads PASS, with two actual
  players reconnecting and advancing snapshots after every reload. CoD1 also
  passed three reloads (`run/qa-checkpoint/result.json`). These tests exposed
  and fixed absent reliable buffers for saved remotes, server-time rollback,
  deferred same-map loads and the secondary cgame server-simulation syscall.
- Core `1de73345e5efe9e6e2634ce481ebe057073d261e5c2c738a49ee3622abc25870`:
  four-player CoD1 smoke PASS with three independent remote movements,
  advancing commands, stable observation and clean shutdown (`run/qa-cod1-four/`).
- Core `84790c2fcba9ef35dab13a7be12dcfcc6d1db2e7fa0a331540eff8c4fc110b6a`:
  two-player real Co-op Anything `bad_wifi` relay smoke PASS
  (`run/qa-chaos/history/1795273945569903274/`).
  Preserved scheduling logs show 86/1393 client-to-server and 254/5746
  server-to-client packets dropped, plus duplication and scheduled reordering.
  Exact log hash/counts are in `network-summary.json`; this is not Steam or
  impaired checkpoint/map-transition certification.
- A later mainline retry reached UO and accepted real remote input but correctly
  failed its error gate: game DLL reload at the same address lost the GetEnt
  hook. Core `8cbe87c19949988dacfb87030a12584e3be4179c5b88839961d6d38713cf0d4d`
  rearms fresh native prologues and reports failed native world attachment
  instead of silently retrying a half-attached world. Its targeted retest PASS:
  both players saw progressing original credits, naturally reached Bastogne
  after 137.475 seconds, completed the opening scene, accepted real remote
  input and shut down cleanly. Native script/asset/clock error count was zero.
  The initial expected party size was one and grew from the actual joining
  player, rather than a test-only forced party size. Evidence:
  `run/mainline-credits-qa/{result.json,mainline-probe.json}` and both-player
  early/middle/late captures under `credits-captures/1795272560008934078/`.
- The same `8cbe87c1` core also passed the complete targeted movie regression:
  actual native playback on both players, playing acknowledgement, natural end,
  regular host world reload, reconnection, real remote input, stable observation
  and clean shutdown. `run/qa-movie-final/{movie-probe.json,result.json}` preserve
  this newer result separately from the older film proof.
- Current Python suite: 111 cases, PASS with nine environment-dependent skips
  (the opt-in native Wine identity/checker cases).
  Separate native Wine identity/CryptoAPI tests passed; no native Windows game
  test is implied. Final artifact hashes remain pending source freeze.
- Pinned `19470452` core with the reviewed thirteen-model UF early-precache
  overlay: healthy Brecourt enemy 129 independently acquired actual remote 1
  and dealt 43 native damage (600 to 557 health). Read-only GSC line-of-sight
  and external native process reads confirmed the remote's valid sentient/team,
  visible perception record, actual enemy pointer and actor state transition.
  No target/goal/flags/accuracy or artificial damage assignment was used. The
  prior negative remains preserved; this proves one controlled ordinary combat
  case rather than all enemies or missions. Exact DLLs, QA overlays, native
  read-only helper source/binary, observations and fresh images are archived in
  `run/uf-script-qa/history/1795273220045343268/`; the prior healthy negative
  remains under `1795272974986328327/`.
- Core `6cbb0f969b46357067bf05c8f02801f3206367feeaf44071592c48038c0a069d`:
  explicit leave now correctly reduces the agreed party from two to one; clock
  resync and timeout departures keep reserved participants. The real party
  regression then exposed a separate host-only startup race: a normal UI action
  fired before native UI settled, native pause returned and the world remained
  at 300 ms. The test correctly FAILed its next-mission gate. Evidence:
  `run/qa-party-final/history/1795274057785701111/`.
  Core `a1bbd793a7102a34bd8c1e559ea639e5734d997726c1fa68840b09a204e19fc2`
  adds stable native readiness and bounded startup retry. Its first repeat
  completed departure, host-only start and real rejoin/input but the final error
  oracle counted the intentional native `ERROR: Getrennt` notice as an unexpected
  disconnect. The probe now acknowledges exactly one observed notice after its
  own explicit leave command, with an empty pre-departure error baseline. All
  other errors and second disconnects still fail. Full repeat PASS on `a1bbd793`:
  explicit leave, normal host-only next mission start, real rejoin, 221.7 units
  of actual remote input, stable observation and clean exits. Exact evidence:
  `run/qa-party-final/{party-probe.json,result.json}`.
- The same `a1bbd793` core passed the natural two-player credits→Bastogne route
  again in 97.009 seconds, with both credit displays progressing, normal opening
  scene release, real remote input, zero unexpected native errors and clean exits.
  Immutable proof: `run/mainline-credits-qa/proof-a1bb-PASS/`.
- Core `6cbb0f96` also passed two real checkpoint reloads through the actual
  Co-op Anything `bad_wifi` relay, including advancing peer commands after each,
  real movement and clean shutdown (`run/qa-chaos/`). Its scheduling log records
  184/3079 client-to-server and 238/5412 server-to-client drops, duplication and
  reordered schedules. This tests that particular impaired route; exhaustive
  delayed old-world packets and deliberate loss of every reload control remain open.

## Open acceptance / Offene Abnahme

This development change is NOT a full-campaign certification. Required remaining proof includes:

- Natural full original campaign→credits→UO route, and complete per-mission playthrough coverage.
- Safe group campaign changes with both real processes restarting/rejoining and failure/cancel recovery.
- UF complete terrain-dependent MG use and artillery/airstrike damage.
- All mission objectives/interactions, vehicles, checkpoint/save-load stress and rejoin scenarios.
- Complete real-client network impairment/recovery coverage, including delayed
  old-world packets across checkpoint/map changes. Relay startup alone is not a
  successful gameplay/network test. Initial parent setup attempts were interrupted
  or hit Wine-prefix initialization timeout under concurrent disk load; those
  results remain preserved and are not gameplay PASS evidence.
- Healthy combat AI acquisition, broad NPC/mission coverage and comparative AI
  behavior. The earlier scripted-scene observation is insufficient for this gate;
  static increased ally bravery is not a hit-rate test.
- Film playback and natural completion have targeted runtime proof. Full campaign
  movie/mission coverage and impaired-network delayed-packet behavior remain open.
- The first network handshake must survive blocking cold map loads. A new timer
  resets after a long engine-poll gap; unit cases cover active timeout, a blocked
  load and tick wrap. The original cold-load failure is preserved in AI/movie QA.
- Reproduction/stress verification of upstream UO issue1 `MT_AllocIndex: failed allocation of9206 bytes`.
  Do not add a second free to ordinary UO XAnimFreeTree: native code already calls MT_FreeIndex.
- Actual Windows10/11 hardware, mixed-OS peers, and Steam across separate accounts.
- Final launcher/AppImage/Windows bundles rebuilt after source freeze, fresh platform-specific payloads,
  QA-only script fixtures excluded, all checksums matched. No stable0.6 release before these gates pass.

## Reproduction / Reproduzieren

Tools and evidence / Werkzeuge und Nachweise:

- Native builds: 32-bit MinGW-w64; Python suite tools; PySide6/PyInstaller for
  graphical installers and launchers. Portable Linux builds use a pinned,
  isolated Ubuntu 22.04 container and inspect every bundled ELF's glibc floor.
- Runtime: real game processes under Wine, owned Xvfb displays and separate
  prefixes, logs/state probes/screenshots, plus exact preserved DLL hashes.
  Source copies and QA scripts are separate from the live game installation.
- Co-op Anything: pinned checkout and actual UDP chaos relay used in the
  successful impaired-network smoke above; procedures are adapted to this
  engine rather than counted as gameplay evidence by themselves.
- Native reverse engineering in this iteration uses the existing notes and
  concrete Capstone/objdump instruction evidence. The available REA 6.4 setup
  expects Ghidra 12.1 while this machine has Ghidra 12.2; do not describe these
  new traces as a successful REA/Ghidra execution. Fixing that tool mismatch
  remains separate from the proven binary findings.

See [development commands](development-0.6.md), [campaign compatibility](campaign-compatibility.md),
[YAP notes](yap-compatibility.md) and [launcher](launcher.md).

### Disk hygiene / Platten-Hygiene (binding / verbindlich)

Each QA run creates a full game copy under `run/<tag>/` (host, join1..3,
prefix, runtime). `run/` is gitignored throwaway material, but it grew to
~600 GB and filled the 916 GB volume once. Rules:

- Before every build or QA run: `df -h /mnt/intern-1tb` and
  `home-cleanup --cod-status`. Below 60 GB free: no new run; clean up first.
  Below 20 GB free: emergency prune of old families.
- After every run, in the same session: copy `result.json`, `provenance.json`,
  `*.log`, `tree-watch.json` and `*-proof.json` to `run/<tag>/evidence/`, then
  delete `run/<tag>/{host,join1,join2,join3,prefix,runtime}`. `home-cleanup
  --cod-slim` automates this, but it skips runs younger than 12 h, so a fresh
  run needs the manual step.
- Run names use `run/<family><n>` (`qa-noville-m1-union1` … `union7`); the
  prune groups by the numeric suffix.
- Never delete while a Wine/Xvfb/QA process is active.
- Do not touch `run/<tag>/evidence/`, documented `run/<name>` evidence,
  `run/prepared9-uo/{host-en,joiner-de}`, `game/`, `build/` or `third_party/`
  without asking.

Build/runtime tools are under `tools/`; the source tree has no checked-in game assets.
Use a fresh `tools/stage_suite.py` output after modifying any locked runtime/source files.
For a canonical complete distribution, include base files rather than assuming unrelated starting
installations have identical gameplay PK3s. Never merge Windows/Linux Qt `_internal` trees.
