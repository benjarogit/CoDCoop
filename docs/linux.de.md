# CoD Coop unter Linux (Proton / Wine)

[Installation](#0-installation-unter-linux) · [Start und Grafik](#1-buffer-overrun-detected-direkt-nach-dem-intro) · [Steam](#4-steam-einrichten) · [Spieleranleitung](../README.de.md) · [English](linux.md)

CoDCoop verwendet Windows-DLLs. Unter Linux lädt Wine oder Proton das Spiel und
die Mod. Die folgenden Einstellungen stammen aus den Tests mit dieser Umgebung.

| Komponente | Getestete Umgebung |
| --- | --- |
| Launcher | AnkerGames mit `umu-run` und Proton |
| Proton | 11.0 |
| Grafiktreiber | NVIDIA (proprietär) und Mesa (llvmpipe) |
| Spiel | Call of Duty 1.5 und United Offensive 1.51 mit CoDCoop |
| Suite | CoD 1, UO, SP Improved 1.5, United Fronts und YAP |

Wenn du von Steam aus spielst oder einen anderen Launcher verwendest, findest
du die passenden Startoptionen weiter unten.

## 0. Installation unter Linux

Du brauchst eine vollständige Call-of-Duty-Installation. Der Spielordner enthält
`CoDSP.exe`. Zum Spielen brauchst du Wine oder Proton und genügend Speicherplatz
für die Suite und die Sicherungen des Setups.

### Grafisches AppImage

Mache das AppImage ausführbar und öffne es. Wähle im Setup den Spielordner.
Die enthaltene Suite ist bereits ausgewählt. Öffne nach der Installation
`Start-CoD-Coop.sh` im Spielordner.
[AppImage herunterladen](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop-Linux-x86_64.AppImage)

### Terminal-Setup mit install.sh

Lade das Skript aus einem Terminal herunter und starte es. Es benötigt
`python3`, lädt das passende AppImage, prüft dessen SHA-256-Wert und startet
die darin enthaltene Installation im Terminal.

```sh
curl -fsSLo install-codcoop.sh https://raw.githubusercontent.com/benjarogit/CoDCoop/v0.6.3/tools/install.sh && sh ./install-codcoop.sh
```

Wenn das Setup genau eine Installation findet, übernimmt es deren Pfad.
Bei keiner oder mehreren erkannten Installationen gibst du den Spielordner mit
`--game` an. Das Terminal-Setup verwendet standardmäßig Englisch. Für Deutsch
gibst du `--language de` an. Ohne `--yes` fragt es vor der Installation nach.

```sh
# Spielordner angeben und auf Deutsch installieren.
sh ./install-codcoop.sh --game "/Pfad/zu/Call of Duty" --language de

# Installation prüfen oder das letzte abgeschlossene Setup zurücknehmen.
sh ./install-codcoop.sh --game "/Pfad/zu/Call of Duty" --check
sh ./install-codcoop.sh --game "/Pfad/zu/Call of Duty" --rollback latest
```

Mit `--dry-run` kannst du die Installationsschritte vorab prüfen. Das Skript lädt
auch dabei das AppImage herunter und prüft dessen Prüfsumme.

### Zusätzliche Downloads und Sicherungen

Das AppImage enthält SP Improved, United Fronts, YAP und die Coop-Laufzeit.
Fehlt `CoDUOSP.exe`, kann das Setup das festgelegte Archiv mit UO-Spieldaten
laden. Bei einer deutschen Installation kann es auch das festgelegte deutsche
Sprachpaket laden. Für die Coop-Dateien verwendet es die aktuelle Suite.

Das Setup behält vorhandene Einstellungen und Spielstände standardmäßig bei.
Ersetzte Dateien sichert es unter `coop/backups/`.

## 1. „Buffer overrun detected!“ direkt nach dem Intro

**Symptom.** Das Spiel beendet sich vor dem Hauptmenü mit der Meldung
`Buffer overrun detected!` aus der Microsoft-Visual-C++-Laufzeit. Das kann auch
ohne CoDCoop auftreten.

**Ursache.** Die Engine kopiert die Liste der OpenGL-Erweiterungen in einen
Puffer von etwa 8,7 KB. Manche modernen Treiber liefern eine längere Liste.

| Treiber und Einstellung | Länge der OpenGL-Liste |
| --- | --- |
| NVIDIA, unverändert | 11.703 Zeichen, Absturz |
| NVIDIA, `__GL_ExtensionStringVersion=15000` | 3.885 Zeichen, Start erfolgreich |
| Mesa, `MESA_EXTENSION_MAX_YEAR=2015` | 8.475 Zeichen, Start erfolgreich |
| Mesa, `MESA_EXTENSION_MAX_YEAR=2020` | 8.987 Zeichen, Absturz |

Der CoDCoop Launcher setzt die Variablen automatisch. Bei einem manuellen Start
kannst du sie so setzen.

```sh
export __GL_ExtensionStringVersion=15000   # NVIDIA
export MESA_EXTENSION_MAX_YEAR=2003        # Mesa (AMD/Intel)
```

### Einstellungen für Proton dauerhaft übernehmen

Für Launcher, die `umu-run` aufrufen, liefert das Repository ein Startskript
mit. Kopiere es und die Steam-Suche aus dem Quellordner von CoDCoop.

```sh
install -Dm755 tools/umu-run ~/.local/bin/umu-run
install -Dm755 tools/steam-shortcut.py ~/.local/bin/cod-coop-steam-id
```

1. Das Skript setzt die OpenGL-Variablen sowie
   `WINEDLLOVERRIDES="ddraw=n,b"`. Damit lädt Wine die `ddraw.dll` der Mod.
   Ohne diese DLL erscheinen weder der Menüpunkt **Co-op** noch die Datei
   `codcoop.log`. Das Skript übernimmt vorhandene DLL-Overrides.
2. Beim Start von `CoDSP.exe` aus einer vollständigen CoDCoop-Installation prüft
   das Skript die Suite und bereitet das Profil für die Originalkampagne vor.
3. Findet es einen passenden Eintrag als Steam-fremdes Spiel, startet es das
   Spiel über `steam://rungameid/…`. So kann Steam sein Overlay und die
   Freundesliste einblenden. Das Skript wartet bis zum Spielende, damit der
   Launcher den laufenden Prozess weiterhin anzeigt.
4. Ohne passenden Steam-Eintrag startet das Skript das Spiel über
   `umu-run`. Dann steht der Beitritt per IP zur Verfügung.

Wenn dein Launcher einen eigenen `umu-run`-Pfad verwendet, sichere sein
ursprüngliches Startskript, bevor du es ersetzt. Beende und starte den Launcher
anschließend vollständig neu. Schließe dabei auch sein Symbol im Infobereich.

[Startskript `umu-run`](../tools/umu-run) · [Steam-Suche](../tools/steam-shortcut.py)

## 2. Der Launcher meldet geänderte Dateien

Nach der Installation der Mod oder dem Update von `CoDSP.exe` auf 1.5 kann
die Dateiprüfung des Launchers einen Hinweis anzeigen.

![Hinweis des Launchers mit der Schaltfläche zum Behalten der Dateien](screenshots/launcher-keep-files.png)

Klicke auf **Dateien behalten** beziehungsweise **Keep my files**. Die
Reparaturfunktion des Spiele-Launchers stellt die Originaldateien wieder her.
Danach musst du CoDCoop erneut installieren.

## 3. Das Spiel über den Launcher starten

Installiere die vollständige Suite einmal in den vorhandenen Spielordner.
Mit dem Startskript oben öffnet **Spielen** in AnkerGames die Originalkampagne
und bereitet sie für Coop vor. Freunde im CoDCoop Launcher wählen
**Call of Duty — Original**. Für andere Kampagnen wählt ihr dieselbe Variante
im CoDCoop Launcher, geöffnet über `Start-CoD-Coop.sh` unter Linux oder
`Start-CoD-Coop.bat` unter Windows.

Wenn AnkerGames die geänderten Dateien akzeptiert, startet **Spielen** mit
einer kurzen Prüfung. Der Launcher sollte `CoDSP.exe` finden und Proton zum
Starten verwenden.

![Startprüfung des Launchers mit Proton-Unterstützung](screenshots/launcher-starting.png)

| Anzeige | Bedeutung |
| --- | --- |
| Spieldateien, `CoDSP.exe` gefunden | Die Spiel-EXE liegt am erwarteten Ort. |
| Proton oder Wine, mit Proton-Unterstützung | Der Launcher startet das Spiel unter Proton. |
| Cloud-Spielstände, Tarif erforderlich | Coop verwendet lokale Spielstände. |
| `CoDSP.exe` starten, Prozess prüfen | Der Launcher wartet, bis das Spiel läuft. Das kann einige Sekunden dauern. |

Schließt sich das Spiel direkt, prüfe zuerst die
[OpenGL-Einstellungen](#1-buffer-overrun-detected-direkt-nach-dem-intro).

## 4. Steam einrichten

Host und Mitspieler richten Steam jeweils auf ihrem eigenen Rechner ein.

1. Starte Steam und melde dich an. Die Mod verbindet sich mit der laufenden
   Steam-Instanz.
2. Installiere **Spacewar** über `steam://install/480`. Die Mod verwendet
   diese Testanwendung für Steam-Netzwerkverbindungen. Steam kann deshalb
   **Spielt Spacewar** anzeigen.
3. **Unter Linux** braucht das Spiel einen Start über Steam mit Proton, wenn
   du das Overlay oder die Freundesliste nutzen willst. Für die klassische
   Kampagne füge `CoDSP.exe` über **Spiele → Ein Steam-fremdes Spiel meiner
   Bibliothek hinzufügen → Durchsuchen** hinzu. Aktiviere unter
   **Eigenschaften → Kompatibilität** ein Proton-Werkzeug.
   **Unter Windows** kannst du das Spiel normal starten, während Steam läuft.

### Startoptionen für den Steam-Eintrag

Öffne beim Steam-Eintrag **Eigenschaften → Startoptionen** und füge diese Zeile
ein.

```sh
WINEDLLOVERRIDES="ddraw=n,b" __GL_ExtensionStringVersion=15000 MESA_EXTENSION_MAX_YEAR=2003 %command%
```

| Einstellung | Zweck |
| --- | --- |
| `WINEDLLOVERRIDES="ddraw=n,b"` | Lädt die mitgelieferte `ddraw.dll` für CoDCoop. |
| `__GL_ExtensionStringVersion=15000` | Verkürzt die OpenGL-Liste für NVIDIA. |
| `MESA_EXTENSION_MAX_YEAR=2003` | Verkürzt die OpenGL-Liste für Mesa, etwa bei AMD oder Intel. |
| `%command%` | Steam ersetzt den Platzhalter durch den Startbefehl des Spiels. |

**Prüfe den Spielstart.** Sobald die Mod geladen ist, siehst du **Co-op**
im Hauptmenü und `codcoop.log` im Spielordner. Fehlen beide, prüfe zuerst den
DLL-Override. Wenn Steam erreichbar ist, steht im Log eine Zeile wie diese.

```text
steam: listo como 'dein Steam-Name' (7656119...)
```

Bei `steam: no disponible ... solo por IP` prüfe die Anmeldung, die
Spacewar-Installation und den Startweg. Für IP-Verbindungen verwendest du
die Host-Adresse. Bei Direkt-IP übers Internet leitet der Host für CoD 1
und UO standardmäßig **UDP 28960** an seinen Rechner weiter.

### Freundesliste und Overlay bei AnkerGames

Wenn du **Spielt Spacewar** siehst und **Umschalt+Tab** das Overlay nicht öffnet,
prüfe, ob das Spiel durch Steam gestartet wurde. Das Startskript aus
[Abschnitt 1](#1-buffer-overrun-detected-direkt-nach-dem-intro) sucht nach
einem vorhandenen Eintrag für `CoDSP.exe` und kann den Start an Steam
weitergeben. Lege den Eintrag einmal mit Proton und den Startoptionen an
und starte den Launcher danach neu. Die Steam-Suche liest `shortcuts.vdf`.

Alle Spieler brauchen dasselbe CoDCoop-Release. Der Steam-ID-Beitritt unter
0.6.2 mit zwei echten Konten endete in einem Timeout. Direkt-IP zwischen
demselben Linux-Host und der Windows-VM funktionierte. Die
[Verbindungsanleitung](connect.de.md#steam) zeigt den Teststand und die Beitrittswege.

## 5. „Ihr Computer wurde geändert“ beim ersten Start

**Symptom.** Vor dem Hauptmenü erscheint ein kleiner Dialog. Manche
AnkerGames-Installationen zeigen wegen fehlender `Main/localization.txt`
statt der Meldung die Platzhalter `WIN_COMPUTER_CHANGE_TITLE` und
`WIN_COMPUTER_CHANGE_BODY`. Die Schaltflächen heißen **Ja** und **Nein**.

**Ursache.** Call of Duty vergleicht die erkannten Hardwarewerte mit
`sys_cpuMHz`, `sys_sysMB` und `sys_vidMB` aus `Main/config.cfg`. Die
getestete AnkerGames-Installation hatte 1024 MB Videospeicher eingetragen.
Proton meldete 4096 MB. Der Dialog gehört zum Basisspiel.

**Lösung.** Klicke einmal auf **Ja**, damit das Spiel seine aktuellen Werte
speichert. Wenn der Dialog wiederkommt, prüfe die Schreibrechte von
`Main/config.cfg` und verwende für dieselbe Installation denselben Launcher
und Wine- oder Proton-Startweg.

Bei `WIN_CONFIGURE_UPDATED` vergleicht das Spiel `sys_configSum` mit der
Prüfsumme seiner Hardware-Konfiguration. Das Linux-Setup aktualisiert den
Wert beim Anwenden der Spieleinstellungen. Bei einer manuell kopierten
Installation kannst du die Zeile mit `seta sys_configSum` aus der
Konfigurationsdatei entfernen. Das Spiel schreibt sie beim nächsten Start neu.

### Meldung nach einem erzwungenen Beenden

Nach einem Absturz oder dem Abbruch eines Spielprozesses kann beim nächsten
Start `WIN_IMPROPER_QUIT_TITLE` erscheinen. Das laufende Spiel hinterlegt
die Markierungsdatei `__CoDSP` neben `CoDSP.exe` und entfernt sie beim
geordneten Beenden.

| Schaltfläche | Aktion |
| --- | --- |
| **Nein** | Normal starten. Verwende das, wenn nur der letzte Prozess abgebrochen wurde. |
| **Ja** | Im abgesicherten Modus mit Standardwerten für Grafik und Ton starten. |
| **Abbrechen** | Den Spielstart abbrechen. |

## 6. DLLs unter Linux bauen

Zum Bauen brauchst du einen 32-Bit-MinGW-Cross-Compiler.

```sh
sudo apt install g++-mingw-w64-i686
./build.sh
```

Mit `./build.sh --install` kopierst du die DLLs zusätzlich nach `game/`
und baust, soweit möglich, das Menüpaket. `./build.sh --installer` erstellt
auch den Windows-Installer und benötigt alle Ressourcen aus
`installer/installer.rc`. Für Steam braucht der Build die 32-Bit-Version
von Valves `steam_api.dll` im Ordner `build/`. IP-Verbindungen funktionieren
auch ohne diese Datei. [Build und Tests](development-0.6.md)

## 7. Aus dem Quellordner installieren (install-linux.py)

`tools/install-linux.py` ist derselbe Installationskern wie im AppImage.
Er lässt sich mit Python 3 direkt ausführen.

```sh
# Vollständige Suite installieren.
python3 tools/install-linux.py --game "/Pfad/zu/Call of Duty" \
    --suite-source /pfad/zur/suite --yes

# Vorhandene Installation prüfen.
python3 tools/install-linux.py --game "/Pfad/zu/Call of Duty" --check

# Installation vorab prüfen.
python3 tools/install-linux.py --game "/Pfad/zu/Call of Duty" \
    --suite-source /pfad/zur/suite --dry-run
```

Das Verzeichnis für `--suite-source` muss unter anderem `coop/variants.json`
und `coop/launcher/CoD-Coop-Launcher` enthalten. Mit `tools/stage_suite.py`
kannst du die Suite aus einer eigenen Spielinstallation bereitstellen.
`--archive` akzeptiert das festgelegte ältere UO-Basisarchiv. Fehlende Daten
der Originalkampagne meldet das Setup vor dem Schreiben. Ersetzte Dateien
werden unter `coop/backups/` gesichert.

Das AppImage findet seine enthaltene Suite auch bei einem Aufruf mit
`--backend` automatisch. United Offensive kann im Spiel **1.41** anzeigen,
weil die Versionsanzeige fest eingebaut ist. Der Eintrag `ExtVersion=1.51`
in `uo/version.inf` ist für den UO-Paketstand maßgeblich.

## 8. Paketstand vor dem Beitritt prüfen

Klicke bei Host und Mitspielern im CoDCoop Launcher auf **Installation prüfen**.
Vergleicht den angezeigten Paketstand und verwendet dasselbe CoDCoop-Release.
Die Spielsprache und Grafikeinstellungen können sich unterscheiden.
[Gemeinsam spielen](../README.de.md#gemeinsam-spielen)
