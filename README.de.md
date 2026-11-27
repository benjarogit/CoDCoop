# Call of Duty Coop

Spielt **Call of Duty (2003)** und **United Offensive** gemeinsam mit **2–4 Spielern** unter Windows und Linux. SP Improved und United Fronts sind enthalten.

[![Aktuelle Version](https://img.shields.io/github/v/release/benjarogit/CoDCoop?label=Release)](https://github.com/benjarogit/CoDCoop/releases/latest)

[Installieren](#installation) · [Starten](#codcoop-starten) · [Gemeinsam spielen](#gemeinsam-spielen) · [Hilfe](#probleme-beheben) · [Danksagung](#danksagung-und-lizenzen) · [English](README.md)

## Installation

Alle brauchen dieselbe CoDCoop-Version und eine **vollständige Call-of-Duty-Installation**. Wähle im Setup den Ordner, der `CoDSP.exe` und `Main` enthält. Falls du das Spiel schon über Steam oder AnkerGames startest, verwende den Spielordner dieser Installation.

### Windows 10/11 (64 Bit)

1. [Windows-Installationspaket herunterladen](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop-Windows-x86_64.zip).
2. Das komplette ZIP entpacken. Im entpackten Ordner **`Install-CoD-Coop.exe`** öffnen. Der mitgelieferte Ordner `suite` bleibt neben der EXE.
3. Deinen Call-of-Duty-Spielordner auswählen und warten, bis das Setup die Installation geprüft hat.

### Linux (x86_64)

1. [Linux-AppImage herunterladen](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop-Linux-x86_64.AppImage).
2. In den Dateieigenschaften die Ausführung erlauben und das AppImage öffnen. Im Terminal kannst du im Download-Ordner Folgendes ausführen:

   ```sh
   chmod +x Install-CoD-Coop-Linux-x86_64.AppImage
   ./Install-CoD-Coop-Linux-x86_64.AppImage
   ```

3. Deinen Call-of-Duty-Spielordner auswählen und warten, bis das Setup die Installation geprüft hat.

Zum Spielen brauchst du Wine oder Proton. Das grafische Setup benötigt glibc 2.35 oder neuer. [Installation mit `install.sh` im Terminal](docs/linux.de.md#terminal-setup-mit-installsh) · [AppImage bei FUSE-Fehlern öffnen](docs/linux.de.md#grafisches-appimage)

<details>
<summary>Zusätzliche Downloads, Sprache und vorhandene Spielstände</summary>

Das Setup lädt bei Bedarf fehlende United-Offensive-Daten oder das deutsche Sprachpaket. Es behält deine Spielstände und vorhandenen Einstellungen standardmäßig bei. Zum Wechseln der Spielsprache führst du das Setup erneut aus. Wenn du dort den Spielernamen oder die Anzeige ändern möchtest, aktiviere die Option zum Ändern vorhandener Einstellungen.

</details>

## CoDCoop starten

| System | Im installierten Spielordner öffnen |
| --- | --- |
| Windows | Verknüpfung **CoDCoop** oder `Start-CoD-Coop.bat` |
| Linux | `Start-CoD-Coop.sh` |

Im Launcher ist **CoD + UO — Verbesserter Coop** vorausgewählt. Mit **Installation prüfen** überprüfst du die Suite und siehst ihre Version. Lass die Startmission leer, wenn du im Spielmenü eine Mission starten oder laden möchtest.

<details>
<summary>Start über Steam oder AnkerGames und andere Kampagnen auswählen</summary>

Wenn **Spielen** die Datei `CoDSP.exe` öffnet, startet **Call of Duty — Original**. Alle Mitspieler wählen für diese Partie ebenfalls das Original-Profil. Für die kombinierte Standardkampagne nutzt ihr den CoDCoop Launcher. Für Einzelkampagnen öffnet ihr dort die **Erweiterten Startoptionen**. Unter Linux verwendet der Launcher standardmäßig `wine`. Unter **Wine-/Proton-Befehl** lässt sich ein anderer kompatibler Starter hinterlegen. [AnkerGames und Proton einrichten](docs/linux.de.md#3-das-spiel-über-den-launcher-starten) · [Steam-Overlay einrichten](docs/connect.de.md#steam)

</details>

## Gemeinsam spielen

1. Alle öffnen dieselbe Kampagne. Für die erste Partie lasst ihr **CoD + UO — Verbesserter Coop** ausgewählt.
2. Der Host wählt im Launcher **Spiel hosten → Kampagne starten**. Sobald das Spiel offen ist, könnt ihr euch im **Co-op**-Menü in der Lobby treffen oder einer bereits laufenden Mission beitreten.
3. Die Mitspieler folgen dem passenden Verbindungsweg. Lasst den Launcher für automatische Kampagnenwechsel offen.

[Lobby eröffnen oder Mission beitreten](docs/connect.de.md#hosten-und-beitreten) · [Heimnetz](docs/connect.de.md#im-selben-heimnetz) · [Öffentliche IP](docs/connect.de.md#über-das-internet-per-direkt-ip) · [Steam](docs/connect.de.md#steam) · [Tailscale](docs/connect.de.md#über-tailscale)

<details>
<summary>Kampagnenreihenfolge, Spielstände und alleine testen</summary>

**Verbesserter Coop** spielt Call of Duty mit SP Improved und danach United Offensive. Nach dem UO-Abspann kann der Launcher die Gruppe nach United Fronts mitnehmen. Falls der Übergang hängt, wählt der Host **Weiter zu United Fronts**. Mit **Kampagne wechseln** kann der Host im laufenden Launcher auch eine andere Kampagne auswählen. Für die Gruppe gilt der Fortschritt des Hosts. Derselbe Host kann den Spielstand später laden.

Du kannst eine Mission alleine testen. Die Coop-Plätze sind für andere Spieler vorgesehen.

</details>

## Probleme beheben

| Was du siehst | Erster Schritt |
| --- | --- |
| Das Windows-Setup findet die Suite nicht | Das ganze ZIP entpacken. Der entpackte Ordner sollte sowohl `Install-CoD-Coop.exe` als auch `suite/coop/variants.json` enthalten. |
| Der Launcher meldet eine unvollständige Installation | Das passende Setup erneut ausführen und **Installation prüfen** wiederholen. |
| Im Spiel fehlt das **Co-op**-Menü | Über den CoDCoop Launcher starten. Unter Linux prüfen, ob Wine oder Proton die mitgelieferte `ddraw.dll` lädt. [Linux-Hilfe](docs/linux.de.md#1-buffer-overrun-detected-direkt-nach-dem-intro) |
| Steam zeigt **Spacewar**, aber der Mitspieler bleibt im Menü | CoDCoop vor dem Annehmen der Einladung öffnen und auf beiden Rechnern die Kampagne prüfen. [Hilfe zum Beitritt](docs/connect.de.md#probleme-beim-beitritt) |
| United Fronts schließt sich in Foy oder Noville | Diese Karten können das Modelllimit der Engine erreichen. [Bekannte Grenzen](docs/campaign-compatibility.md) |

<details>
<summary>Installation zurücknehmen, getestete Kampagnen und Entwicklung</summary>

- **Windows:** Im Setup **Letzte Installation zurücknehmen** wählen.
- **Linux:** Den Terminal-Installer mit `--game "/Pfad/zu/Call of Duty" --rollback latest` starten. [Terminal-Optionen](docs/linux.de.md#terminal-setup-mit-installsh)
- Vollständige Kampagnendurchläufe stehen noch aus. Die Unterstützung für Call of Duty 2 ist experimentell und liegt außerhalb der Standard-Installer.
- [Getestete Missionen und Kampagnengrenzen](docs/campaign-compatibility.md) · [Änderungsprotokoll](CHANGELOG.md) · [Build und Tests](docs/development-0.6.md) · [Technische Übergabe](docs/HANDOFF-0.6.md)

</details>

## Danksagung und Lizenzen

CoDCoop ist ein [MIT-lizenzierter](LICENSE) Fork von [TheTiranix/CoDCoop](https://github.com/TheTiranix/CoDCoop). SP Improved und United Fronts nennen ihre jeweiligen Urheber. Für YAP gelten eine eigene [GPL-3.0-Lizenz](third_party/yap/LICENSE) und [Hinweise zum Quellcode und zur Kompatibilität](docs/yap-compatibility.md). Call of Duty gehört Activision, die Steam-Komponenten gehören Valve.
