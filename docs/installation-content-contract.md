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

Current `0.6.0-dev.6` candidates additionally require compiled Core API mask 63;
see [runtime-protocol.md](runtime-protocol.md). A new compiled mask, native
readiness and complete gameplay acceptance remain distinct checks. Historical
AppImages, receipts and test records are not retroactively updated.

The added bit16 is native asset-bootstrap support, not individual UF kit readiness.
Same-protocol API 15 runtimes (including preserved 602/bac candidates) are rejected
before a new staging output is created. Historical artifacts remain unchanged.

Der aktuelle Stand `0.6.0-dev.6` verlangt Maske 63. Bit 16 bestätigt kompilierten
Ressourcen-Bootstrap, keine individuelle Ausrüstungsübernahme. Alte API 15-DLLs
werden trotz gleichem Protokoll vor dem Paketaufbau abgewiesen.


## Owned Coop UI banks / Eigene Coop-Sprachdateien

Dev6 additionally requires Main/localized_english_codcoop_ui.pk3 with exactly
one owned stored STR resource and two approved byte hashes. The immutable EN/DE
copies under coop/languages are individually required and runtime-lock pinned.
New payloads default to English. The English copy is generated from project-owned
strings and added to the canonical English inventory; it is never sought in the
old Ready ZIP. German selection copies the reviewed German bank after original
language installation; English selection restores the English bank. Both paths
use the existing transaction and preserve personal configuration and saves.
Missing, changed or extra-resource banks abort before package installation.
Bit32 LOCALIZED_BANNERS is compiled support, not a claim of full campaign or
individual-equipment readiness. Old API31 DLLs cannot satisfy the new mask63.

Dev6 benötigt die eigene Coop-Sprachdatei und beide unveränderlichen EN-/DE-
Vorlagen. Das neue Paket enthält standardmäßig Englisch. Diese Texte werden
unabhängig vom alten Ready-ZIP erzeugt und in den geprüften englischen Bestand
aufgenommen. Deutsch wird nach dem eigentlichen Spielsprachpaket kopiert.
Reparatur, Update und Rücknahme sichern die vorherige Auswahl; persönliche
Einstellungen und Spielstände bleiben erhalten. Fehlende, veränderte oder um
weitere Ressourcen ergänzte Dateien werden abgewiesen. Der neue Paketstand
verlangt Core-Maske63; ältere API31-DLLs sind dafür unzureichend.
