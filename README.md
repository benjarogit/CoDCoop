# Call of Duty Coop

Play the Call of Duty and United Offensive campaigns with 2–4 players on
Windows or Linux. The suite also includes SP Improved and United Fronts.

[Deutsch](README.de.md) · [Latest release](https://github.com/benjarogit/CoDCoop/releases/latest) · [Changelog](CHANGELOG.md)

## Installation

Start with an existing, complete Call of Duty installation. The game folder
contains `CoDSP.exe`. Use matching downloads from the same release.

### Windows 10/11 (64-bit)

1. Download **both** `Install-CoD-Coop.exe` and the ZIP ending in
   `-suite-windows.zip`. [Windows installer](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop.exe) · [Windows suite ZIP under Assets](https://github.com/benjarogit/CoDCoop/releases/latest#assets)
2. Extract the ZIP. Rename the extracted folder that directly contains
   `coop` to `suite` and put it next to `Install-CoD-Coop.exe`.
3. Run the EXE, select your existing **Call of Duty game folder** and install.
   The installer finds the `suite` folder automatically.
4. Open `Start-CoD-Coop.bat` in the game folder.

### Linux (x86_64)

1. Download just `Install-CoD-Coop-Linux-x86_64.AppImage`. The suite is bundled
   inside it. [Linux AppImage](https://github.com/benjarogit/CoDCoop/releases/latest/download/Install-CoD-Coop-Linux-x86_64.AppImage)
2. In the file properties, allow execution, then open the AppImage. You can
   also run these commands in the download directory.

   ```sh
   chmod +x Install-CoD-Coop-Linux-x86_64.AppImage
   ./Install-CoD-Coop-Linux-x86_64.AppImage
   ```
3. Select your existing **Call of Duty game folder** and install. Then run
   `Start-CoD-Coop.sh` from the game folder.

Linux needs Wine or Proton for the game. The graphical bundle requires glibc
2.35 or newer. You can also use the [terminal installer with `install.sh`](docs/linux.md#terminal-setup-with-installsh).
The [Linux guide](docs/linux.md) covers Steam setup, troubleshooting and rollback.

GitHub lists two **Source code** archives for building from source.
`SHA256SUMS` is optional and lets you check the downloads.

## Play together

1. Open **CoDCoop Launcher** and choose a campaign.
2. One player selects **Host** and starts a mission. Everyone else selects
   **Join**. Use the host's local IP on a LAN. Direct-IP play over the internet
   uses UDP port `28960` by default.
3. Use the same suite release on every machine. Players can use different
   languages. The host's save and mission progress are shared with the group,
   so use the same host to continue later.

Steam joins use Spacewar (AppID 480) and a separate signed-in Steam account
for each player. The Linux guide covers launching through Steam and Proton.
The Steam transport has been tested locally with a stand-in Steam API.
Joins with two real Steam accounts remain untested. [Linux Steam setup](docs/linux.md)

## Campaigns

- **CoD + UO — Improved Coop** is the recommended route. Play the original
  campaign with SP Improved through the UO engine, then continue into UO with
  the same group.
- **Call of Duty Classic** uses the original CoD 1.5 engine.
- **United Offensive** starts the original expansion campaign.
- **SP Improved** adds gameplay improvements to the CoD and UO missions.
- **United Fronts** offers its own missions, campaign order and equipment.
  Foy and Noville can hit the game's 255-model limit on the default path.

The campaign variants keep separate saves. Call of Duty 2 remains experimental.
The [compatibility guide](docs/campaign-compatibility.md) records which missions
and mechanics were sampled. Full campaign playthroughs remain unverified.

## Development

See the [build and test guide](docs/development-0.6.md), the
[implementation handoff](docs/HANDOFF-0.6.md) and the
[bilingual changelog](CHANGELOG.md) for release-specific changes.

CoDCoop is an [MIT-licensed](LICENSE) fork of
[TheTiranix/CoDCoop](https://github.com/TheTiranix/CoDCoop). YAP has its own
[GPL-3.0 license](third_party/yap/LICENSE) and
[source and compatibility notes](docs/yap-compatibility.md). SP Improved and
United Fronts credit their respective authors. Call of Duty belongs to Activision
and Steam components belong to Valve.
