<div align="center">

# Call of Duty Coop

**Die ursprünglichen Kampagnen. Ein gemeinsamer Trupp.**

[![Entwicklung](https://img.shields.io/badge/0.6.0--dev.6-Entwicklung-orange)](#entwicklungsstand)
![Spieler](https://img.shields.io/badge/Spieler-2%E2%80%934-blue)
![Windows-Ziel](https://img.shields.io/badge/Ziel-Windows%2010%20%2F%2011-0078D4)
![Linux](https://img.shields.io/badge/Linux-Wine%20%2F%20Proton-FCC624)
[![Lizenz](https://img.shields.io/badge/CoDCoop-MIT-green)](LICENSE)

[English](README.md) · **Deutsch**

[Installation](#installation) · [Kampagnen](#kampagnen) · [Gemeinsam spielen](#gemeinsam-spielen) · [Entwicklungsstand](#entwicklungsstand) · [Build und Tests](#build-und-tests)

</div>

> **0.6.0-dev.6 ist in Entwicklung.** Dieser Branch setzt die vollständige Coop-Suite um;
> er ist noch keine durchgehend geprüfte Kampagnenveröffentlichung. Das bestehende
> [Release v0.5.4](https://github.com/benjarogit/CoDCoop/releases/tag/v0.5.4)
> entstand vorher und bietet **keinen Coop für SP Improved oder United Fronts**.
> Eine erfolgreiche Installation oder ein kurzer Verbindungstest bestätigt noch
> keine vollständige Kampagne.

Der aktuelle Paketvertrag verlangt die Core-API-Maske 63 einschließlich
des nativen Ressourcen-Bootstraps und lokalisierter Coop-Hinweise. Das aktiviert noch keine individuelle
UF-Ausrüstungsübernahme; deren Gruppen-/Spielanbindung bleibt gesperrt.

## Kampagnen

**Empfohlene Hauptkampagne: CoD + UO — Verbesserter Coop.** Mit der ersten
CoD-Kampagne anfangen, die KI-/Gameplay-Verbesserungen von SP Improved 1.5 nutzen,
die ursprüngliche CoD-Abschlusssequenz sehen und anschließend mit derselben
Gruppe in UO weiterspielen. Dieser Ablauf verwendet durchgehend die UO-Engine;
der Abspann→UO-Übergang hat einen gezielten Test mit zwei echten Spielinstanzen
bestanden. Ein vollständiger Durchspiel-Lauf von Hand ist **kein**
Veröffentlichungskriterium: Die Abdeckung wird kapitelweise festgehalten, und ein
Kapitel ohne aufgezeichnete Stichprobe wird ausdrücklich als nicht abgedeckt
benannt. Klassische Varianten und
United Fronts bleiben zusätzlich auswählbar.


| Variante | Inhalt | Laufzeit |
|---|---|---|
| Call of Duty | Die ursprüngliche Kampagne von 2003 | CoD 1.5 |
| United Offensive | Die ursprüngliche Erweiterungskampagne | UO 1.51 + YAP |
| SP Improved 1.5 | CoD-/UO-Missionen mit Gameplay- und Komfortverbesserungen der Mod | UO + YAP |
| United Fronts 1.1 beta | Original- und Zusatzmissionen, Reihenfolgeoptionen und Spezialwaffen | UO + YAP |

Jede Variante behält ihre eigenen Regeln und Spielstände. Die Mods werden
**nicht zu einer einzigen Mod vermischt**. Auf jedem Coop-Rechner ist derselbe
vollständige, festgelegte Paketstand erforderlich. Sprache, Auflösung und
persönliche Anzeigeeinstellungen bleiben lokal. Deutsche und englische
Spielinstallationen sollen zusammen spielen können. Nicht übersetzte
Zusatzinhalte behalten zunächst ihre Originalsprache.

In UO-basierten Varianten gelten Sprint- und Sprungschuss-Einstellungen des Hosts
auch für die Bewegungsvorhersage der Mitspieler. Beim Verlassen werden deren
vorherige lokale Werte wiederhergestellt. Der Launcher zeigt den geprüften
Paketstand und den letzten lokalen Spielstand je Kampagne; beim Beitritt gilt
immer der Fortschritt des Hosts.

**Call of Duty 2 ist experimentell und nicht Teil des aktuellen Fertigstellungsziels.**
Das UO Map Pack ist ein normaler Multiplayer-Zusatz; seine Karten werden dadurch
nicht zu neuen Coop-Kampagnenmissionen.

## Gemeinsam spielen

Der Host führt die gemeinsame Welt aus: KI, Missionsziele, Skripte und Fortschritt.
Bis zu drei weitere Spieler verbinden sich. Implementiert sind unter anderem
Spielerkörper und Animationen, einstellbares Friendly Fire, Wiederbeleben,
Checkpoint-Wiederherstellung, Missionswechsel und Fahrzeugpassagiere.

Die Arbeit an 0.6 erweitert dieses Verhalten auf die Zusatzvarianten und ihre
Mechaniken. Alle sollen an Missionszielen mitwirken können. Eine exklusive
Fahrzeug- oder Filmsequenzrolle bleibt beim Host; die anderen bekommen passende
Passagier-, Schützen- oder gemeinsame Szenenabläufe. Bis die Missionstests
bestanden sind, ist das ein Entwicklungsziel.

1. **CoDCoop Launcher** starten und eine Kampagnenvariante wählen.
2. Der Host wählt **Hosten** und startet eine Mission. Mitspieler wählen **Beitreten**.
3. Für LAN/direkte IP die Host-Adresse verwenden oder bei erfüllten Voraussetzungen
   über Steam beitreten.
4. Nur der Host wählt eine andere Kampagne. Alle müssen bereit sein; am sicheren
   Punkt wird gespeichert, danach starten die Launcher neu und verbinden erneut.

Die Spielstände gehören dem Host. Zum Fortsetzen dessen Spielstände aufbewahren.
Es gibt keine automatische Hostmigration. Im normalen Spiel pausiert das
Pausenmenü des Hosts die Mitspieler nicht; Start- und Abschlussbildschirme
behalten ihren vorgesehenen Ablauf. Der Host kann außerdem nicht sterben,
solange ein Mitspieler noch die Karte lädt: Ein tödlicher Treffer in diesem
Fenster wird auf 1 Leben geklemmt, damit der Singleplayer-Deathscreen den Server
nicht pausiert und den laufenden Beitritt blockiert.

<details>
<summary>Verbindungsvoraussetzungen</summary>

Direkte IP verwendet standardmäßig **UDP 28960**. Im LAN genügt die lokale
Host-Adresse; über das Internet muss dieser Port zum Host weitergeleitet werden.

Steam verwendet **Spacewar, AppID 480**. Jeder Spieler benötigt einen eigenen
angemeldeten Steam-Account. Unter Linux den beschriebenen Steam-/Proton-Startweg
verwenden: [Linux-Anleitung](docs/linux.md). Zwei lokale IP-Instanzen beweisen
keine funktionierende Steam-Einladung zwischen zwei Rechnern.

</details>

## Installation

**Voraussetzungen:** eine vorhandene Call-of-Duty-Installation, genügend Platz für
UO und alle Zusätze sowie 64-Bit-Windows 10/11 oder x86_64-Linux mit funktionierendem
Wine/Proton. Die grafischen Linux-Pakete benötigen glibc ab 2.35
(Build-Grundlage Ubuntu 22.04). Spieldateien liegen nicht in diesem Quellrepository.

| Plattform | Installationsweg für 0.6 |
|---|---|
| Windows | Grafisches Setup; während der Entwicklung mit vollständigem lokalem Suite-Paket |
| Linux | Grafischer AppImage-Assistent; zusätzlich Terminal-Backend |
| Offline | Derselbe festgelegte Paketstand und die erforderlichen Spieldaten lokal |

Das Setup prüft Inhalts- und Laufzeit-Prüfsummen, erhält persönliche
Konfigurationen und Spielstände bei Reparaturen und erstellt einen
Installationsnachweis. Fehlende oder veränderte Pflichtdateien verhindern eine
erfolgreiche Abschlussprüfung. Sprachwechsel erfolgen ausdrücklich; eine
Reparatur ersetzt Einstellungen nicht stillschweigend.

**Downloadlinks für 0.6 erscheinen erst nach einem tatsächlich gebauten und
veröffentlichten Vorabrelease.** Ein 0.5.4-Installer mit beliebigen neuen DLLs ist
noch keine vollständige Suite. GitHub ist die Hauptquelle; MEGA-Spiegel müssen
dieselbe Version und dieselben Prüfsummen ausweisen.

Lokale Entwicklungspakete und genaue Befehle:
[Entwicklungsinstallation](docs/development-0.6.md).

<details>
<summary>Reparatur, Sicherungen und Rücknahme</summary>

Bei beschädigten Installationen die Prüfung/Reparatur des Setups verwenden.
Auch eine gleich große, aber inhaltlich veränderte Datei wird erkannt.
Installationsversuche führen ein Änderungsjournal und stellen Dateien bei
Fehlern wieder her.

Das Linux-Backend bietet `--rollback latest` oder eine aufgezeichnete
Transaktionskennung. Sicherungen behalten, bis die neue Installation geprüft ist.

</details>

<details>
<summary>Linux-Start und Grafikprobleme</summary>

Wine muss die mitgelieferte `ddraw.dll` durch
`WINEDLLOVERRIDES="ddraw=n,b"` laden. Bei alten OpenGL-Engines können moderne
Erweiterungslisten einen Pufferüberlauf auslösen. Der Launcher setzt
`__GL_ExtensionStringVersion=15000` und `MESA_EXTENSION_MAX_YEAR=2003`.
Weitere Einzelheiten: [Linux / Proton](docs/linux.md).

</details>

## Entwicklungsstand

United Fronts hat weiterhin einen offenen Ressourcenfehler im Standardpfad:
Foy und Noville können beim sauberen Start mit dem vollständigen
Ausrüstungsbestand die 255 Modellplätze der Engine ausschöpfen. Der
experimentelle Pfad mit Registrierung erst bei tatsächlicher Verwendung hat
Vier-Spieler-Ausrüstungen und native Checkpoint-Reloads auf Foy, Noville,
Brecourt, Bastogne1, Afrika2, Dawnville, Pavlov, Arnhem und Pegasusnight bestanden; er ist aber noch nicht der
Produktionsstandard und bestätigt keine vollständigen Missionen. Die Abdeckung
wird jetzt kapitelweise festgehalten; benannte Grenzen stehen pro Karte:
Bizerte lädt kein alliiertes Spielermodell, bei Dawnvilles Gefechtsstart
wird im QA-Join-Fenster nur der Host festgehalten (Liveness-Eingabe, keine
Damage-Aussage), Pavlov verbindet einen im Overlay behobenen Stock-Fehler
der Waffentabelle mit zwei exakt verglichenen, benannten Inhaltswarnungen,
Arnhem brauchte einen Fix für ein Autoren-Präfix plus eine benannte Warnung über
eine fehlende Dekoration, und Pegasusnights Gleiter-Intro gehört dem Host-Körper,
weshalb die Feuerbereitschaft des Hosts in einem begrenzten Pro-Map-Fenster
abgewartet wird. Die signierte Ausrüstungslobby funktioniert in gebauten
Linux- und Windows/Wine-Workern; ihre native Spieler-/Ausrüstungsbindung im
Spiel ist noch nicht fertig.

Für die Veröffentlichung zählt **mindestens eine Stichprobe pro Kapitel und ein
Smoke-Test jeder Variante auf der Zielplattform**, nicht ein vollständiger
Durchspiel-Lauf von Hand. Ein Durchspielen entsteht nur durch stundenlanges
korrektes Spielen; es wird deshalb als *nicht abgedeckt* dokumentiert statt als
offener Blocker geführt. Steam mit zwei getrennten Accounts und die restlichen
Spezialmechaniken bleiben weiterhin offen ausgewiesen.

- [Umsetzungsstand und Übergabe](docs/HANDOFF-0.6.md)
- [Missionsinventar und Kompatibilität](docs/campaign-compatibility.md)
- [YAP-Kompatibilität und festgelegte Quelle](docs/yap-compatibility.md)
- [Englisches/deutsches Changelog](CHANGELOG.md)

Die Tests unterscheiden kurze Verbindungs-/Mechaniktests von tatsächlichen
Missionsabschlüssen. Sie verwenden getrennte Spielkopien und verändern die
Live-Installation nicht. Fehlende Tests bleiben offen; Wine oder ein Screenshot
bestätigen keine andere Plattform und keine vollständige Kampagne.

## Build und Tests

Unter Linux das 32-Bit-MinGW-w64-Werkzeugpaket installieren, danach:

```sh
./build.sh
python3 -m unittest discover -s tests -v
g++ -std=c++17 tests/test_suite_protocol.cpp -o build/test_suite_protocol
./build/test_suite_protocol
```

Die Python-Werkzeuge benötigen Python ab 3.10. Die grafischen
Entwicklungswerkzeuge verwenden PySide6. Befehle für native Prüfer, getrennte
Wine-Tests, Paketbau und AppImage:
[Entwicklungsanleitung](docs/development-0.6.md).

<details>
<summary>Architektur und Analysewerkzeuge</summary>

Der Host führt den eigenen Singleplayer-Server des Spiels aus. Der Loader
verbindet dessen Loopback-Netzwerk mit entfernten Clients und überträgt Zustände,
die das Einzelspiel sonst direkt im Prozessspeicher teilt. Der Kern lässt sich
zur Entwicklung neu laden; unverträglicher Code oder Inhalt verlangt passende
Stände bei allen Teilnehmern.

[Ghidra und REA](https://github.com/morluto/rea) helfen bei konkreten
Engine-Funktionen und Fehlern. [Co-op Anything](https://github.com/cranebeaker/coop-anything)
liefert Test- und Analysemethoden. Ihre Verwendung allein beweist keine
Kompatibilität: Dafür müssen echte Spielinstanzen das Verhalten nachweisen.

Ursprüngliche technische Notizen: [Architektur](notes/ARQUITECTURA.md).

</details>

## Mitwirkende und Lizenzen

Weitergeführter Fork von [TheTiranix/CoDCoop](https://github.com/TheTiranix/CoDCoop).
CoDCoop-Quellcode: [MIT](LICENSE). YAP ist eine separate
[GPL-3.0-Komponente](third_party/yap/LICENSE); Quellstand und Lizenz müssen beim
Paketbau erhalten bleiben. SP Improved, United Fronts und enthaltene
Community-Inhalte bleiben ihren jeweiligen Autoren zugeordnet. Call of Duty
gehört Activision, Steam-Komponenten gehören Valve.
