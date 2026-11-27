# Joining a CoDCoop game

[Deutsch](connect.de.md) · [Installation](../README.md#installation)

1. Open the **CoDCoop Launcher** on both computers and use the same mod release. Use the same campaign on both sides.
2. The host selects **Host a game → Start campaign**, loads a mission, and stays in it while the other player joins.
3. The other player selects **Join a game**, enters the address and port, and selects **Join campaign**. From the game menu, use **Co-op → Host IP → Join**.

### Meet in the in-game lobby

Enter the same campaign on both computers and
open **Co-op** in the main menu. The host chooses **Host game**. The other players
can join with the host address or a Steam join while everyone is still at the
menu. The lobby shows each player as they arrive. The host goes back and starts
a new game or loads a save. The waiting players follow automatically. Players
can still join after the mission has started.

## On the same home network

The host shares their local IPv4 address and port, such as `192.168.1.50:28960`. The other players enter that address. The default game port is **UDP 28960**. The host allows inbound UDP on the game port in their local firewall.

## Direct IP over the internet

1. The host forwards an external **UDP port** on the router to their computer's local IPv4 and game port. The host firewall allows the internal game port.
2. The host looks up their public IPv4 and shares it **with the external port**. For example, if the router forwards external UDP `3202` to internal port `28960`, players enter an address such as `203.0.113.42:3202`.
3. The other player connects to that public address from a different internet connection. If the host's provider cannot accept inbound IPv4 connections, use the VPN path.

## Steam

1. Sign in to separate Steam accounts and enable the Steam overlay for the game entry.
2. Launch the matching game entry **through Steam** to use the overlay. **Original** uses `CoDSP.exe`. **Improved Coop** uses `CoDUOSP.exe` with `+set fs_game sp_improved +set coop_mainline 1` in the launch options. A player accepting through Steam chat can open CoDCoop from its launcher. On Linux the Steam entry needs Proton and the CoDCoop launch options for graphics and the mod DLL. [Set up Proton and Steam](linux.md#4-steam-friend-invites) · [Valve overlay documentation](https://partner.steamgames.com/doc/features/overlay)
3. Add each other as Steam friends and leave CoDCoop open on both computers. The host loads a mission, opens the friends list with **Shift+Tab**, and selects **Invite to Play**. The other player selects **Play Game** in Steam chat. The **Co-op** menu also offers **Join [name]** when available, and the launcher accepts `steam:<SteamID64>`.
4. Verify that both players enter the same mission and can move. If the joiner remains in the menu, try direct IP or a VPN and save the logs from both sides.

**Test status.** CoDCoop 0.6.3 passed direct Steam-ID joins with two real accounts and swapped host roles. The Linux host used Steam Relay, and the native Windows host used Steam P2P with ICE. Windows ran in a VM behind the same physical internet connection. A Linux host also sent an overlay invitation that the Windows player accepted in Steam chat with CoDCoop already running. If CoDCoop is closed, Steam can open the separate Spacewar app or its setup dialog. Open CoDCoop first, then accept the invitation. The public IPv4 test across two physical connections is still pending. The **Spacewar** label confirms the game signed in to Steam.

## Over Tailscale

Tailscale gives each computer a private VPN address. Use it when you're on different networks and want to play without forwarding the game port on your router.

1. Install Tailscale on **both** computers. On Windows, open the Tailscale tray icon and sign in. On Linux, install the package for your distribution, start the Tailscale service and run `sudo tailscale up`. Follow the sign-in link. [Windows installation](https://tailscale.com/docs/install/windows) · [Linux installation](https://tailscale.com/docs/install/linux)
2. Make sure the guest can see the host in Tailscale. Use an existing shared tailnet, or share just the host device with your friend. With a shared device, the recipient can join the sharer's game. To swap host roles, share the new host too or use a joint tailnet. [Device sharing](https://tailscale.com/docs/features/sharing)
3. The host opens CoDCoop and selects **Host game**. Find the host's Tailscale IPv4 in the tray app or run `tailscale ip -4`. For a shared device, the guest can use the address shown in their own Tailscale device list. Enter it with the game port in **Join game**, for example `100.64.10.20:28960`. Allow inbound game UDP on the host's Tailscale connection and in any custom tailnet policy.
4. If joining fails, run `tailscale ping <host-address>` on the guest. If Tailscale can reach the host, check the game port, host firewall and whether CoDCoop is hosting. During play, `tailscale status` shows `direct`, `relay` (DERP), or `peer-relay`. Relays can add latency. [Connection types](https://tailscale.com/docs/reference/connection-types)

You can leave router forwarding for the game port closed. This route uses the CoDCoop IP join field and works without a Steam invitation.

Starting with CoDCoop 0.6.3, press **P** during a match to open the console if the key was free. The original console key below **Esc** (backtick/tilde on US layouts) also works in the menu and closes the console. Enable **Console** in the game options if needed. To change an existing binding, open the console and enter `bind p coopconsole`. The launcher and Co-op menu cover the connection steps above.

For failed joins, save `codcoop.log` and, when present, `codcoop_join.log` from the game folder on both computers. Include the release, campaign, and connection method.
