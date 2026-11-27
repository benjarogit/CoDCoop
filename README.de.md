# Call of Duty Coop

Spielt **Call of Duty** und **United Offensive** mit **2–4 Spielern** unter Windows oder Linux. **SP Improved** und **United Fronts** sind ebenfalls dabei.

[![Windows installieren](https://img.shields.io/badge/Windows-Installieren-005A9C)](#windows-1011-64-bit)
[![Linux installieren](https://img.shields.io/badge/Linux-Installieren-765400)](#linux-x86_64)
[![Aktuelles Release](https://img.shields.io/github/v/release/benjarogit/CoDCoop?label=Release)](https://github.com/benjarogit/CoDCoop/releases/latest)

[Installation](#installation) · [Starten](#codcoop-starten) · [Einrichten](#einrichten) · [Spielen](#gemeinsam-spielen) · [Hilfe](#probleme-beheben) · [English](README.md)

## Installation

Du brauchst eine **vorhandene, vollständige Call-of-Duty-Installation**. Der richtige Spielordner enthält `CoDSP.exe` und den Ordner `Main`. Verwende auf allen Rechnern dasselbe CoDCoop-Release.

### Windows 10/11 (64 Bit)

1. [Windows-Installationspaket herunterladen](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop-Windows-x86_64.zip).
2. Entpacke die ZIP-Datei und öffne `Install-CoD-Coop.exe` im entpackten Ordner.
3. Wähle im Setup deinen **Call-of-Duty-Spielordner**. Danach geht es weiter
   mit [CoDCoop starten](#codcoop-starten).

### Linux (x86_64)

Du brauchst **Wine oder Proton** zum Spielen. Die grafische Installation setzt **glibc 2.35 oder neuer** voraus.

1. Lade **ein AppImage** herunter. Die Suite ist darin enthalten. [Linux-AppImage herunterladen](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop-Linux-x86_64.AppImage)
2. Erlaube das Ausführen in den Dateieigenschaften und öffne die Datei.
3. Wähle im Setup deinen **Call-of-Duty-Spielordner** und installiere.
   Danach geht es weiter mit [CoDCoop starten](#codcoop-starten).

<details>
<summary><strong>AppImage aus dem Terminal öffnen</strong></summary>

Führe im Download-Ordner diese Befehle aus.

```sh
chmod +x Install-CoD-Coop-Linux-x86_64.AppImage
./Install-CoD-Coop-Linux-x86_64.AppImage
```

Bei einem FUSE-Fehler kannst du es so öffnen.

```sh
APPIMAGE_EXTRACT_AND_RUN=1 ./Install-CoD-Coop-Linux-x86_64.AppImage
```

</details>

<details>
<summary><strong>Alternative unter Linux: mit install.sh im Terminal installieren</strong></summary>

Kopiere den Befehl unter **Linux** aus dem [aktuellen Release](https://github.com/benjarogit/CoDCoop/releases/latest#linux). Er speichert das Skript als `install-codcoop.sh`. Das Skript lädt das passende AppImage, prüft SHA-256 und startet das Terminal-Setup. Du brauchst dafür `python3`.

Wenn keine oder mehrere Installationen gefunden werden, gib den Spielordner an. Beispiel für ein deutsches Setup:

```sh
sh ./install-codcoop.sh --game "/Pfad/zu/Call of Duty" --language de
```

</details>

<details>
<summary><strong>Weitere Downloads und vorhandene Spielstände</strong></summary>

- Fehlen United-Offensive-Daten oder passende deutsche Sprachdateien, kann das Setup zusätzliche Dateien herunterladen.
- Das Setup behält deine Spielstände und vorhandenen Einstellungen standardmäßig bei.
- GitHub zeigt die SHA-256-Prüfsumme neben jedem Download. GitHubs **Source code**-Archive enthalten den Quellcode für eigene Builds.

</details>

## CoDCoop starten

Öffne für eine Coop-Partie den **CoDCoop Launcher** aus dem installierten
Spielordner. Die Startdatei öffnet den Launcher mit deinem Spielordner.

- **Windows:** Öffne **CoDCoop** im Spielordner. Das Setup legt die
  Verknüpfung ab Version 0.6.2 an. `Start-CoD-Coop.bat` öffnet den Launcher
  ebenfalls.
- **Linux** verwendet `Start-CoD-Coop.sh`.

<details>
<summary><strong>Was ist mit „Spielen“ in AnkerGames?</strong></summary>

Installiere CoDCoop einmal in den Spielordner, den AnkerGames bereits
verwendet. Wenn **Spielen** dort `CoDSP.exe` startet, öffnet sich die
Originalkampagne. Unter Linux lädt das CoDCoop-Startskript für `umu-run`
die Mod und bereitet das Profil für diese Kampagne automatisch vor.
Steam kann `CoDSP.exe` ebenfalls direkt starten. Sobald eine neuere Version
die Mod lädt, bereitet sie beim Hosten oder Beitreten ein fehlendes oder
unpassendes Kampagnenprofil vor. Wer über den CoDCoop Launcher mitspielt,
wählt **Call of Duty — Original**. Nutzt alle dieselbe CoDCoop-Version.
Für die anderen Kampagnen wählt ihr die passende Variante im Launcher.
[AnkerGames und Proton einrichten](docs/linux.de.md#3-das-spiel-über-den-launcher-starten)

</details>

## Einrichten

Alle wählen **dieselbe Kampagne wie der Host**. Wer über **Spielen** in AnkerGames `CoDSP.exe` startet, spielt **Call of Duty — Original**. Bei Problemen zeigt **Installation prüfen** eure CoDCoop-Version an.

<details>
<summary><strong>Kampagnen und Startoptionen</strong></summary>

| Variante im Launcher | Inhalt |
| --- | --- |
| **CoD + UO — Verbesserter Coop** | Call of Duty mit SP Improved auf der UO-Engine, danach United Offensive |
| **Call of Duty — Original** | Die klassische Kampagne auf der CoD-1.5-Engine |
| **United Offensive — Original** | Die ursprüngliche Erweiterungskampagne mit YAP |
| **United Fronts** | Eigene Missionen, wählbare Kampagnenreihenfolge und Spezialwaffen |

Lasst **Startmission** leer, um im Spiel eine Kampagne zu beginnen oder einen Spielstand zu laden. Der Host wählt den Schwierigkeitsgrad für neue Spiele.

</details>

<details>
<summary><strong>Sprache, Grafik oder das Linux-Startprogramm ändern</strong></summary>

- Starte das Setup erneut, um die Spielsprache zu ändern. Dort stellst du auch
  Spielernamen, Auflösung, Vollbild und Sichtfeld ein. Aktiviere **Vorhandene
  Einstellungen ändern**, wenn deine bisherigen Grafik- und Spielereinstellungen
  ersetzt werden sollen.
- Unter Linux verwendet der Launcher standardmäßig `wine`. Einen anderen
  kompatiblen Startbefehl trägst du unter **Erweiterte Startoptionen → Wine-/Proton-Befehl** ein.
  [Wine und Proton einrichten](docs/linux.de.md#3-das-spiel-über-den-launcher-starten)

</details>

## Gemeinsam spielen

1. Der Host wählt **Spiel hosten** → **Kampagne starten** und öffnet eine Mission oder lädt seinen Spielstand.
2. Die Mitspieler öffnen den CoDCoop Launcher, wählen **Spiel beitreten**, tragen die **Host-Adresse** ein und klicken auf **Kampagne beitreten**.
3. Lasst den Launcher während der Sitzung offen. Der Host bestimmt den gemeinsamen Fortschritt. Spielt später mit demselben Host weiter, um seinen Spielstand fortzusetzen.

Die Verbindungsanleitung erklärt Schritt für Schritt, wie ihr im Heimnetz,
über eine öffentliche IPv4 mit UDP-Portfreigabe, per Steam-Einladung oder per
VPN zusammenspielt.

[Verbindungsanleitung für Windows und Linux](docs/connect.de.md)

<details>
<summary><strong>Kampagne wechseln oder alleine testen</strong></summary>

- **Kampagne wechseln.** Der Host wählt im laufenden Launcher das Ziel und klickt auf **Kampagne wechseln**. Bestätigt den Wechsel und wartet, bis der Launcher den Fortschritt am sicheren Punkt gespeichert und die Gruppe verbunden hat.
- **Alleine testen.** Du kannst eine Mission alleine starten. Automatisierte Coop-Tests nutzen zusätzliche, skriptgesteuerte Spielinstanzen. Einen KI-Partner für einen Coop-Spielerplatz gibt es derzeit nicht.

</details>

## Probleme beheben

| Symptom | Nächster Schritt |
| --- | --- |
| **Windows-Setup findet die Suite nicht** | Prüfe, ob `suite/coop/variants.json` direkt neben der EXE erreichbar ist. Häufig steckt ein zusätzlicher Ordner dazwischen. |
| **Installation prüfen schlägt fehl** | Lies die gemeldete Datei, starte das passende Setup erneut und prüfe danach wieder im Launcher. |
| **Linux startet ohne Coop-Menü oder bricht beim Start ab** | Prüfe, ob Wine/Proton die mitgelieferte `ddraw.dll` lädt. [Linux-Start und Grafik](docs/linux.de.md#1-buffer-overrun-detected-direkt-nach-dem-intro) |
| **Steam zeigt Spacewar, aber die Kampagne ist nicht bereit** | Schließe `CoDMP.exe`, falls es läuft. Öffne den CoDCoop Launcher, wähle die Kampagne des Hosts und klicke auf **Installation prüfen**. `CoDMP.exe` öffnet die klassischen Mehrspielermodi. |
| **Mitspieler kommen nicht rein** | Prüft Paketstand und Host-Adresse. Bei Direkt-IP übers Internet prüft die Weiterleitung von UDP 28960 und die Firewall. Die Meldungen zum Beitritt stehen in `codcoop.log` oder `codcoop_join.log` im Ordner mit `CoDSP.exe`. |
| **United Fronts bricht in Foy oder Noville ab** | Beide Karten können im Standardbetrieb das Modelllimit erreichen. [Bekannte Grenzen und getestete Karten](docs/campaign-compatibility.md) |

<details>
<summary><strong>Rücknahme, Teststand und Entwicklung</strong></summary>

- **Windows:** Im Setup **Letzte Installation zurücknehmen** wählen.
- **Linux:** Den Terminal-Installer mit `--game "/Pfad/zu/Call of Duty" --rollback latest` starten. [Terminal-Optionen](docs/linux.de.md#terminal-setup-mit-installsh)
- In der [Kompatibilitätsübersicht](docs/campaign-compatibility.md) stehen die getesteten Missionen und Mechaniken. Vollständige Kampagnendurchläufe sind noch ungeprüft. Call of Duty 2 ist experimentell.
- [Changelog](CHANGELOG.md) · [Build und Tests](docs/development-0.6.md) · [Projektübergabe](docs/HANDOFF-0.6.md)

</details>

## Mitwirkende und Lizenzen

CoDCoop ist ein [MIT-lizenzierter](LICENSE) Fork von [TheTiranix/CoDCoop](https://github.com/TheTiranix/CoDCoop). Für YAP gelten eine eigene [GPL-3.0-Lizenz](third_party/yap/LICENSE) und [Hinweise zu Quelle und Kompatibilität](docs/yap-compatibility.md). SP Improved und United Fronts stammen von ihren jeweiligen Autoren. Call of Duty gehört Activision, Steam-Komponenten gehören Valve.
