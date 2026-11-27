# Call of Duty Coop

Play **Call of Duty** and **United Offensive** with **2–4 players** on Windows or Linux. The suite includes **SP Improved** and **United Fronts**.

[![Install on Windows](https://img.shields.io/badge/Windows-Install-005A9C)](#windows-1011-64-bit)
[![Install on Linux](https://img.shields.io/badge/Linux-Install-765400)](#linux-x86_64)
[![Latest release](https://img.shields.io/github/v/release/benjarogit/CoDCoop?label=Release)](https://github.com/benjarogit/CoDCoop/releases/latest)

[Install](#installation) · [Start](#start-codcoop) · [Set up](#setup) · [Play](#play-together) · [Get help](#troubleshooting) · [Deutsch](README.de.md)

## Installation

Start with an **existing, complete Call of Duty installation**. The game folder contains `CoDSP.exe` and the `Main` folder. Use the same CoDCoop release on every machine.

### Windows 10/11 (64-bit)

1. [Download the Windows setup ZIP](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop-Windows-x86_64.zip).
2. Extract the ZIP and open `Install-CoD-Coop.exe` from the extracted folder.
3. In setup, select your **Call of Duty game folder**. After setup, follow the
   [Coop startup steps](#start-codcoop).

### Linux (x86_64)

You need **Wine or Proton** to play. The graphical setup requires **glibc 2.35 or newer**.

1. Download **one AppImage**. It includes the suite. [Download the Linux AppImage](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop-Linux-x86_64.AppImage)
2. Allow execution in the file properties and open the AppImage.
3. Select your **Call of Duty game folder** and install. After setup, follow the
   [Coop startup steps](#start-codcoop).

<details>
<summary><strong>Open the AppImage from a terminal</strong></summary>

Run these commands in the download directory.

```sh
chmod +x Install-CoD-Coop-Linux-x86_64.AppImage
./Install-CoD-Coop-Linux-x86_64.AppImage
```

If you get a FUSE error, run it this way.

```sh
APPIMAGE_EXTRACT_AND_RUN=1 ./Install-CoD-Coop-Linux-x86_64.AppImage
```

</details>

<details>
<summary><strong>Linux alternative: install from the terminal with install.sh</strong></summary>

Copy the command under **Linux** in the [latest release](https://github.com/benjarogit/CoDCoop/releases/latest#linux). It saves the script as `install-codcoop.sh`. The script downloads the matching AppImage, verifies its SHA-256 and starts terminal setup. This method requires `python3`.

If setup finds zero or several installations, give it the game folder.

```sh
sh ./install-codcoop.sh --game "/path/to/Call of Duty"
```

Add `--language de` to install in German.

</details>

<details>
<summary><strong>Additional downloads and existing saves</strong></summary>

- Setup can download additional files if United Offensive data or the selected German language pack is missing.
- Setup keeps your saves and existing settings by default.
- GitHub shows the SHA-256 checksum next to each download. GitHub’s **Source code** archives contain the source for building the mod.

</details>

## Start CoDCoop

For a Coop session, open the **CoDCoop Launcher** from the installed game folder.
The start file opens the launcher and points it to that installation.

- **Windows:** Open **CoDCoop** in the game folder. The setup creates this
  shortcut. `Start-CoD-Coop.bat` also opens the launcher.
- **Linux** uses `Start-CoD-Coop.sh`.

<details>
<summary><strong>What about the Play button in AnkerGames?</strong></summary>

Install CoDCoop once into the game folder AnkerGames already uses. When
**Play** starts `CoDSP.exe`, it opens the original campaign. On Linux,
the CoDCoop wrapper for `umu-run` loads the mod and automatically prepares
that campaign's profile. Steam can also start `CoDSP.exe` directly. When a
newer build loads the mod, the game prepares a missing or mismatched
campaign profile when you host or join. Friends using the CoDCoop Launcher
select **Call of Duty — Original**. Everyone should use the same CoDCoop
version. For other campaigns, select the matching variant in the launcher.
[AnkerGames and Proton setup](docs/linux.md#3-starting-the-game-from-the-launcher)

</details>

## Setup

Everyone selects **the same campaign as the host**. When **Play** in AnkerGames starts `CoDSP.exe`, choose **Call of Duty — Original**. If you run into trouble, **Check installation** shows your CoDCoop version.

<details>
<summary><strong>Campaigns and starting options</strong></summary>

| Launcher variant | What you play |
| --- | --- |
| **CoD + UO — Improved Coop** | Call of Duty with SP Improved on the UO engine, followed by United Offensive |
| **Call of Duty — original** | The classic campaign on the CoD 1.5 engine |
| **United Offensive — original** | The original expansion campaign with YAP |
| **United Fronts** | Its own missions, campaign order options and special weapons |

Leave **Starting mission** blank to start the campaign or load a save in the game. The host chooses the difficulty for new games.

</details>

<details>
<summary><strong>Change language, display or the Linux runner</strong></summary>

- Run setup again to change the game language. In the same setup you can set
  your player name, resolution, fullscreen mode and field of view. To update
  display and player settings in an existing installation, enable the checkbox
  for changing existing settings.
- Under Linux, the launcher uses `wine` by default. To use another compatible
  runner, enter its command under **Advanced launch options → Wine / Proton command**.
  [Wine and Proton setup](docs/linux.md#3-starting-the-game-from-the-launcher)

</details>

## Play together

1. The host selects **Host a game** → **Start campaign** and opens a mission or loads their save.
2. Other players open the CoDCoop Launcher, select **Join a game**, enter the **Host address**, then select **Join campaign**.
3. Keep the launcher open during play. The host's progress is shared with the group. Use the same host to resume their save later.

Use the path that matches your group. The connection guide covers same-network play,
public IPv4 with a UDP port forward, Steam invitations and a VPN fallback.

[Windows and Linux connection guide](docs/connect.md)

<details>
<summary><strong>Switch campaigns or test on your own</strong></summary>

- **Switch campaigns.** The host selects the destination in the active launcher and chooses **Switch campaign**. Confirm and wait while the launcher saves at a safe point and reconnects the group.
- **Test on your own.** You can start a mission solo. Automated Coop tests run extra, scripted game clients. A Coop slot currently has no AI teammate option.

</details>

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| **Windows setup cannot find the suite** | Check that `suite/coop/variants.json` is reachable next to the EXE. Look for an extra directory level after extraction. |
| **Check installation fails** | Read which file the launcher reports, run the matching installer again and repeat the check. |
| **Linux starts without the Coop menu or closes at launch** | Check that Wine or Proton loads the supplied `ddraw.dll`. [Linux launch and graphics fixes](docs/linux.md#1-buffer-overrun-detected-right-after-the-intro) |
| **Steam shows Spacewar but the campaign is not ready** | Close `CoDMP.exe` if you started it. Open the CoDCoop Launcher, select the host's campaign, and run **Check installation**. `CoDMP.exe` opens the standard multiplayer modes. |
| **Players cannot join** | Check the suite version and host address. For direct-IP internet play, check UDP 28960 forwarding and the host’s firewall. Join messages are in `codcoop.log` or `codcoop_join.log` in the folder containing `CoDSP.exe`. |
| **United Fronts closes in Foy or Noville** | Both maps can reach the engine’s model limit in the default configuration. [Known limits and tested maps](docs/campaign-compatibility.md) |

<details>
<summary><strong>Rollback, test coverage and development</strong></summary>

- **Windows:** Select **Roll back last install** in setup.
- **Linux:** Run the terminal installer with `--game "/path/to/Call of Duty" --rollback latest`. [Terminal options](docs/linux.md#terminal-setup-with-installsh)
- The [compatibility guide](docs/campaign-compatibility.md) records tested missions and mechanics. Full campaign playthroughs remain unverified. Call of Duty 2 is experimental.
- [Changelog](CHANGELOG.md) · [Build and test guide](docs/development-0.6.md) · [Implementation handoff](docs/HANDOFF-0.6.md)

</details>

## Credits and licenses

CoDCoop is an [MIT-licensed](LICENSE) fork of [TheTiranix/CoDCoop](https://github.com/TheTiranix/CoDCoop). YAP has its own [GPL-3.0 license](third_party/yap/LICENSE) and [source and compatibility notes](docs/yap-compatibility.md). SP Improved and United Fronts credit their respective authors. Call of Duty belongs to Activision and Steam components belong to Valve.
