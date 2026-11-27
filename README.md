# Call of Duty Coop

Play **Call of Duty (2003)** and **United Offensive** together with **2–4 players** on Windows and Linux. SP Improved and United Fronts are included.

[![Latest release](https://img.shields.io/github/v/release/benjarogit/CoDCoop?label=Release)](https://github.com/benjarogit/CoDCoop/releases/latest)

[Install](#installation) · [Start](#start-codcoop) · [Play together](#play-together) · [Troubleshooting](#troubleshooting) · [Credits](#credits-and-licenses) · [Deutsch](README.de.md)

## Installation

Everyone needs the same CoDCoop release and a **complete Call of Duty installation**. Select the folder that contains `CoDSP.exe` and `Main` when setup asks for the game folder. Use that same folder if you already start the game through Steam or AnkerGames.

### Windows 10/11 (64-bit)

1. [Download the Windows setup ZIP](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop-Windows-x86_64.zip).
2. Extract the entire ZIP. In the extracted folder, open **`Install-CoD-Coop.exe`**. Leave the included `suite` folder beside it.
3. Select your Call of Duty game folder and wait for setup to verify the installation.

### Linux (x86_64)

1. [Download the Linux AppImage](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop-Linux-x86_64.AppImage).
2. In the file properties, allow execution, then open the AppImage. From a terminal in the download folder, you can run:

   ```sh
   chmod +x Install-CoD-Coop-Linux-x86_64.AppImage
   ./Install-CoD-Coop-Linux-x86_64.AppImage
   ```

3. Select your Call of Duty game folder and wait for setup to verify the installation.

You need Wine or Proton to play. The graphical setup requires glibc 2.35 or newer. [Terminal setup with `install.sh`](docs/linux.md#terminal-setup-with-installsh) · [AppImage FUSE workaround](docs/linux.md#graphical-appimage)

<details>
<summary>Additional downloads, language and existing saves</summary>

Setup may download missing United Offensive data or the German language pack. It preserves your saves and existing settings by default. Run setup again to change the game language. Enable the option to update existing settings if you want to change the player name or display settings during setup.

</details>

## Start CoDCoop

| System | Open from the installed game folder |
| --- | --- |
| Windows | **CoDCoop** shortcut or `Start-CoD-Coop.bat` |
| Linux | `Start-CoD-Coop.sh` |

The launcher starts with **CoD + UO — Improved Coop** selected. Click **Check installation** to verify the suite and see its version. Keep the starting mission blank to start or load a game from the game menu.

<details>
<summary>Starting from Steam or AnkerGames and choosing other campaigns</summary>

If the **Play** button opens `CoDSP.exe`, that starts **Call of Duty — original**. Everyone joining that session should choose the original profile. Use the CoDCoop Launcher for the default combined campaign, or open **Advanced launch options** to choose an individual campaign. On Linux the launcher uses `wine` by default, and you can set a compatible runner under **Wine / Proton command**. [AnkerGames and Proton setup](docs/linux.md#3-starting-the-game-from-the-launcher) · [Steam overlay setup](docs/connect.md#steam)

</details>

## Play together

1. Everyone opens the same campaign. For the first session, keep the default **CoD + UO — Improved Coop**.
2. The host chooses **Host a game → Start campaign** in the launcher. Once the game opens, you can meet in its **Co-op** lobby or join after the host starts a mission.
3. Friends follow the instructions for their connection. Keep the launcher open for automatic campaign changes.

[Host a lobby or join a mission](docs/connect.md#host-and-join) · [Same network](docs/connect.md#on-the-same-home-network) · [Public IP](docs/connect.md#direct-ip-over-the-internet) · [Steam](docs/connect.md#steam) · [Tailscale](docs/connect.md#over-tailscale)

<details>
<summary>Campaign order, saved games and solo testing</summary>

**Improved Coop** runs Call of Duty with SP Improved, followed by United Offensive. After the UO credits, the launcher can take the group into United Fronts. The host can use **Continue to United Fronts** if the transition stalls, or **Switch campaign** to change campaigns from the active launcher. The group uses the host’s progress. Use the same host to load that save later.

You can test a mission alone. Coop teammate slots are for other players.

</details>

## Troubleshooting

| What you see | First step |
| --- | --- |
| Windows setup cannot find the suite | Extract the entire ZIP. The extracted folder should contain both `Install-CoD-Coop.exe` and `suite/coop/variants.json`. |
| The launcher reports an incomplete installation | Run the matching installer again and repeat **Check installation**. |
| The game has no **Co-op** menu | Start with the CoDCoop Launcher. On Linux, check that Wine or Proton loads the supplied `ddraw.dll`. [Linux help](docs/linux.md#1-buffer-overrun-detected-right-after-the-intro) |
| Steam shows **Spacewar** but your friend stays in the menu | Open CoDCoop before accepting the invite and check the campaign on both computers. [Steam and join troubleshooting](docs/connect.md#troubleshoot-a-join) |
| United Fronts closes in Foy or Noville | These maps can reach the engine’s model limit. [Known limits](docs/campaign-compatibility.md) |

<details>
<summary>Rollback, tested campaigns and development</summary>

- **Windows:** Choose **Roll back last install** in setup.
- **Linux:** Run the terminal installer with `--game "/path/to/Call of Duty" --rollback latest`. [Terminal options](docs/linux.md#terminal-setup-with-installsh)
- Full campaign playthroughs remain unverified. Call of Duty 2 support is experimental and outside the standard installers.
- [Tested missions and campaign limits](docs/campaign-compatibility.md) · [Changelog](CHANGELOG.md) · [Build and test guide](docs/development-0.6.md) · [Implementation handoff](docs/HANDOFF-0.6.md)

</details>

## Credits and licenses

CoDCoop is an [MIT-licensed](LICENSE) fork of [TheTiranix/CoDCoop](https://github.com/TheTiranix/CoDCoop). SP Improved and United Fronts credit their respective authors. YAP has its own [GPL-3.0 license](third_party/yap/LICENSE) and [source and compatibility notes](docs/yap-compatibility.md). Call of Duty belongs to Activision and Steam components belong to Valve.
