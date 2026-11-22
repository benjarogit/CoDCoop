#!/usr/bin/env python3
"""Native campaign selector. Validation and game supervision run out of process.

The GUI never constructs engine console commands or starts arbitrary game
executables. coop_session validates and launches registered profiles only.
"""
import argparse
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import sys
import uf_equipment_preferences as equipment
from uf_equipment_roster_view import validate_snapshot as validate_roster_snapshot


TEXT = {
    "en": {
        "title": "Call of Duty Coop", "subtitle": "One campaign. Your whole squad.",
        "folder": "Game folder", "browse": "Browse…", "browse_title": "Choose your complete CoD Coop installation",
        "variant": "Campaign variant", "mode": "Play as", "hosting": "Host a game", "joining": "Join a game",
        "host": "Host address", "host_help": "Use the host's IP address or steam: followed by their Steam ID.",
        "difficulty": "Difficulty", "difficulty_help": "For a new campaign. Saved games keep their own difficulty.",
        "host_difficulty": "The host chooses the difficulty when you join.",
        "difficulty_0": "Recruit", "difficulty_1": "Regular", "difficulty_2": "Hardened", "difficulty_3": "Veteran",
        "campaign_beginning": "Campaign beginning",
        "advanced": "Advanced launch options", "runner": "Wine / Proton command", "map": "Starting mission (optional)",
        "map_help": "Leave blank to select a mission or continue your save in the game.",
        "start": "Start campaign", "join": "Join campaign", "check": "Check installation", "stop": "Leave session",
        "ready": "Choose your campaign and start or join a game.", "checking": "Checking the complete installation…",
        "valid": "Complete installation verified. Ready to play.", "launching": "Starting the campaign…",
        "installed": "Verified suite: {version}", "check_summary": "Check installation to see its version and local saves.",
        "no_saves": "No local saves for this campaign at the last check.",
        "latest_save": "Latest local save: {name} · {modified}",
        "saves_unavailable": "Local save information is unavailable.",
        "host_progress": "When joining, the host's progress applies.",
        "active": "Session running. Keep this window open to follow campaign changes.", "stopping": "Leaving the session…",
        "ended": "Session ended. You can start or join another game.", "failed": "The session could not continue. Read the details, correct the problem and retry.",
        "invalid": "This installation is incomplete or has changed. Run the installer to repair it, then check again.",
        "need_folder": "Choose the game folder first.", "need_host": "Enter the host's address before joining.",
        "details": "Details", "retry": "Retry", "language": "Language", "close_title": "Leave the session?",
        "cancel_check": "Cancel check", "cancelled": "Installation check cancelled.",
        "switch": "Switch campaign", "cancel_switch": "Cancel switch", "switching": "Preparing the campaign change with your squad…",
        "switch_waiting": "Campaign change is waiting. Retry or cancel; your squad stays together.",
        "reconnecting": "Reconnecting to the saved campaign. Wait for your squad, retry this session or leave it.",
        "recovery_waiting": "Reconnection is taking longer than expected. The game stays open. Retry this session or leave; saved progress is kept.",
        "switch_title": "Switch the whole squad?", "switch_message": "Switch everyone to {campaign}?\n\nStarting mission: {mission}\nDifficulty: {difficulty}\n\nProgress is saved at a safe point before the group follows.",
        "close_message": "The game session is still running. Leave it and close this window?",
        "worker_error": "The session helper could not start. Repair the CoD Coop launcher installation.",
        "cod1": "Call of Duty — original", "uo": "United Offensive — original",
        "sp_improved": "CoD + UO — Improved Coop", "united_fronts": "United Fronts",
        "cod1_desc": "Optional classic profile: the original Call of Duty campaign and CoD 1 engine, without SP Improved's changes.",
        "uo_desc": "The United Offensive campaign with YAP improvements and cooperative play.",
        "sp_improved_desc": "Recommended main campaign: CoD 1, its original credits, then United Offensive in the UO engine. Preserves SP Improved 1.5's weapon, balance and AI improvements.",
        "united_fronts_desc": "United Fronts missions, campaign order options and special weapons. Uses the UO engine.",
        "notice": "All players need the complete, matching CoD Coop installation. Local language and graphics can differ.",
    },
    "de": {
        "title": "Call of Duty Coop", "subtitle": "Eine Kampagne. Euer ganzer Trupp.",
        "folder": "Spielordner", "browse": "Durchsuchen…", "browse_title": "Vollständige CoD-Coop-Installation auswählen",
        "variant": "Kampagnenvariante", "mode": "Spielweise", "hosting": "Spiel hosten", "joining": "Spiel beitreten",
        "host": "Host-Adresse", "host_help": "IP-Adresse des Hosts oder steam: mit seiner Steam-ID verwenden.",
        "difficulty": "Schwierigkeit", "difficulty_help": "Für eine neue Kampagne. Spielstände behalten ihre eigene Schwierigkeit.",
        "host_difficulty": "Beim Beitreten bestimmt der Host die Schwierigkeit.",
        "difficulty_0": "Rekrut", "difficulty_1": "Normal", "difficulty_2": "Schwer", "difficulty_3": "Veteran",
        "campaign_beginning": "Kampagnenanfang",
        "advanced": "Erweiterte Startoptionen", "runner": "Wine-/Proton-Befehl", "map": "Startmission (optional)",
        "map_help": "Leer lassen, um im Spiel eine Mission zu wählen oder einen Spielstand fortzusetzen.",
        "start": "Kampagne starten", "join": "Kampagne beitreten", "check": "Installation prüfen", "stop": "Sitzung verlassen",
        "ready": "Kampagne auswählen und ein Spiel starten oder einem Spiel beitreten.", "checking": "Vollständige Installation wird geprüft…",
        "valid": "Vollständige Installation geprüft. Bereit zum Spielen.", "launching": "Kampagne wird gestartet…",
        "installed": "Geprüfter Paketstand: {version}", "check_summary": "Installation prüfen, um Paketstand und lokale Spielstände zu sehen.",
        "no_saves": "Bei der letzten Prüfung keine lokalen Spielstände für diese Kampagne.",
        "latest_save": "Letzter lokaler Spielstand: {name} · {modified}",
        "saves_unavailable": "Lokale Spielstandinformationen sind nicht verfügbar.",
        "host_progress": "Beim Beitritt gilt der Fortschritt des Hosts.",
        "active": "Sitzung läuft. Dieses Fenster für gemeinsame Kampagnenwechsel offen lassen.", "stopping": "Sitzung wird verlassen…",
        "ended": "Sitzung beendet. Du kannst ein weiteres Spiel starten oder einem beitreten.",
        "failed": "Die Sitzung konnte nicht fortgesetzt werden. Details lesen, Ursache beheben und erneut versuchen.",
        "invalid": "Diese Installation ist unvollständig oder wurde verändert. Mit dem Installer reparieren und erneut prüfen.",
        "need_folder": "Zuerst den Spielordner auswählen.", "need_host": "Zum Beitreten zuerst die Host-Adresse eingeben.",
        "details": "Details", "retry": "Erneut versuchen", "language": "Sprache", "close_title": "Sitzung verlassen?",
        "cancel_check": "Prüfung abbrechen", "cancelled": "Installationsprüfung abgebrochen.",
        "switch": "Kampagne wechseln", "cancel_switch": "Wechsel abbrechen", "switching": "Kampagnenwechsel wird mit deinem Trupp vorbereitet…",
        "switch_waiting": "Der Kampagnenwechsel wartet. Erneut versuchen oder abbrechen; dein Trupp bleibt zusammen.",
        "reconnecting": "Verbindung zur gespeicherten Kampagne wird hergestellt. Auf den Trupp warten, diese Sitzung erneut versuchen oder verlassen.",
        "recovery_waiting": "Die Wiederverbindung dauert länger als erwartet. Das Spiel bleibt offen. Diese Sitzung erneut versuchen oder verlassen; der Spielstand bleibt erhalten.",
        "switch_title": "Mit dem ganzen Trupp wechseln?", "switch_message": "Alle zu {campaign} wechseln?\n\nStartmission: {mission}\nSchwierigkeit: {difficulty}\n\nDer Fortschritt wird an einem sicheren Punkt gespeichert, bevor die Gruppe folgt.",
        "close_message": "Die Spielsitzung läuft noch. Verlassen und dieses Fenster schließen?",
        "worker_error": "Die Sitzungshilfe konnte nicht starten. Die CoD-Coop-Launcher-Installation reparieren.",
        "cod1": "Call of Duty — Original", "uo": "United Offensive — Original",
        "sp_improved": "CoD + UO — Verbesserter Coop", "united_fronts": "United Fronts",
        "cod1_desc": "Optionales klassisches Profil: die originale Call-of-Duty-Kampagne und CoD-1-Engine ohne die Änderungen von SP Improved.",
        "uo_desc": "Die United-Offensive-Kampagne mit YAP-Verbesserungen und kooperativem Spiel.",
        "sp_improved_desc": "Empfohlene Hauptkampagne: CoD 1, der Original-Abspann und anschließend United Offensive in der UO-Engine. Waffen-, Balance- und KI-Verbesserungen von SP Improved 1.5 bleiben erhalten.",
        "united_fronts_desc": "United-Fronts-Missionen, wählbare Kampagnenreihenfolge und Spezialwaffen. Verwendet die UO-Engine.",
        "notice": "Alle Spieler brauchen den vollständigen, gleichen CoD-Coop-Stand. Sprache und Grafik dürfen sich unterscheiden.",
    },
}
VARIANTS = ("cod1", "uo", "sp_improved", "united_fronts")

EQUIPMENT_TEXT = {
    'en': {'open': 'Your equipment preferences…', 'title': 'Your United Fronts equipment',
           'scope': 'For your player only. Each teammate chooses independently.',
           'unsupported': 'Preferences only: this build cannot apply individual starting kits. The game keeps its current equipment rules.',
           'mode': 'Equipment mode', 'automatic': 'Automatic — original mission loadout', 'manual': 'Manual — choose four slots',
           'automatic_help': 'The original mission chooses your equipment. Saved manual choices are kept for later.',
           'family': 'Equipment family', 'primary': 'Primary weapon', 'secondary': 'Secondary weapon', 'pistol': 'Pistol / equipment', 'grenade': 'Grenade / equipment',
           'world': 'The host still chooses the world faction, year and campaign order. A personal kit does not change them.',
           'duplicate': 'Choosing the same weapon twice does not create a second copy.',
           'save': 'Save preferences', 'cancel': 'Cancel', 'saved': 'Preferences saved locally. They are not applied by this build.',
           'catalog_error': 'Equipment catalog unavailable. Repair the launcher to edit preferences.',
           'load_error': 'Saved preferences could not be loaded. Choose and save your preferences again.',
           'save_error': 'Could not save equipment preferences. Check access to your user settings folder.',
           'american': 'American', 'british': 'British', 'german': 'German', 'italian': 'Italian', 'russian': 'Russian'},
    'de': {'open': 'Deine Ausrüstungswünsche…', 'title': 'Deine United-Fronts-Ausrüstung',
           'scope': 'Nur für deinen Spieler. Jeder Mitspieler wählt unabhängig.',
           'unsupported': 'Nur Vormerkung: Dieser Stand kann individuelle Startausrüstung noch nicht übernehmen. Im Spiel gelten die bisherigen Ausrüstungsregeln.',
           'mode': 'Ausrüstungsmodus', 'automatic': 'Automatisch — originale Missionsausrüstung', 'manual': 'Manuell — vier Plätze wählen',
           'automatic_help': 'Die originale Mission bestimmt deine Ausrüstung. Manuelle Wünsche bleiben für später gespeichert.',
           'family': 'Ausrüstungsfamilie', 'primary': 'Primärwaffe', 'secondary': 'Sekundärwaffe', 'pistol': 'Pistole / Ausrüstung', 'grenade': 'Granate / Ausrüstung',
           'world': 'Weltfraktion, Jahr und Kampagnenreihenfolge bestimmt weiterhin der Host. Persönliche Ausrüstung ändert sie nicht.',
           'duplicate': 'Dieselbe Waffe in zwei Plätzen erzeugt keine zweite Kopie.',
           'save': 'Wünsche speichern', 'cancel': 'Abbrechen', 'saved': 'Wünsche lokal gespeichert. Dieser Stand übernimmt sie noch nicht ins Spiel.',
           'catalog_error': 'Ausrüstungskatalog fehlt. Zum Bearbeiten den Launcher reparieren.',
           'load_error': 'Gespeicherte Wünsche konnten nicht geladen werden. Bitte erneut wählen und speichern.',
           'save_error': 'Ausrüstungswünsche konnten nicht gespeichert werden. Zugriff auf deinen Einstellungsordner prüfen.',
           'american': 'Amerikanisch', 'british': 'Britisch', 'german': 'Deutsch', 'italian': 'Italienisch', 'russian': 'Russisch'},
}

ROSTER_TEXT = {
    'en': {'open': 'Group choices: {ready}/{total} confirmed…', 'title': 'Group equipment choices',
           'world': 'Mission: {map} · Revision {revision}', 'host': 'Host', 'peer': 'Teammate',
           'member': 'Player {number} · {role} — {ready}', 'yes': 'Selection confirmed', 'no': 'Confirmation pending',
           'UNRESOLVED_AUTOMATIC': 'Waiting for the original automatic equipment to be resolved.',
           'WAITING_RESOURCE_APPROVAL': 'Waiting for equipment resource verification.',
           'WAITING_PARTICIPANTS': 'Waiting for each player to confirm the current choices.',
           'CONTRACT_READY_RUNTIME_UNAVAILABLE': 'All selections confirmed. Equipment application is still unavailable in this build.',
           'notice': 'Read-only group overview. Confirmed choices do not mean that equipment has been applied.',
           'close': 'Close', 'invalid': 'Group information could not be verified. Waiting for a fresh update.'},
    'de': {'open': 'Gruppenwahl: {ready}/{total} bestätigt…', 'title': 'Ausrüstungswahl der Gruppe',
           'world': 'Mission: {map} · Stand {revision}', 'host': 'Host', 'peer': 'Mitspieler',
           'member': 'Spieler {number} · {role} — {ready}', 'yes': 'Auswahl bestätigt', 'no': 'Bestätigung ausstehend',
           'UNRESOLVED_AUTOMATIC': 'Die originale automatische Ausrüstung muss noch ermittelt werden.',
           'WAITING_RESOURCE_APPROVAL': 'Die Ausrüstungsressourcen müssen noch geprüft werden.',
           'WAITING_PARTICIPANTS': 'Jeder Spieler muss die aktuelle Auswahl noch bestätigen.',
           'CONTRACT_READY_RUNTIME_UNAVAILABLE': 'Alle Auswahlen bestätigt. Dieser Stand kann die Ausrüstung weiterhin nicht übernehmen.',
           'notice': 'Schreibgeschützte Gruppenübersicht. Eine bestätigte Auswahl bedeutet noch keine übernommene Ausrüstung.',
           'close': 'Schließen', 'invalid': 'Gruppeninformationen konnten nicht geprüft werden. Ein neuer Stand wird benötigt.'},
}


def load_equipment_catalog():
    sibling = Path(__file__).resolve().with_name('uf_equipment_catalog.json')
    source = sibling if sibling.is_file() else Path(__file__).resolve().parents[1] / 'campaign_patches/uf_equipment_catalog.json'
    path = Path(sys._MEIPASS) / 'uf_equipment_catalog.json' if getattr(sys, 'frozen', False) else source
    catalog = json.loads(path.read_text(encoding='utf-8'))
    for family in equipment.active_families(catalog).values():
        for slot in equipment.SLOTS:
            for choice in family['menu_slots'][slot]['choices'].values():
                equipment.choice_label(choice)
    return catalog


def worker_command(kind, arguments):
    """Use the same dispatch in source and frozen bundles; never invoke a shell."""
    if kind not in {"suite", "session", "party"}:
        raise ValueError("unknown launcher worker")
    if getattr(sys, "frozen", False):
        return [sys.executable, "--internal-command", kind, *arguments]
    name = {"suite": "coop_suite.py", "session": "coop_session.py", "party": "coop_party.py"}[kind]
    return [sys.executable, str(Path(__file__).resolve().with_name(name)), *arguments]


def internal_worker(argv):
    if argv[:1] != ["--internal-command"]:
        return None
    if len(argv) < 2 or argv[1] not in {"suite", "session", "party", "capabilities"}:
        return 2
    # A Windows windowed bundle normally sets sys.std* to None. QProcess still
    # supplies inherited pipes for worker invocations; attach Python streams to
    # those exact handles so validation/status and cooperative stop keep working.
    if getattr(sys, "frozen", False) and os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        for name, number, flags, mode in (("stdin", -10, os.O_RDONLY, "r"),
                                          ("stdout", -11, os.O_WRONLY, "w"),
                                          ("stderr", -12, os.O_WRONLY, "w")):
            if getattr(sys, name) is None:
                handle = kernel.GetStdHandle(number & 0xFFFFFFFF)
                if not handle or handle == ctypes.c_void_p(-1).value:
                    return 2
                fd = msvcrt.open_osfhandle(handle, flags)
                setattr(sys, name, os.fdopen(fd, mode, encoding="utf-8", buffering=1))
    if argv[1]=="capabilities":
        if len(argv)!=2:return 2
        from launcher_provenance import capabilities
        print(json.dumps(capabilities()),flush=True);return 0
    module = importlib.import_module({"suite":"coop_suite", "session":"coop_session", "party":"coop_party"}[argv[1]])
    return module.main(argv[2:])


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    result = internal_worker(argv)
    if result is not None:
        return result
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path)
    parser.add_argument("--language", choices=("en", "de"))
    parser.add_argument("--variant", choices=VARIANTS)
    parser.add_argument("--settings-file", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--smoke-screenshot", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        from PySide6.QtCore import QProcess, QSettings, QTimer, Qt
        from PySide6.QtWidgets import (
            QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
            QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
            QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
            QVBoxLayout, QWidget,
        )
    except ImportError:
        print("PySide6 is required for the source launcher. Use the packaged launcher or install the GUI dependencies.", file=sys.stderr)
        return 2

    class Launcher(QMainWindow):
        def __init__(self):
            super().__init__()
            self.settings = (QSettings(str(args.settings_file), QSettings.Format.IniFormat)
                             if args.settings_file else QSettings("CoDCoop", "Launcher"))
            self.lang = args.language or self.settings.value("language", "en")
            if self.lang not in TEXT:
                self.lang = "en"
            self.busy = False
            self.session = False
            self.stopping = False
            self.close_when_done = False
            self.pending_launch = False
            self.output = ""
            self.event_buffer = ""
            self.active_variant = None
            self.switching = False
            self.recovering = False
            self.status_key = "ready"
            self.verified_summary = None
            self.equipment_path = args.settings_file.with_name('equipment.json') if args.settings_file else equipment.preferences_path()
            self.equipment_catalog = None
            self.equipment_preferences = None
            self.equipment_error = None
            self.authoritative_roster = None
            self.roster_checkpoint = None
            self.roster_unavailable = False
            self.roster_dialog = None
            try:
                self.equipment_catalog = load_equipment_catalog()
                try:
                    self.equipment_preferences = equipment.load_preferences(self.equipment_catalog, self.equipment_path)
                except (OSError, ValueError):
                    self.equipment_error = 'load_error'
                    self.equipment_preferences = equipment.default_preferences(self.equipment_catalog)
            except (OSError, ValueError, KeyError, TypeError):
                self.equipment_error = 'catalog_error'
            self.process = QProcess(self)
            self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.read_output)
            self.process.finished.connect(self.finished)
            self.process.errorOccurred.connect(self.process_error)

            root = QWidget()
            outer = QVBoxLayout(root)
            outer.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
            outer.setContentsMargins(24, 24, 24, 24)
            outer.setSpacing(16)
            head = QHBoxLayout()
            self.title = QLabel()
            self.title.setObjectName("title")
            head.addWidget(self.title, 1)
            self.language_label = QLabel()
            head.addWidget(self.language_label)
            self.language = QComboBox()
            self.language.addItem("English", "en")
            self.language.addItem("Deutsch", "de")
            self.language.setCurrentIndex(0 if self.lang == "en" else 1)
            self.language.currentIndexChanged.connect(self.change_language)
            self.language_label.setBuddy(self.language)
            head.addWidget(self.language)
            outer.addLayout(head)
            self.subtitle = QLabel()
            self.subtitle.setObjectName("subtitle")
            outer.addWidget(self.subtitle)

            form = QFormLayout()
            form.setHorizontalSpacing(16)
            form.setVerticalSpacing(12)
            folder_row = QHBoxLayout()
            default_game = str(args.game or self.settings.value("game", os.environ.get("CODCOOP_GAME", "")))
            self.folder = QLineEdit(default_game)
            self.folder.setMinimumWidth(320)
            self.browse = QPushButton()
            self.browse.clicked.connect(self.browse_folder)
            folder_row.addWidget(self.folder, 1)
            folder_row.addWidget(self.browse)
            self.folder_label = QLabel()
            self.folder_label.setBuddy(self.folder)
            form.addRow(self.folder_label, folder_row)
            outer.addLayout(form)

            campaign_row = QHBoxLayout()
            self.campaigns = QListWidget()
            self.campaigns.setMinimumWidth(220)
            self.campaigns.setMaximumWidth(300)
            self.campaigns.setMinimumHeight(200)
            for variant in VARIANTS:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, variant)
                self.campaigns.addItem(item)
            selected = args.variant or self.settings.value("variant", "sp_improved")
            self.campaigns.setCurrentRow(VARIANTS.index(selected) if selected in VARIANTS else VARIANTS.index("sp_improved"))
            self.campaigns.currentRowChanged.connect(self.campaign_changed)
            campaign_row.addWidget(self.campaigns)
            info = QVBoxLayout()
            self.variant_label = QLabel()
            self.variant_label.setObjectName("variantTitle")
            self.description = QLabel()
            self.description.setWordWrap(True)
            self.description.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.notice = QLabel()
            self.notice.setWordWrap(True)
            self.notice.setObjectName("muted")
            info.addWidget(self.variant_label)
            info.addWidget(self.description)
            self.installation_info = QLabel()
            self.installation_info.setWordWrap(True)
            self.installation_info.setTextFormat(Qt.TextFormat.PlainText)
            self.save_info = QLabel()
            self.save_info.setWordWrap(True)
            self.save_info.setTextFormat(Qt.TextFormat.PlainText)
            self.save_info.setObjectName("muted")
            info.addWidget(self.installation_info)
            info.addWidget(self.save_info)
            self.party_button = QPushButton()
            self.party_button.clicked.connect(self.open_party)
            info.addWidget(self.party_button, 0, Qt.AlignmentFlag.AlignLeft)
            self.equipment_button = QPushButton()
            self.equipment_button.clicked.connect(self.edit_equipment)
            info.addWidget(self.equipment_button, 0, Qt.AlignmentFlag.AlignLeft)
            self.equipment_note = QLabel()
            self.equipment_note.setWordWrap(True)
            self.equipment_note.setObjectName('muted')
            info.addWidget(self.equipment_note)
            self.roster_button = QPushButton()
            self.roster_button.clicked.connect(self.show_authoritative_roster)
            info.addWidget(self.roster_button, 0, Qt.AlignmentFlag.AlignLeft)
            self.roster_note = QLabel()
            self.roster_note.setWordWrap(True)
            info.addWidget(self.roster_note)
            info.addStretch(1)
            info.addWidget(self.notice)
            campaign_row.addLayout(info, 1)
            outer.addLayout(campaign_row)

            options = QFormLayout()
            options.setHorizontalSpacing(16)
            options.setVerticalSpacing(12)
            self.mode_label = QLabel()
            self.mode = QComboBox()
            self.mode.addItem("", "hosting")
            self.mode.addItem("", "joining")
            self.mode.currentIndexChanged.connect(self.mode_changed)
            self.mode_label.setBuddy(self.mode)
            options.addRow(self.mode_label, self.mode)
            self.difficulty_label = QLabel()
            self.difficulty = QComboBox()
            for value in range(4):
                self.difficulty.addItem("", value)
            try:
                difficulty = int(self.settings.value("difficulty", 1))
            except (ValueError, TypeError):
                difficulty = 1
            self.difficulty.setCurrentIndex(difficulty if 0 <= difficulty <= 3 else 1)
            self.difficulty_label.setBuddy(self.difficulty)
            options.addRow(self.difficulty_label, self.difficulty)
            self.difficulty_help = QLabel()
            self.difficulty_help.setWordWrap(True)
            self.difficulty_help.setObjectName("muted")
            options.addRow("", self.difficulty_help)
            self.host_label = QLabel()
            self.host = QLineEdit(self.settings.value("host", ""))
            self.host_label.setBuddy(self.host)
            options.addRow(self.host_label, self.host)
            self.host_help = QLabel()
            self.host_help.setWordWrap(True)
            self.host_help.setObjectName("muted")
            options.addRow("", self.host_help)
            outer.addLayout(options)

            self.advanced_toggle = QPushButton()
            self.advanced_toggle.setCheckable(True)
            self.advanced_toggle.toggled.connect(lambda checked: self.advanced.setVisible(checked))
            outer.addWidget(self.advanced_toggle, 0, Qt.AlignmentFlag.AlignLeft)
            self.advanced = QWidget()
            advanced_form = QFormLayout(self.advanced)
            advanced_form.setContentsMargins(0, 0, 0, 0)
            self.runner_label = QLabel()
            self.runner = QLineEdit(self.settings.value("runner", "wine" if os.name != "nt" else ""))
            self.runner.setEnabled(os.name != "nt")
            self.runner_label.setBuddy(self.runner)
            advanced_form.addRow(self.runner_label, self.runner)
            self.map_label = QLabel()
            self.map = QLineEdit()
            self.map_label.setBuddy(self.map)
            advanced_form.addRow(self.map_label, self.map)
            self.map_help = QLabel()
            self.map_help.setWordWrap(True)
            self.map_help.setObjectName("muted")
            advanced_form.addRow("", self.map_help)
            self.advanced.hide()
            outer.addWidget(self.advanced)

            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            outer.addWidget(line)
            self.status = QLabel()
            self.status.setWordWrap(True)
            outer.addWidget(self.status)
            self.progress = QProgressBar()
            self.progress.setTextVisible(False)
            self.progress.setRange(0, 0)
            self.progress.setFixedHeight(6)
            self.progress.hide()
            outer.addWidget(self.progress)
            self.details_toggle = QPushButton()
            self.details_toggle.setCheckable(True)
            self.details_toggle.toggled.connect(lambda checked: self.details.setVisible(checked))
            outer.addWidget(self.details_toggle, 0, Qt.AlignmentFlag.AlignLeft)
            self.details = QPlainTextEdit()
            self.details.setReadOnly(True)
            self.details.setMaximumBlockCount(2000)
            self.details.setMaximumHeight(180)
            self.details.hide()
            outer.addWidget(self.details)
            actions = QHBoxLayout()
            self.check = QPushButton()
            self.check.clicked.connect(lambda: self.validate(False))
            self.stop = QPushButton()
            self.stop.clicked.connect(self.stop_session)
            self.stop.hide()
            self.switch = QPushButton()
            self.switch.clicked.connect(self.switch_campaign)
            self.switch.hide()
            self.retry_session = QPushButton()
            self.retry_session.clicked.connect(lambda: self.send_control("retry"))
            self.retry_session.hide()
            self.cancel_switch = QPushButton()
            self.cancel_switch.clicked.connect(lambda: self.send_control("cancel"))
            self.cancel_switch.hide()
            self.start = QPushButton()
            self.start.setObjectName("primary")
            self.start.setDefault(True)
            self.start.clicked.connect(lambda: self.validate(True))
            actions.addWidget(self.check)
            actions.addStretch(1)
            actions.addWidget(self.retry_session)
            actions.addWidget(self.cancel_switch)
            actions.addWidget(self.switch)
            actions.addWidget(self.stop)
            actions.addWidget(self.start)
            footer = QWidget()
            actions.setContentsMargins(24, 12, 24, 12)
            footer.setLayout(actions)
            scroll = QScrollArea()
            self.content_scroll = scroll
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(root)
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            container_layout.addWidget(scroll, 1)
            container_layout.addWidget(footer)
            self.setCentralWidget(container)
            self.setMinimumSize(760, 600)
            self.resize(840, 800)
            self.setStyleSheet("""
                QWidget { background: #f4f6f6; color: #202927; font-size: 14px; }
                QLabel#title { font-size: 26px; font-weight: 700; }
                QLabel#subtitle { font-size: 16px; color: #52635e; }
                QLabel#variantTitle { font-size: 19px; font-weight: 600; }
                QLabel#muted { color: #52635e; }
                QLineEdit, QComboBox, QListWidget, QPlainTextEdit {
                    background: #fafbfa; border: 1px solid #b8c5c1; border-radius: 4px; padding: 8px;
                }
                QListWidget::item { padding: 12px 8px; border-radius: 3px; }
                QListWidget::item:selected { background: #d6e5de; color: #1f3d32; }
                QPushButton { border: 1px solid #b8c5c1; border-radius: 4px; padding: 9px 14px; background: #e8eeeb; }
                QPushButton:hover { background: #dce7e1; border-color: #667f73; }
                QPushButton:pressed { background: #d0ded6; }
                QPushButton#primary { background: #315e4e; color: #f4f6f6; border-color: #315e4e; font-weight: 600; }
                QPushButton#primary:hover { background: #264b3d; }
                QPushButton#primary:pressed { background: #1f3d32; }
                QPushButton:disabled { background: #e6ebe8; color: #7a8981; border-color: #cbd5cf; }
                QLineEdit:focus, QComboBox:focus, QPushButton:focus, QListWidget:focus { border: 2px solid #315e4e; }
                QLineEdit:disabled { background: #e9eeeb; color: #697b72; }
                QProgressBar { background: #dce5e0; border: none; }
                QProgressBar::chunk { background: #315e4e; }
            """)
            self.translate()
            self.folder.textChanged.connect(self.folder_changed)
            self.mode_changed()

        def text(self, key):
            return TEXT[self.lang][key]

        def translate(self):
            self.setWindowTitle(self.text("title"))
            self.title.setText(self.text("title"))
            self.subtitle.setText(self.text("subtitle"))
            for name, key in (("folder_label", "folder"), ("browse", "browse"), ("mode_label", "mode"),
                              ("host_label", "host"), ("host_help", "host_help"), ("advanced_toggle", "advanced"),
                              ("runner_label", "runner"), ("map_label", "map"), ("map_help", "map_help"),
                              ("details_toggle", "details"), ("check", "check"), ("stop", "stop"),
                              ("language_label", "language"), ("notice", "notice")):
                getattr(self, name).setText(self.text(key))
            self.switch.setText(self.text("switch"))
            self.retry_session.setText(self.text("retry"))
            self.cancel_switch.setText(self.text("stop" if self.recovering else "cancel_switch"))
            self.campaigns.setAccessibleName(self.text("variant"))
            self.mode.setItemText(0, self.text("hosting"))
            self.mode.setItemText(1, self.text("joining"))
            self.difficulty_label.setText(self.text("difficulty"))
            for value in range(4):
                self.difficulty.setItemText(value, self.text("difficulty_" + str(value)))
            for index, variant in enumerate(VARIANTS):
                self.campaigns.item(index).setText(self.text(variant))
                self.campaigns.item(index).setToolTip(self.text(variant) + "\n" + self.text(variant + "_desc"))
            self.campaign_changed()
            self.mode_changed()
            self.set_status(self.status_key)

        def change_language(self):
            self.lang = self.language.currentData()
            self.translate()

        def campaign_changed(self):
            variant = self.campaigns.currentItem().data(Qt.ItemDataRole.UserRole)
            self.variant_label.setText(self.text(variant))
            self.description.setText(self.text(variant + "_desc"))
            self.refresh_installation_info()
            self.refresh_equipment()
            if hasattr(self, "switch"):
                self.switch.setEnabled(self.session and not self.switching and variant != self.active_variant)

        def mode_changed(self):
            joining = self.mode.currentData() == "joining"
            self.host.setEnabled(joining and not self.busy)
            self.host_label.setEnabled(joining)
            self.host_help.setVisible(joining)
            self.difficulty.setEnabled(not joining and (not self.busy or (self.session and not self.switching)))
            self.difficulty_label.setEnabled(not joining)
            self.difficulty_help.setText(self.text("host_difficulty" if joining else "difficulty_help"))
            self.map.setEnabled(not joining and (not self.busy or (self.session and not self.switching)))
            self.start.setText(self.text("join" if joining else "start"))
            self.refresh_installation_info()

        def refresh_equipment(self):
            if not hasattr(self, 'equipment_button'):
                return
            words = EQUIPMENT_TEXT[self.lang]
            visible = self.campaigns.currentItem().data(Qt.ItemDataRole.UserRole) == 'united_fronts'
            self.party_button.setText('Group lobby…' if self.lang == 'en' else 'Gruppen-Lobby…')
            self.party_button.setVisible(visible)
            self.party_button.setEnabled(not self.busy and self.equipment_catalog is not None)
            self.equipment_button.setText(words['open'])
            self.equipment_button.setVisible(visible)
            self.equipment_button.setEnabled(not self.busy and self.equipment_catalog is not None)
            self.equipment_note.setVisible(visible)
            self.equipment_note.setText(words[self.equipment_error] if self.equipment_error else words['unsupported'])
            roster = self.authoritative_roster
            self.roster_button.setVisible(visible and roster is not None)
            if roster:
                self.roster_button.setText(ROSTER_TEXT[self.lang]['open'].format(
                    ready=sum(member['ready'] for member in roster['members']), total=len(roster['members'])))
            self.roster_note.setVisible(visible and self.roster_unavailable)
            self.roster_note.setText(ROSTER_TEXT[self.lang]['invalid'])

        def open_party(self):
            if self.busy or self.equipment_catalog is None or not self.folder.text().strip():
                return
            if getattr(self, 'party_dialog', None) is not None:
                self.party_dialog.show(); self.party_dialog.raise_(); return
            from party_gui import create_dialog
            dialog = create_dialog(self, language=self.lang, game=Path(self.folder.text().strip()),
                map_name=self.map.text().strip() or 'pathfinder', difficulty=self.difficulty.currentData(),
                preferences=lambda: self.equipment_preferences, command_factory=worker_command,
                settings_directory=self.equipment_path.parent / 'party-invitations')
            self.party_dialog = dialog
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.finished.connect(lambda: setattr(self, 'party_dialog', None))
            dialog.show()  # independent worker survives owned native restarts

        def present_authoritative_roster(self, snapshot, native_capability):
            """Future trusted-controller seam; deliberately not a stdout handler.

            The controller must authenticate origin/owner acknowledgments and
            verify the authoritative plan before calling this presentation API.
            This method never sends ready actions or grants launch permission.
            """
            try:
                self.authoritative_roster = validate_roster_snapshot(
                    snapshot, self.equipment_catalog, native_capability, self.roster_checkpoint)
            except (ValueError, TypeError, KeyError):
                self.clear_authoritative_roster(unavailable=True)
                return False
            self.roster_unavailable = False
            self.roster_checkpoint = self.authoritative_roster
            self.refresh_equipment()
            self.refresh_roster_dialog()
            return True

        def clear_authoritative_roster(self, unavailable=False):
            self.authoritative_roster = None
            self.roster_unavailable = unavailable
            if not unavailable:
                self.roster_checkpoint = None
            if self.roster_dialog is not None:
                self.roster_dialog.reject()
            self.refresh_equipment()

        def refresh_roster_dialog(self):
            dialog = self.roster_dialog
            roster = self.authoritative_roster
            if dialog is None or roster is None:
                return
            words = ROSTER_TEXT[self.lang]
            dialog.setWindowTitle(words['title'])
            dialog.world.setText(words['world'].format(map=roster['world']['map'], revision=roster['revision']))
            for index, row in enumerate(dialog.rows):
                row.setVisible(index < len(roster['members']))
                if index < len(roster['members']):
                    member = roster['members'][index]
                    row.setText(words['member'].format(number=member['slot_id'] + 1,
                        role=words['host' if member['slot_id'] == roster['host_slot'] else 'peer'],
                        ready=words['yes' if member['ready'] else 'no']))
            dialog.summary.setText(words[roster['status']])

        def show_authoritative_roster(self):
            if self.authoritative_roster is None:
                return
            words = ROSTER_TEXT[self.lang]
            dialog = QDialog(self)
            self.roster_dialog = dialog
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(16)
            dialog.world = QLabel()
            dialog.world.setTextFormat(Qt.TextFormat.PlainText)
            dialog.world.setWordWrap(True)
            layout.addWidget(dialog.world)
            dialog.rows = []
            for _ in range(4):
                row = QLabel()
                row.setTextFormat(Qt.TextFormat.PlainText)
                row.setWordWrap(True)
                dialog.rows.append(row)
                layout.addWidget(row)
            dialog.summary = QLabel()
            dialog.summary.setWordWrap(True)
            layout.addWidget(dialog.summary)
            notice = QLabel(words['notice'])
            notice.setWordWrap(True)
            layout.addWidget(notice)
            close = QPushButton(words['close'])
            close.clicked.connect(dialog.accept)
            layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
            self.refresh_roster_dialog()
            dialog.setMinimumWidth(520)
            dialog.resize(640, dialog.sizeHint().height())
            dialog.exec()
            self.roster_dialog = None

        def edit_equipment(self):
            if self.busy or self.equipment_catalog is None:
                return
            words = EQUIPMENT_TEXT[self.lang]
            catalog = self.equipment_catalog
            value = equipment.validate_preferences(self.equipment_preferences, catalog)
            dialog = QDialog(self)
            self.equipment_dialog = dialog
            dialog.setWindowTitle(words['title'])
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(16)
            for key in ('scope', 'unsupported'):
                label = QLabel(words[key]); label.setWordWrap(True); layout.addWidget(label)
            form = QFormLayout(); form.setVerticalSpacing(12); layout.addLayout(form)
            dialog.mode = QComboBox()
            for mode in ('automatic', 'manual'): dialog.mode.addItem(words[mode], mode)
            dialog.mode.setCurrentIndex(0 if value['mode'] == 'automatic' else 1)
            label = QLabel(words['mode']); label.setBuddy(dialog.mode); form.addRow(label, dialog.mode)
            automatic_help = QLabel(words['automatic_help']); automatic_help.setWordWrap(True); layout.addWidget(automatic_help)
            manual = QWidget(); manual_form = QFormLayout(manual); manual_form.setContentsMargins(0, 0, 0, 0); manual_form.setVerticalSpacing(12)
            dialog.family = QComboBox()
            for family in sorted(equipment.active_families(catalog)):
                dialog.family.addItem(words.get(family, family), family)
            dialog.family.setCurrentIndex(dialog.family.findData(value['manual']['family']))
            label = QLabel(words['family']); label.setBuddy(dialog.family); manual_form.addRow(label, dialog.family)
            dialog.slots = {}
            for slot in equipment.SLOTS:
                combo = QComboBox(); dialog.slots[slot] = combo
                label = QLabel(words[slot]); label.setBuddy(combo); manual_form.addRow(label, combo)
            draft = {value['manual']['family']: value['manual']['slots'].copy()}
            previous_family = [None]
            def populate():
                if previous_family[0] is not None:
                    draft[previous_family[0]] = {slot: combo.currentData() for slot, combo in dialog.slots.items()}
                family = dialog.family.currentData()
                for slot, combo in dialog.slots.items():
                    combo.clear()
                    choices = catalog['families'][family]['menu_slots'][slot]['choices']
                    for number in sorted(choices, key=int): combo.addItem(equipment.choice_label(choices[number], self.lang), int(number))
                    preferred = draft.get(family, {}).get(slot)
                    index = combo.findData(preferred)
                    combo.setCurrentIndex(index if index >= 0 else 0)
                previous_family[0] = family
            dialog.family.currentIndexChanged.connect(populate); populate(); layout.addWidget(manual)
            dialog.duplicate_note = QLabel(words['duplicate'])
            dialog.duplicate_note.setWordWrap(True)
            layout.addWidget(dialog.duplicate_note)
            def refresh_duplicates():
                family = catalog['families'][dialog.family.currentData()]['menu_slots']
                weapons = [family[slot]['choices'].get(str(combo.currentData()), {}).get('weapon') for slot, combo in dialog.slots.items()]
                weapons = [weapon.lower() for weapon in weapons if weapon and weapon != 'none']
                dialog.duplicate_note.setVisible(dialog.mode.currentData() == 'manual' and len(weapons) != len(set(weapons)))
            for combo in dialog.slots.values(): combo.currentIndexChanged.connect(refresh_duplicates)
            world = QLabel(words['world']); world.setWordWrap(True); layout.addWidget(world)
            if self.equipment_error == 'load_error':
                warning = QLabel(words['load_error']); warning.setWordWrap(True); layout.addWidget(warning)
            actions = QHBoxLayout(); actions.addStretch(1)
            cancel = QPushButton(words['cancel']); cancel.clicked.connect(dialog.reject); actions.addWidget(cancel)
            dialog.save = QPushButton(words['save']); dialog.save.setObjectName('primary'); dialog.save.setDefault(True); actions.addWidget(dialog.save); layout.addLayout(actions)
            def mode_changed():
                manual.setVisible(dialog.mode.currentData() == 'manual')
                automatic_help.setVisible(dialog.mode.currentData() == 'automatic')
                refresh_duplicates()
            dialog.mode.currentIndexChanged.connect(mode_changed); mode_changed()
            def save():
                selected = {'schema': 1, 'mode': dialog.mode.currentData(), 'manual': {
                    'family': dialog.family.currentData(), 'slots': {slot: combo.currentData() for slot, combo in dialog.slots.items()}}}
                try:
                    self.equipment_preferences = equipment.save_preferences(selected, catalog, self.equipment_path)
                except (OSError, ValueError):
                    QMessageBox.warning(dialog, words['title'], words['save_error']); return
                self.equipment_error = None
                self.equipment_note.setText(words['saved'])
                dialog.accept()
            dialog.save.clicked.connect(save)
            dialog.setMinimumWidth(540); dialog.resize(640, dialog.sizeHint().height())
            dialog.exec()

        def folder_changed(self):
            self.verified_summary = None
            self.clear_authoritative_roster()
            self.refresh_installation_info()

        def refresh_installation_info(self):
            if not hasattr(self, "installation_info"):
                return
            result = self.verified_summary
            if not result:
                self.installation_info.setText(self.text("check_summary"))
                self.save_info.clear()
                return
            self.installation_info.setText(self.text("installed").format(version=result["suite_version"]))
            variant = self.campaigns.currentItem().data(Qt.ItemDataRole.UserRole)
            saved = result.get("local_saves", {}).get(variant)
            if not saved or saved.get("unavailable"):
                text = self.text("saves_unavailable")
            elif not saved.get("latest"):
                text = self.text("no_saves")
            else:
                latest = saved["latest"]
                try:
                    modified = datetime.fromisoformat(latest["modified"]).astimezone().strftime("%Y-%m-%d %H:%M")
                except (KeyError, TypeError, ValueError):
                    modified = "?"
                text = self.text("latest_save").format(name=latest["name"], modified=modified)
            if self.mode.currentData() == "joining":
                text += "\n" + self.text("host_progress")
            self.save_info.setText(text)

        def browse_folder(self):
            folder = QFileDialog.getExistingDirectory(self, self.text("browse_title"), self.folder.text())
            if folder:
                self.folder.setText(folder)

        def set_status(self, key):
            self.status_key = key
            self.status.setText(self.text(key))
            if key in {"invalid", "failed", "worker_error", "need_folder", "need_host", "reconnecting", "recovery_waiting"}:
                self.content_scroll.ensureWidgetVisible(self.status)

        def set_busy(self, value):
            self.busy = value
            for widget in (self.folder, self.browse, self.campaigns, self.mode, self.runner, self.map, self.check, self.start):
                widget.setEnabled(not value)
            hosting = self.mode.currentData() == "hosting"
            self.campaigns.setEnabled(not value or (self.session and hosting and not self.switching))
            self.switch.setVisible(value and self.session and hosting)
            self.switch.setEnabled(value and self.session and hosting and not self.switching
                                   and self.campaigns.currentItem().data(Qt.ItemDataRole.UserRole) != self.active_variant)
            if not value:
                self.switching = False
                self.recovering = False
                self.retry_session.hide()
                self.cancel_switch.hide()
            self.runner.setEnabled(not value and os.name != "nt")
            self.stop.setVisible(value and not self.recovering)
            self.stop.setEnabled(value and not self.stopping)
            self.stop.setText(self.text("stop" if self.session else "cancel_check"))
            self.progress.setVisible(value)
            self.mode_changed()
            self.refresh_equipment()

        def run_worker(self, kind, arguments):
            self.output = ""
            self.event_buffer = ""
            command = worker_command(kind, arguments)
            self.process.setProgram(command[0])
            self.process.setArguments(command[1:])
            self.process.start()

        def validate(self, launch):
            if self.busy:
                return
            if not self.folder.text().strip():
                self.set_status("need_folder")
                self.folder.setFocus()
                return
            if launch and self.mode.currentData() == "joining" and not self.host.text().strip():
                self.set_status("need_host")
                self.host.setFocus()
                return
            self.pending_launch = launch
            self.clear_authoritative_roster()
            self.session = False
            self.stopping = False
            self.details.clear()
            self.set_status("checking")
            self.set_busy(True)
            self.run_worker("suite", ["check", "--game", self.folder.text().strip()])

        def read_output(self):
            text = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
            self.output += text
            self.details.moveCursor(self.details.textCursor().MoveOperation.End)
            self.details.insertPlainText(text)
            if self.session and not self.stopping:
                self.event_buffer += text
                while "\n" in self.event_buffer:
                    line, self.event_buffer = self.event_buffer.split("\n", 1)
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    phase = event.get("phase") if isinstance(event, dict) else None
                    if phase in {"reconnecting", "recovery_waiting"} or (phase == "running" and event.get("recovering") is True):
                        self.active_variant = event.get("variant", self.active_variant)
                        self.recovering = True
                        self.switching = True
                        self.clear_authoritative_roster()
                        self.retry_session.show()
                        self.cancel_switch.setText(self.text("stop"))
                        self.cancel_switch.show()
                        self.set_status("recovery_waiting" if phase == "recovery_waiting" else "reconnecting")
                        self.set_busy(True)
                    elif phase in {"running", "resumed"}:
                        self.active_variant = event.get("variant", self.active_variant)
                        self.recovering = False
                        self.switching = False
                        self.retry_session.hide()
                        self.cancel_switch.hide()
                        self.set_status("active")
                        self.set_busy(True)
                    elif phase in {"verifying", "prepared", "restarting"}:
                        self.clear_authoritative_roster()
                        self.recovering = phase == "restarting"
                        self.switching = True
                        self.cancel_switch.setText(self.text("stop" if self.recovering else "cancel_switch"))
                        self.cancel_switch.setVisible(self.recovering or self.mode.currentData() == "hosting")
                        self.set_status("switching")
                        self.set_busy(True)
                    elif phase == "cancelled":
                        self.recovering = False
                        self.switching = False
                        self.cancel_switch.hide()
                        self.retry_session.hide()
                        self.set_status("active")
                        self.set_busy(True)
                    elif phase == "waiting":
                        self.set_status("switch_waiting")
                        self.retry_session.setVisible(self.mode.currentData() == "hosting")
                        self.cancel_switch.setVisible(self.mode.currentData() == "hosting")
                    elif phase == "error":
                        self.clear_authoritative_roster(unavailable=True)
                        self.recovering = self.recovering or event.get("recovering") is True
                        self.set_status("recovery_waiting" if self.recovering else "failed")
                        self.details_toggle.setChecked(True)
                        self.retry_session.show()
                        self.cancel_switch.setText(self.text("stop" if self.recovering else "cancel_switch"))
                        self.cancel_switch.setVisible(self.recovering or self.mode.currentData() == "hosting")
                    elif phase == "recovery_cancelled":
                        self.stopping = True
                        self.set_status("stopping")
                        self.retry_session.hide()
                        self.cancel_switch.hide()
                        self.set_busy(True)

        def send_control(self, action, **fields):
            if self.session and self.busy and not self.stopping:
                self.process.write((json.dumps({"action": action, **fields}) + "\n").encode("utf-8"))

        def switch_campaign(self):
            variant = self.campaigns.currentItem().data(Qt.ItemDataRole.UserRole)
            if not self.session or self.mode.currentData() != "hosting" or variant == self.active_variant or self.switching:
                return
            answer = QMessageBox.question(self, self.text("switch_title"),
                                          self.text("switch_message").format(campaign=self.text(variant),
                                            mission=self.map.text().strip() or self.text("campaign_beginning"),
                                            difficulty=self.difficulty.currentText()),
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                          QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.switching = True
            self.clear_authoritative_roster()
            self.cancel_switch.show()
            self.set_status("switching")
            self.set_busy(True)
            self.send_control("switch", variant=variant, map=self.map.text().strip(), difficulty=self.difficulty.currentData())

        def finished(self, code, exit_status):
            self.read_output()
            if not self.session:
                try:
                    result = json.loads(self.output)
                except (ValueError, TypeError):
                    result = {}
                valid = code == 0 and exit_status == QProcess.ExitStatus.NormalExit and result.get("ok") is True
                self.verified_summary = result if valid and isinstance(result.get("suite_version"), str) else None
                self.refresh_installation_info()
                if valid and self.pending_launch and not self.stopping:
                    self.session = True
                    self.active_variant = self.campaigns.currentItem().data(Qt.ItemDataRole.UserRole)
                    self.stop.setText(self.text("stop"))
                    self.set_status("launching")
                    arguments = ["--game", self.folder.text().strip(), "--variant", self.campaigns.currentItem().data(Qt.ItemDataRole.UserRole)]
                    if self.mode.currentData() == "joining":
                        arguments += ["--host", self.host.text().strip()]
                    else:
                        arguments += ["--hosting", "--difficulty", str(self.difficulty.currentData())]
                    if self.mode.currentData() == "hosting" and self.map.text().strip():
                        arguments += ["--map", self.map.text().strip()]
                    if os.name != "nt" and self.runner.text().strip():
                        arguments += ["--runner", self.runner.text().strip()]
                    self.run_worker("session", arguments)
                    self.set_busy(True)
                    return
                self.set_status("cancelled" if self.stopping else "valid" if valid else "invalid")
            else:
                self.clear_authoritative_roster()
                self.set_status("ended" if code == 0 or self.stopping else "failed")
            if self.status_key in {"invalid", "failed"}:
                self.details_toggle.setChecked(True)
            self.stopping = False
            self.set_busy(False)
            if self.status_key in {"invalid", "failed", "worker_error"}:
                self.start.setText(self.text("retry"))
            if self.close_when_done:
                self.close()

        def process_error(self, error):
            if error == QProcess.ProcessError.FailedToStart:
                self.clear_authoritative_roster(unavailable=True)
                self.set_status("worker_error")
                self.details_toggle.setChecked(True)
                self.details.appendPlainText(self.process.errorString())
                self.stopping = False
                self.set_busy(False)
                if self.close_when_done:
                    self.close()

        def stop_session(self):
            if not self.busy or self.stopping:
                return
            self.stopping = True
            self.set_status("stopping")
            self.stop.setEnabled(False)
            if self.session:
                self.process.write(b'{"action":"stop"}\n')
            else:
                self.process.kill()  # the checker does not own any game process

        def closeEvent(self, event):
            if self.busy:
                if not self.close_when_done:
                    answer = QMessageBox.question(self, self.text("close_title"), self.text("close_message"),
                                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                                  QMessageBox.StandardButton.No)
                    if answer != QMessageBox.StandardButton.Yes:
                        event.ignore()
                        return
                    self.close_when_done = True
                    self.stop_session()
                event.ignore()
                return
            self.settings.setValue("language", self.lang)
            self.settings.setValue("game", self.folder.text().strip())
            self.settings.setValue("variant", self.campaigns.currentItem().data(Qt.ItemDataRole.UserRole))
            self.settings.setValue("host", self.host.text().strip())
            self.settings.setValue("runner", self.runner.text().strip())
            self.settings.setValue("difficulty", self.difficulty.currentData())
            self.settings.sync()
            if getattr(self, 'party_dialog', None) is not None:
                self.party_dialog.reject()
            event.accept()

    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("CoD Coop")
    window = Launcher()
    window.show()
    if args.smoke_screenshot:
        def screenshot_and_exit():
            args.smoke_screenshot.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(args.smoke_screenshot)):
                app.exit(1)
            else:
                app.exit(0)
        QTimer.singleShot(500, screenshot_and_exit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
