# Gemeinsam verbinden

[English](connect.md) · [Installation](../README.de.md#installation)

1. Startet auf beiden Rechnern den **CoDCoop Launcher** und verwendet dieselbe Mod-Version. Wählt dieselbe Kampagne.
2. Der Host wählt **Spiel hosten → Kampagne starten**, lädt eine Mission und bleibt darin, während der andere beitritt.
3. Der Mitspieler wählt **Spiel beitreten**, trägt die Adresse mit Port ein und klickt **Kampagne beitreten**. Wenn das Spielmenü schon offen ist, geht das auch über **Co-op → Host IP → Join**.

### Vor dem Missionsstart in der Lobby treffen

Öffnet dieselbe Kampagne und wählt im Hauptmenü
**Co-op**. Der Host klickt **Host game**. Die anderen können schon im Menü über
die Host-Adresse oder Steam beitreten. In der Lobby seht ihr, wer angekommen ist.
Der Host geht zurück und startet ein neues Spiel oder lädt einen Spielstand.
Die wartenden Mitspieler folgen automatisch. Der Beitritt zur bereits laufenden
Mission geht weiterhin.

## Im selben Heimnetz

Der Host teilt seine lokale IPv4-Adresse mit Port, etwa `192.168.1.50:28960`. Die Mitspieler tragen diese Adresse ein. Der Standard-Spielport ist **UDP 28960**. Der Host erlaubt eingehendes UDP auf dem Spielport in seiner lokalen Firewall.

## Über das Internet per Direkt-IP

1. Der Host leitet im Router einen externen **UDP-Port** an die lokale IPv4 und den Spielport seines Rechners weiter. In der Host-Firewall muss der interne Spielport erlaubt sein.
2. Der Host ermittelt seine öffentliche IPv4 und teilt sie **mit dem externen Port**. Wenn der Router außen UDP `3202` auf intern `28960` weiterleitet, lautet der Eintrag beispielsweise `203.0.113.42:3202`.
3. Der Mitspieler verwendet diese öffentliche Adresse über einen anderen Internetanschluss. Falls der Anbieter keine eingehende IPv4-Verbindung zulässt, könnt ihr den VPN-Weg verwenden.

## Steam

1. Meldet euch mit je einem Steam-Konto an und aktiviert das Steam-Overlay für den Spieleintrag.
2. Startet den passenden Spieleintrag **über Steam**, wenn ihr das Overlay verwenden wollt. **Original** verwendet `CoDSP.exe`. **Verbesserter Coop** verwendet `CoDUOSP.exe` mit `+set fs_game sp_improved +set coop_mainline 1` in den Startoptionen. Wer über den Steam-Chat annimmt, kann CoDCoop über den Launcher öffnen. Unter Linux braucht der Steam-Eintrag Proton und die CoDCoop-Startoptionen für Grafik und Mod-DLL. [Proton und Steam einrichten](linux.de.md#4-steam-einrichten) · [Valve zum Overlay](https://partner.steamgames.com/doc/features/overlay)
3. Fügt euch als Steam-Freunde hinzu und lasst CoDCoop auf beiden Rechnern offen. Der Host lädt eine Mission, öffnet mit **Umschalt+Tab** die Freundesliste und wählt **Zum Spiel einladen**. Der Mitspieler klickt im Steam-Chat auf **Spiel spielen**. Im Coop-Menü gibt es, falls verfügbar, **Join [Name]**. Der Launcher nimmt auch `steam:<SteamID64>` an.
4. Prüft nach dem Beitritt, ob beide in derselben Mission sind und sich bewegen können. Falls der Mitspieler im Menü bleibt, probiert Direkt-IP oder VPN und sichert die Logs beider Seiten.

**Teststand:** CoDCoop 0.6.3 bestand den Beitritt per Steam-ID mit zwei echten Konten und getauschten Host-Rollen. Linux als Host nutzte Steam Relay, natives Windows als Host Steam-P2P mit ICE. Windows lief in einer VM am selben physischen Internetanschluss. Eine Overlay-Einladung vom Linux-Host kam im Steam-Chat unter Windows an und führte bei bereits geöffnetem CoDCoop in die Mission. Bei geschlossenem CoDCoop kann Steam stattdessen die separate Anwendung Spacewar oder deren Einrichtungsdialog öffnen. Startet zuerst CoDCoop und nehmt dann die Einladung an. Der Test per öffentlicher IPv4 über zwei physische Anschlüsse steht noch aus. Die Anzeige **Spacewar** bestätigt die Steam-Anmeldung des Spiels.

## Über Tailscale

Tailscale gibt jedem Rechner eine private VPN-Adresse. So könnt ihr aus verschiedenen Netzen spielen, ohne den Spielport im Router weiterzuleiten.

1. Installiert Tailscale auf **beiden** Rechnern. Unter Windows öffnet ihr das Tailscale-Symbol im Infobereich und meldet euch an. Unter Linux installiert ihr das Paket für eure Distribution, startet den Tailscale-Dienst und führt `sudo tailscale up` aus. Öffnet danach den Anmeldelink. [Windows-Installation](https://tailscale.com/docs/install/windows) · [Linux-Installation](https://tailscale.com/docs/install/linux)
2. Der Mitspieler muss den Host in Tailscale sehen. Nutzt ein gemeinsames Tailscale-Netz oder gebt nur den Host-Rechner für den Freund frei. Bei einer Gerätefreigabe kann der Empfänger dem freigegebenen Host beitreten. Wenn ihr die Rollen tauscht, gebt auch den neuen Host frei oder nutzt ein gemeinsames Netz. [Geräte freigeben](https://tailscale.com/docs/features/sharing)
3. Der Host öffnet CoDCoop und wählt **Spiel hosten**. Seine Tailscale-IPv4 steht in der Tailscale-App oder unter `tailscale ip -4`. Bei einer Gerätefreigabe kann der Mitspieler die Adresse aus seiner eigenen Tailscale-Geräteliste nehmen. Tragt sie unter **Spiel beitreten** mit dem Spielport ein, etwa `100.64.10.20:28960`. Die Firewall des Hosts und eigene Tailscale-Zugriffsregeln müssen eingehendes Spiel-UDP über Tailscale erlauben.
4. Wenn der Beitritt scheitert, führt der Mitspieler `tailscale ping <Host-Adresse>` aus. Ist der Host darüber erreichbar, prüft Spielport, Firewall und ob CoDCoop hostet. Während des Spiels zeigt `tailscale status` den Weg an. `direct` steht für direkt, `relay` für einen DERP-Relay und `peer-relay` für einen Relay über ein anderes Gerät. Relays können die Verzögerung erhöhen. [Verbindungsarten](https://tailscale.com/docs/reference/connection-types)

Die Portweiterleitung im Router kann geschlossen bleiben. Ihr nutzt das CoDCoop-IP-Feld und braucht dafür keine Steam-Einladung.

Ab CoDCoop 0.6.3 öffnet **P** im laufenden Spiel die Konsole, wenn die Taste noch frei war. Die ursprüngliche Konsolentaste unter **Esc** (auf einer deutschen Tastatur meistens **^**) funktioniert auch im Menü und schließt die Konsole. Aktiviere bei Bedarf **Konsole** in den Spieloptionen. Eine vorhandene Belegung kannst du in der Konsole mit `bind p coopconsole` ändern. Für die Beitrittswege oben reichen Launcher oder Coop-Menü.

Wenn ein Beitritt scheitert, sichert aus dem Spielordner auf beiden Rechnern `codcoop.log` und, soweit vorhanden, `codcoop_join.log`. Gebt Mod-Version, Kampagne und Verbindungsweg an.
