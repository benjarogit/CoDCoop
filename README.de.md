# Call of Duty Coop

Spielt die Kampagnen von Call of Duty und United Offensive mit 2–4 Spielern
unter Windows oder Linux. SP Improved und United Fronts sind ebenfalls dabei.

[English](README.md) · [Aktuelles Release](https://github.com/benjarogit/CoDCoop/releases/latest) · [Changelog](CHANGELOG.md)

## Installation

Du brauchst eine vorhandene, vollständige Call-of-Duty-Installation.
Im Spielordner liegt die Datei `CoDSP.exe`. Verwende Downloads aus demselben Release.

### Windows 10/11 (64 Bit)

1. Lade **beide Dateien** herunter, `Install-CoD-Coop.exe` und das ZIP mit der
   Endung `-suite-windows.zip`. [Windows-Installer](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop.exe) · [Windows-Suite-ZIP unter Assets](https://github.com/benjarogit/CoDCoop/releases/latest#assets)
2. Entpacke das ZIP. Benenne den entpackten Ordner, der direkt `coop` enthält,
   in `suite` um und lege ihn neben `Install-CoD-Coop.exe`.
3. Starte die EXE, wähle deinen vorhandenen **Call-of-Duty-Spielordner** und
   installiere. Das Setup findet den Ordner `suite` automatisch.
4. Öffne danach `Start-CoD-Coop.bat` im Spielordner.

### Linux (x86_64)

1. Lade nur `Install-CoD-Coop-Linux-x86_64.AppImage` herunter. Die Suite steckt
   im AppImage. [Linux-AppImage](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop-Linux-x86_64.AppImage)
2. Erlaube in den Dateieigenschaften das Ausführen und öffne das AppImage.
   Du kannst es auch im Download-Ordner über das Terminal starten.

   ```sh
   chmod +x Install-CoD-Coop-Linux-x86_64.AppImage
   ./Install-CoD-Coop-Linux-x86_64.AppImage
   ```
3. Wähle deinen vorhandenen **Call-of-Duty-Spielordner** und installiere.
   Starte danach `Start-CoD-Coop.sh` im Spielordner.

Das Spiel braucht unter Linux Wine oder Proton. Das grafische Paket setzt
glibc 2.35 oder neuer voraus. Terminal-Setup, Steam, Fehlersuche und Rücknahme
sind in der [Linux-Anleitung](docs/linux.md) beschrieben.

Die zwei **Source code**-Archive auf GitHub sind für den Quellcode-Build.
Mit der optionalen Datei `SHA256SUMS` kannst du die Downloads überprüfen.

## Gemeinsam spielen

1. Öffnet den **CoDCoop Launcher** und wählt eine Kampagne.
2. Eine Person wählt **Hosten** und startet die Mission. Die anderen wählen
   **Beitreten**. Im LAN reicht die lokale IP des Hosts. Direkte IP-Verbindungen
   übers Internet verwenden standardmäßig den UDP-Port `28960`.
3. Installiert auf allen Rechnern dasselbe Suite-Release. Die Spielsprache kann
   sich unterscheiden. Für den gemeinsamen Fortschritt zählt der Spielstand
   des Hosts. Spielt später mit demselben Host weiter.

Steam-Beitritte nutzen Spacewar (AppID 480) und ein eigenes angemeldetes
Steam-Konto pro Spieler. Der Steam-Transport wurde lokal mit einer Ersatz-API
geprüft. Beitritte mit zwei echten Steam-Konten sind noch ungeprüft.
[Steam unter Linux einrichten](docs/linux.md)

## Kampagnen

- **CoD + UO — Verbesserter Coop** ist der empfohlene Einstieg. Spielt die
  erste Kampagne mit SP Improved auf der UO-Engine und danach mit derselben
  Gruppe in UO weiter.
- **Call of Duty Classic** nutzt die originale CoD-1.5-Engine.
- **United Offensive** startet die ursprüngliche Erweiterungskampagne.
- **SP Improved** erweitert das Gameplay der CoD- und UO-Missionen.
- **United Fronts** bietet eigene Missionen, Kampagnenreihenfolgen und
  Ausrüstung. Foy und Noville können im Standardpfad das Limit von
  255 Modellen erreichen.

Die Kampagnenvarianten behalten eigene Spielstände. Call of Duty 2 ist
experimentell. Die [Kompatibilitätsübersicht](docs/campaign-compatibility.md)
nennt die stichprobenartig getesteten Missionen und Mechaniken. Vollständige
Kampagnendurchläufe sind noch ungeprüft.

## Entwicklung

Die [Build- und Testanleitung](docs/development-0.6.md), die
[Projektübergabe](docs/HANDOFF-0.6.md) und das
[zweisprachige Changelog](CHANGELOG.md) dokumentieren den Stand der Releases.

CoDCoop ist ein [MIT-lizenzierter](LICENSE) Fork von
[TheTiranix/CoDCoop](https://github.com/TheTiranix/CoDCoop). Für YAP gelten eine
eigene [GPL-3.0-Lizenz](third_party/yap/LICENSE) und
[Hinweise zu Quelle und Kompatibilität](docs/yap-compatibility.md).
SP Improved und United Fronts stammen von ihren jeweiligen Autoren.
Call of Duty gehört Activision, Steam-Komponenten gehören Valve.
