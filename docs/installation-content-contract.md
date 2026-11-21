# Fixed suite content / Einheitlicher Paketstand

Every staged suite, including the online payload without original base-game
packages, includes the reviewed `Main/zzz_patch.pk3` and
`Main/zzzzzzz_kar98k_firing_anim_fix.pk3`. Their hashes and sizes come from
`content/base-packages.json`; both are required by `content/variants.json` and
marked `install_source: suite`. They are package assets, not personal graphics
configuration. Existing user configs and saves retain the normal preservation
rules.

Staging fails on absent/changed sources or disagreement between inventory and
manifest. The GUI and CLI share a backend preflight which rejects a missing or
changed suite-owned patch before any transaction or download. Existing or
embedded SP Improved/United Fronts packages do not bypass this check. The
AppImage packager may omit reviewed original base packages, but never these
required suite patches.

The readonly progress summary includes real `.svg` files in native nested save
folders such as `save/autosave/pathfinder.svg`. Latest names remain relative to
the variant save root. Symlinks and Windows reparse points are not followed.
Save presence/mtime is local metadata, not evidence of a campaign playthrough.

Jeder Paketstand enthält beide geprüften Visual-PK3s, auch ohne optionale
Original-Basispakete. Manifest, Quellenprüfung und Runtime-Lock halten ihren
exakten Stand fest. Fehlende oder veränderte Dateien brechen den Paketbau bzw.
die Installer-Vorprüfung ab; vorhandene Zusatzkampagnen ersetzen diese Prüfung
nicht. Persönliche Einstellungen und Spielstände bleiben geschützt.

Die Fortschrittsanzeige zählt auch echte Autosave-Unterordner. Sie zeigt sichere
relative Dateinamen und Änderungszeiten, folgt aber keinen Symlinks oder
Windows-Reparse-Punkten. Daraus wird kein Kampagnenabschluss abgeleitet.

Current coherent candidates additionally require compiled Core API mask15;
see [runtime-protocol.md](runtime-protocol.md). A new compiled mask, native
readiness and complete gameplay acceptance remain distinct checks. Historical
AppImages, receipts and test records are not retroactively updated.
