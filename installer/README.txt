CALL OF DUTY COOP — 0.6 DEVELOPMENT / ENTWICKLUNG
English | Deutsch below

This is a development build, not a certified complete campaign release.
CoD 2 is experimental and is not installed by the full CoD 1/UO setup.

The complete suite contains four separate campaign variants:
  Call of Duty (original engine), United Offensive, SP Improved, United Fronts.
YAP and both additional campaign packages are required. The UO Map Pack remains
an optional classic multiplayer addition; it is not a cooperative campaign.
An owned, complete CoD 1 installation is required. The legacy Ready ZIP supplies
UO content and cannot replace missing original CoD campaign packages. A reviewed
local full payload can repair them. Modified or unknown language/extra PK3 files
are compared as gameplay content unless their exact hashes are approved.

Windows 10/11:
  Put the matching Windows suite/ payload next to Install-CoD-Coop.exe and run
  the installer. The payload must include the native Windows campaign launcher.
  Language and personal settings remain local. Existing configs and saves are
  preserved unless changing settings was explicitly selected.

Linux:
  Run Install-CoD-Coop-Linux-x86_64.AppImage and choose the game folder and the
  matching full 0.6 payload. The graphical setup shares the terminal backend.
  Terminal alternative: tools/install.sh --game PATH --suite-source PAYLOAD.

Start-CoD-Coop defaults to the improved CoD 1 campaign, continuing into UO.
Start-CoD-Classic selects the original CoD 1 engine separately.
Start with Start-CoD-Coop or the native campaign launcher. Choose the variant
and host/join there, and keep the launcher open for supervised campaign changes.
All players must have the same complete suite. German and English localization
can differ. Steam joining requires Steam and separate signed-in accounts.

Installers verify pinned content and runtime files before reporting success.
Missing files, an incorrect version or the wrong platform launcher must be
repaired first. Successful installation does not certify campaign playthroughs.
See the bilingual project README and acceptance notes for observed tests.

Rollback on Linux: install-linux.py --game PATH --rollback
Windows: coop\suite-check.exe rollback GAME_FOLDER
Keep the installer's backup files if you want to restore an earlier state.

--------------------------------------------------------------------------
DEUTSCH

Dies ist ein Entwicklungsstand, keine vollstaendig abgenommene Kampagnenversion.
CoD 2 bleibt experimentell und wird vom CoD-1/UO-Komplettsetup nicht installiert.

Das vollstaendige Paket enthaelt vier getrennte Kampagnenvarianten:
  Call of Duty (Original-Engine), United Offensive, SP Improved, United Fronts.
YAP und beide Zusatzvarianten sind erforderlich. Das UO Map Pack bleibt ein
optionaler klassischer Multiplayer-Zusatz und ist keine Coop-Kampagne.
Eine eigene vollstaendige CoD-1-Installation wird vorausgesetzt. Das bisherige
Ready-ZIP liefert UO-Inhalte und ersetzt keine fehlenden Originalkampagnenpakete.
Ein geprueftes lokales Komplettpaket kann sie reparieren. Unbekannte oder geaenderte
Sprach-/Zusatz-PK3s werden ohne ausdruecklich freigegebenen Hash als Spielinhalt
zwischen den Teilnehmern verglichen.

Windows 10/11:
  Das passende Windows-Paket suite/ neben Install-CoD-Coop.exe ablegen und den
  Installer starten. Es muss den nativen Windows-Kampagnenlauncher enthalten.
  Sprache und persoenliche Einstellungen bleiben lokal. Vorhandene Konfiguration
  und Spielstaende bleiben erhalten, ausser Einstellungsänderungen wurden
  ausdruecklich ausgewaehlt.

Linux:
  Install-CoD-Coop-Linux-x86_64.AppImage starten, Spielordner und vollstaendiges
  passendes 0.6-Paket waehlen. Grafikassistent und Terminal nutzen denselben Kern.
  Terminal: tools/install.sh --game PFAD --suite-source PAKETORDNER.

Start-CoD-Coop startet standardmaessig die verbesserte CoD-1-Kampagne mit
anschliessendem UO. Start-CoD-Classic waehlt die originale CoD-1-Engine separat.
Start ueber Start-CoD-Coop oder den nativen Kampagnenlauncher. Dort Variante und
Host/Beitritt waehlen. Fuer gemeinsame Kampagnenwechsel den Launcher offen lassen.
Alle benoetigen denselben vollstaendigen Coop-Stand. Deutsche und englische
Spielsprache duerfen sich unterscheiden. Steam-Beitritt braucht Steam und
getrennte angemeldete Konten.

Der Installer prueft Inhalt und Laufzeitdateien vor einer Erfolgsmeldung.
Fehlende Dateien, falsche Versionen oder ein Launcher fuer das falsche System
muessen zuerst repariert werden. Eine erfolgreiche Installation ist kein
Nachweis eines vollstaendigen Kampagnendurchlaufs. Getestete Faelle stehen in
der zweisprachigen Projektanleitung und den Abnahmenotizen.

Ruecknahme unter Linux: install-linux.py --game PFAD --rollback
Windows: coop\suite-check.exe rollback SPIELORDNER
Die Sicherungsdateien des Installers fuer eine spaetere Wiederherstellung behalten.
