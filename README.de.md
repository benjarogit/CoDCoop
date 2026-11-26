# Call of Duty Coop

Spielt **Call of Duty** und **United Offensive** mit **2–4 Spielern** unter Windows oder Linux. **SP Improved** und **United Fronts** sind ebenfalls dabei.

[![Windows installieren](https://img.shields.io/badge/Windows-Installieren-005A9C)](#windows-1011-64-bit)
[![Linux installieren](https://img.shields.io/badge/Linux-Installieren-765400)](#linux-x86_64)
[![Aktuelles Release](https://img.shields.io/github/v/release/benjarogit/CoDCoop?label=Release)](https://github.com/benjarogit/CoDCoop/releases/latest)

[Installation](#installation) · [Einrichten](#einrichten) · [Spielen](#gemeinsam-spielen) · [Hilfe](#probleme-beheben) · [English](README.md)

## Installation

Du brauchst eine **vorhandene, vollständige Call-of-Duty-Installation**. Der richtige Spielordner enthält `CoDSP.exe` und den Ordner `Main`. Verwende auf allen Rechnern dasselbe CoDCoop-Release.

### Windows 10/11 (64 Bit)

1. Lade **beide Dateien** aus demselben Release. [Installer `Install-CoD-Coop.exe`](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop.exe) · [ZIP mit der Endung `-suite-windows.zip`](https://github.com/benjarogit/CoDCoop/releases/latest#assets)
2. Entpacke das ZIP. Benenne den entpackten Ordner, der direkt `coop` enthält, in **`suite`** um und lege ihn neben die EXE.

   ```text
   CoDCoop-Setup/
   ├── Install-CoD-Coop.exe
   └── suite/
       └── coop/
           └── variants.json
   ```

3. Starte die EXE. Wähle im Setup deinen **Call-of-Duty-Spielordner**. Das Setup findet `suite` neben der EXE.
4. Öffne nach der Installation **`Start-CoD-Coop.bat` im Spielordner**.

### Linux (x86_64)

Du brauchst **Wine oder Proton** zum Spielen. Die grafische Installation setzt **glibc 2.35 oder neuer** voraus.

1. Lade **ein AppImage** herunter. Die Suite ist darin enthalten. [Linux-AppImage herunterladen](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop-Linux-x86_64.AppImage)
2. Erlaube das Ausführen in den Dateieigenschaften und öffne die Datei.
3. Wähle im Setup deinen **Call-of-Duty-Spielordner** und installiere. Öffne danach **`Start-CoD-Coop.sh` im Spielordner**.

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
- `SHA256SUMS` ist optional zum Prüfen der Downloads. GitHubs **Source code**-Archive enthalten den Quellcode für eigene Builds.

</details>

## Einrichten

1. Öffne den Launcher über `Start-CoD-Coop.bat` unter Windows oder `Start-CoD-Coop.sh` unter Linux.
2. Klicke auf **Installation prüfen**. Der Launcher zeigt den geprüften Paketstand an. Vergleicht den Stand in der Gruppe.
3. Wähle die **Kampagnenvariante**. Für die erste Runde empfiehlt sich **CoD + UO — Verbesserter Coop**.
4. Lass **Startmission** leer, wenn du die Kampagne im Spiel beginnen oder einen Spielstand fortsetzen willst. Der Host legt den Schwierigkeitsgrad für neue Kampagnen fest. Bestehende Spielstände behalten ihren Schwierigkeitsgrad.

| Variante im Launcher | Inhalt |
| --- | --- |
| **CoD + UO — Verbesserter Coop** | Call of Duty mit SP Improved auf der UO-Engine, danach United Offensive |
| **Call of Duty — Original** | Die klassische Kampagne auf der CoD-1.5-Engine |
| **United Offensive — Original** | Die ursprüngliche Erweiterungskampagne mit YAP |
| **United Fronts** | Eigene Missionen, wählbare Kampagnenreihenfolge und Spezialwaffen |

<details>
<summary><strong>Sprache, Grafik oder das Linux-Startprogramm ändern</strong></summary>

- Starte das Setup erneut, um die Spielsprache zu ändern. Dort stellst du auch
  Spielernamen, Auflösung, Vollbild und Sichtfeld ein. Aktiviere **Vorhandene
  Einstellungen ändern**, wenn deine bisherigen Grafik- und Spielereinstellungen
  ersetzt werden sollen.
- Unter Linux verwendet der Launcher standardmäßig `wine`. Einen anderen
  kompatiblen Startbefehl trägst du unter **Erweiterte Startoptionen → Wine-/Proton-Befehl** ein.
  [Wine und Proton einrichten](docs/linux.md#3-starting-the-game-from-the-launcher)

</details>

## Gemeinsam spielen

1. Der Host wählt **Spiel hosten** → **Kampagne starten** und öffnet eine Mission oder lädt seinen Spielstand.
2. Die Mitspieler wählen **Spiel beitreten**, tragen die **Host-Adresse** ein und klicken auf **Kampagne beitreten**.
3. Lasst den Launcher während der Sitzung offen. Der Host bestimmt den gemeinsamen Fortschritt. Spielt später mit demselben Host weiter, um seinen Spielstand fortzusetzen.

| Verbindung | Was du einträgst |
| --- | --- |
| **LAN** | Lokale IPv4-Adresse des Hosts, zum Beispiel `192.168.1.50` |
| **Direkt-IP übers Internet** | Öffentliche IPv4-Adresse des Hosts. Der Host leitet standardmäßig **UDP 28960** im Router an seinen PC weiter. |
| **Steam** | `steam:<SteamID64>` als Host-Adresse, sobald Steam eingerichtet ist |

<details>
<summary><strong>Steam für Host und Mitspieler einrichten</strong></summary>

1. Alle melden sich mit einem eigenen Steam-Konto an und installieren **Spacewar** über `steam://install/480`.
2. **Windows** kann das Spiel normal starten, während Steam läuft. **Linux** startet das Spiel über einen Steam-Eintrag mit Proton und den nötigen Startoptionen. [Steam-Einrichtung unter Linux](docs/linux.md#4-steam-friend-invites)
3. Nutzt die Steam-ID des Hosts für den Beitritt. Der Steam-Transport wurde mit einer Ersatz-API getestet. Ein Beitritt mit zwei echten Konten ist noch ungeprüft.

</details>

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
| **Linux startet ohne Coop-Menü oder bricht beim Start ab** | Prüfe, ob Wine/Proton die mitgelieferte `ddraw.dll` lädt. [Linux-Start und Grafik](docs/linux.md#1-buffer-overrun-detected-right-after-the-intro) |
| **Mitspieler kommen nicht rein** | Prüft Paketstand, Host-Adresse und die Firewall des Hosts. Bei Direkt-IP übers Internet prüft auch die Weiterleitung von UDP 28960. |
| **United Fronts bricht in Foy oder Noville ab** | Beide Karten können im Standardbetrieb das Modelllimit erreichen. [Bekannte Grenzen und getestete Karten](docs/campaign-compatibility.md) |

<details>
<summary><strong>Rücknahme, Teststand und Entwicklung</strong></summary>

- **Windows:** Im Setup **Letzte Installation zurücknehmen** wählen.
- **Linux:** Den Terminal-Installer mit `--game "/Pfad/zu/Call of Duty" --rollback latest` starten. [Terminal-Optionen](docs/linux.md#terminal-setup-with-installsh)
- In der [Kompatibilitätsübersicht](docs/campaign-compatibility.md) stehen die getesteten Missionen und Mechaniken. Vollständige Kampagnendurchläufe sind noch ungeprüft. Call of Duty 2 ist experimentell.
- [Changelog](CHANGELOG.md) · [Build und Tests](docs/development-0.6.md) · [Projektübergabe](docs/HANDOFF-0.6.md)

</details>

## Mitwirkende und Lizenzen

CoDCoop ist ein [MIT-lizenzierter](LICENSE) Fork von [TheTiranix/CoDCoop](https://github.com/TheTiranix/CoDCoop). Für YAP gelten eine eigene [GPL-3.0-Lizenz](third_party/yap/LICENSE) und [Hinweise zu Quelle und Kompatibilität](docs/yap-compatibility.md). SP Improved und United Fronts stammen von ihren jeweiligen Autoren. Call of Duty gehört Activision, Steam-Komponenten gehören Valve.
