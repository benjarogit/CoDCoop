# Changelog · Änderungsprotokoll

[English](#060-development--english) · [Deutsch](#060-entwicklung--deutsch)

## 0.6.0 development — English

**Unreleased. No full-campaign or native-Windows certification yet.**

- Require a complete, pinned set: CoD, UO, SP Improved, United Fronts and YAP.
- Make the recommended CoD→UO mainline use SP Improved's AI/gameplay improvements
  throughout. Preserve the original CoD ending and credits before continuing into
  UO with the same party; start the next mission when the party is ready.
- Add shared variant manifests, local installation receipts and gameplay fingerprints.
- Negotiate engine, protocol, campaign and content before assigning a player slot.
- Separate same-IP joiners with distinct qports; the original SP transport wrote zero.
- Add bounded control-packet writing and complete animation-fragment assembly.
- Load the pinned YAP plugin alongside Coop on UO-based variants; preserve its
  original `DDRAW.dll` basename in a separate plugin directory.
- Build reviewed mod-specific menu and gameplay overlays from the owner's files.
  Preserve each mod's mission selection; adapt United Fronts player mechanics and
  selected original-campaign mission activators for remote players.
- Add supervised campaign-switch preparation, safe-point saving and restart control.
- Add transactional installation, checksum-verified resumable downloads, repair
  preservation and rollback; add graphical Linux setup and launcher sources/builds.
- Add real multi-instance Wine smoke tests with live remote command-clock checks.
- Prevent a waiting joiner's independent world clock from running ahead of the
  host; recover an already advanced world through a normal reload before joining.
- Correct the shared AI melee script to recognize remote players, and bind UF
  mines, ammunition workers and mount bookkeeping to the actual acting player.
- Repair repeated native CoD/UO checkpoint reloads, including absent reliable
  command buffers, world-time rollback and a secondary native simulation path.
  Rearm hooks after mission changes even when the game DLL reuses its address.
- Share original script movies and reconnect through normal world loading;
  carry the confirmed party size through CoD credits into UO mission startup.
- Validate canonical English language packs separately from German overlays;
  preserve existing saves and personal settings across language changes.
- Development protocol7 requires host-owned YAP sprint/jump-shot prediction
  rules before attaching a peer, retries live changes and restores local values
  on leaving. FOV and input preferences remain individual.
- Development `0.6.0-dev.3` uses protocol8: acknowledge mission/checkpoint
  changes by session and generation, retry after packet loss, and acknowledge
  duplicates without starting the same load twice. A real two-second outage
  during a map change now recovers; full delayed-world-packet coverage is open.
- Development `0.6.0-dev.4` uses protocol9: tag native engine and Coop state
  packets with their session and world generation before processing them.
  Preserve readable incompatibility messages for earlier development clients.
- Wait visibly and reconnect through native world loading after a longer link
  outage. Stop old native input sends while rejoining; cancel loading peers
  when the host closes, and invalidate deferred tree indices on disconnect.
- Preserve local archived YAP settings even when quitting directly while joined.
- Correct the native DObj-destruction wrapper's missing stack argument.
- Add individual United Fronts equipment preferences and a validated role/ready
  roster contract. Applying independent kits through the native session remains
  in development; dense-map model/animation memory is an open integration gate.
- Show the verified package version and latest local save per campaign in the
  English/German launcher. Compare extra loaded PK3s even under multiplayer filenames.
- Add English/German documentation and mark CoD 2 experimental.
- Preserve each player's weapon slots, ammunition and active weapon across
  checkpoint loading; issue a fresh mission kit only for a fresh player state.
  Avoid a duplicate weapon drop when cleaning up a player restored from a save.
- Keep the joiner's native input timer running while freezing its independent
  world simulation, restoring keyboard and mouse look between host snapshots.
- Adapt Brecourt's post-goal handoff to a healthy participating player, retaining
  the original one-time objectives and explosives actions. Targeted native tests
  cover all four variants; full mission completion remains open.
- Require the same pinned visual patches in every installation and check native
  Core feature exports before declaring a payload compatible. Preserve nested
  save directories during installation and repair.
- Record actual game exit codes during launcher retries and process transitions;
  a successful supervisor exit alone does not prove successful game shutdown.

Mission-level coverage, Steam across accounts, native Windows and all special
mechanics remain acceptance gates. See [handoff](docs/HANDOFF-0.6.md).

## 0.6.0 Entwicklung — Deutsch

**Noch nicht veröffentlicht. Keine Bestätigung vollständiger Kampagnen oder nativer Windows-Läufe.**

- Vollständiger festgelegter Paketstand: CoD, UO, SP Improved, United Fronts und YAP.
- Empfohlene CoD→UO-Hauptkampagne durchgehend mit KI-/Gameplay-Verbesserungen von
  SP Improved. Ursprünglichen CoD-Abschluss samt Abspann erhalten und anschließend
  mit derselben Gruppe in UO fortfahren; Missionsstart nach Bereitschaft der Gruppe.
- Gemeinsame Variantenmanifeste, Installationsnachweise und Inhaltsprüfsummen.
- Engine, Protokoll, Kampagne und Inhalte vor Zuweisung eines Spielerplatzes prüfen.
- Mitspieler hinter derselben IP durch eigene qports unterscheiden; der SP-Transport
  schrieb ursprünglich immer null.
- Kontrollpakete begrenzen und Animationsteilstücke erst vollständig anwenden.
- Festgelegtes YAP neben Coop in UO-Varianten laden; Originalname `DDRAW.dll` bleibt
  in einem getrennten Plugin-Verzeichnis erhalten.
- Geprüfte Menü- und Gameplay-Anpassungen aus den vorhandenen Mod-Dateien erzeugen.
  Missionsauswahl erhalten, United-Fronts-Spielermechaniken und ausgewählte
  Missionsauslöser der ursprünglichen Kampagne für Mitspieler anpassen.
- Begleiteten Kampagnenwechsel mit Vorbereitung, Speichern am sicheren Punkt und
  Neustartsteuerung ergänzen.
- Installation mit Änderungsjournal, geprüften fortsetzbaren Downloads, Erhalt
  persönlicher Daten und Rücknahme; grafisches Linux-Setup und Launcher ergänzen.
- Echte Wine-Mehrinstanztests mit Prüfung laufender Mitspielerbefehle ergänzen.
- Verhindern, dass die lokale Spielzeit wartender Mitspieler dem Host vorauseilt;
  bereits weitergelaufene Welten vor dem Beitritt über reguläres Neuladen zurücksetzen.
- Gemeinsames KI-Nahkampfsystem auf echte Mitspieler prüfen und UF-Minen,
  Munitionsverwaltung und MG-Verwaltung dem tatsächlich handelnden Spieler zuordnen.
- Wiederholtes echtes Checkpoint-Laden in CoD/UO absichern, einschließlich
  zuverlässiger Befehlsbuffer, rückgesetzter Weltzeit und einer zweiten nativen
  Simulationsschleife. Nach Missionswechseln Hooks auch bei gleicher DLL-Adresse erneuern.
- Originale Skriptfilme gemeinsam abspielen und danach regulär wieder verbinden;
  bestätigte Mitspielerzahl über den CoD-Abspann bis zum UO-Start erhalten.
- Englische Basis-Sprachdateien und deutsche Overlays getrennt prüfen;
  unveränderte Spielstände und Einstellungen bei Sprachwechseln erhalten.
- Entwicklungsprotokoll7 übernimmt YAP-Sprint-/Sprungschuss-Regeln vor dem
  Beitritt vom Host, bestätigt laufende Änderungen und stellt beim Verlassen
  die lokalen Werte wieder her. FOV und Eingabeeinstellungen bleiben individuell.
- Entwicklungsstand `0.6.0-dev.3` verwendet Protokoll8: Missions-/Checkpoint-Wechsel
  anhand von Sitzung und Generation bestätigen, nach Paketverlust wiederholen
  und Duplikate ohne erneutes Laden bestätigen. Ein echter zweisekündiger
  Ausfall beim Kartenwechsel wird aufgefangen; verzögerte Pakete alter Welten
  müssen noch umfassend geprüft werden.
- Entwicklungsstand `0.6.0-dev.4` verwendet Protokoll9: Engine- und Coop-Zustandspakete
  vor der Verarbeitung ihrer Sitzung und Weltgeneration zuordnen. Ältere
  Entwicklungsstände erhalten weiterhin verständliche Inkompatibilitätsmeldungen.
- Nach längerem Verbindungsausfall sichtbar warten und über reguläres Laden
  wieder verbinden. Alte Eingabepakete während des Beitritts sperren, ladende
  Mitspieler beim Beenden des Hosts informieren und zurückgestellte Baumindizes
  beim Trennen verwerfen.
- Persönlich gespeicherte YAP-Werte auch beim direkten Beenden während des
  Beitritts erhalten.
- Fehlendes Stack-Argument im nativen DObj-Aufruf korrigieren.
- Individuelle United-Fronts-Ausrüstungswünsche und einen geprüften Vertrag für
  Rollen und Bereitschaft ergänzen. Die tatsächliche Vergabe über die Sitzung
  ist noch in Arbeit; Modell-/Animationsspeicher auf dichten Karten bleibt offen.
- Geprüften Paketstand und letzten lokalen Spielstand je Kampagne im deutschen
  und englischen Launcher anzeigen. Zusätzliche geladene PK3s auch unter
  Multiplayer-Dateinamen beim Inhaltsvergleich berücksichtigen.
- Englische/deutsche Dokumentation; CoD 2 ausdrücklich experimentell.
- Waffenplätze, Munition und aktive Waffe jedes Spielers beim Checkpoint-Laden
  erhalten; eine neue Missionsausrüstung nur an einen frischen Spielerzustand
  vergeben. Beim Bereinigen geladener Spielerreste keinen Waffenduplikat abwerfen.
- Lokalen Eingabetakt des Mitspielers trotz eingefrorener eigener Weltsimulation
  fortführen, damit Tastatur- und Mausblick zwischen Host-Snapshots funktionieren.
- Brecourts Übergabe nach dem Missionsziel auf einen gesunden beteiligten Spieler
  erweitern; ursprüngliche einmalige Ziele und Sprengstoffaktionen erhalten.
  Gezielte echte Spieltests decken alle vier Varianten ab; der vollständige
  Missionsdurchlauf bleibt offen.
- Dieselben festgelegten Grafikpatches in jeder Installation verlangen und native
  Core-Funktionsexporte vor der Kompatibilitätsbestätigung prüfen. Verschachtelte
  Spielstandverzeichnisse bei Installation und Reparatur erhalten.
- Tatsächliche Spielprozess-Exitcodes bei Launcher-Wiederholungen und Neustarts
  erfassen; ein erfolgreicher Begleitprozess allein belegt kein sauberes Spielende.

Missionsabdeckung, Steam zwischen Accounts, native Windows-Läufe und sämtliche
Spezialmechaniken bleiben Abnahmekriterien. Siehe [Übergabe](docs/HANDOFF-0.6.md).

## Previous release · Vorherige Veröffentlichung

[v0.5.4](https://github.com/benjarogit/CoDCoop/releases/tag/v0.5.4): existing installer
and CoD/UO animation hotfix. Those published assets remain unchanged. / Bestehender
Installer und CoD-/UO-Animationsfix. Veröffentlichte Dateien bleiben unverändert.
