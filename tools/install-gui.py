#!/usr/bin/env python3
"""Linux graphical full-suite setup. Shares the exact command-line backend."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys


def resource(name):
    return Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / name


def backend():
    spec = importlib.util.spec_from_file_location('coop_installer', resource('install-linux.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bundled_suite():
    """The suite shipped inside this bundle, if any (AppImage / frozen setup)."""
    for candidate in (Path(sys.executable).parent / 'suite', resource('suite')):
        if (candidate / 'coop/variants.json').is_file():
            return candidate
    return None


def main(argv=None):
    # A frozen AppImage uses its own executable for the worker, so Python never
    # has to be installed on the player's machine.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--backend', action='store_true')
    parser.add_argument('--launch', action='store_true')
    options, remaining = parser.parse_known_args(argv)
    if options.backend:
        # A frozen AppImage carries the complete suite next to its worker. The
        # terminal one-liner calls `--backend` directly, so supply the bundled
        # payload unless the caller named one (--check/--rollback ignore it).
        if not any(arg == '--suite-source' or arg.startswith('--suite-source=')
                   for arg in remaining):
            suite = bundled_suite()
            if suite is not None:
                remaining = ['--suite-source', str(suite)] + remaining
        return backend().suite_main(remaining)
    if options.launch:
        spec = importlib.util.spec_from_file_location('coop_launcher', resource('coop_suite.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.main(['launch'] + remaining)
    from PySide6.QtCore import QProcess
    from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                                   QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                                   QMessageBox, QPlainTextEdit, QPushButton,
                                   QSpinBox, QVBoxLayout, QWidget)
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle('CoDCoop 0.6 — Setup')
    window.resize(740, 670)
    outer = QVBoxLayout(window)
    heading = QLabel('CoDCoop — full campaign suite / vollständiges Kampagnenpaket')
    heading.setWordWrap(True)
    outer.addWidget(heading)
    info = QLabel('Development build. All campaign variants and YAP are required.\n'
                  'Entwicklungsstand. Alle Kampagnenvarianten und YAP sind erforderlich.')
    info.setWordWrap(True)
    outer.addWidget(info)
    form = QFormLayout()
    outer.addLayout(form)

    def folder_row(label):
        line = QLineEdit()
        row = QHBoxLayout()
        row.addWidget(line)
        button = QPushButton('Browse… / Wählen…')
        row.addWidget(button)
        def browse():
            chosen = QFileDialog.getExistingDirectory(window, label, line.text() or str(Path.home()))
            if chosen:
                line.setText(chosen)
        button.clicked.connect(browse)
        form.addRow(label, row)
        return line

    game = folder_row('Game folder / Spielordner')
    suite = folder_row('0.6 suite payload / Paketordner')
    base = folder_row('Offline base (optional) / Basis (optional)')
    detected = backend().detect_games()
    if len(detected) == 1:
        game.setText(detected[0])
    elif detected:
        choices = QComboBox()
        choices.addItem('Choose an installation / Installation wählen', '')
        for path in detected:
            choices.addItem(path, path)
        choices.currentIndexChanged.connect(lambda _: game.setText(choices.currentData() or ''))
        form.insertRow(0, 'Detected / Gefunden', choices)
    found = bundled_suite()
    if found is not None:
        suite.setText(str(found))
    language = QComboBox()
    language.addItem('English', 'en')
    language.addItem('Deutsch', 'de')
    form.addRow('Game language / Spielsprache', language)
    name = QLineEdit(os.environ.get('USER', 'Player'))
    form.addRow('Player name / Spielername', name)
    resolution = QComboBox()
    resolution.setEditable(True)
    resolution.addItems(['1920x1080', '1280x720', '2560x1440', '3840x2160'])
    screen = app.primaryScreen()
    if screen:
        size = screen.size()
        resolution.setCurrentText('%dx%d' % (size.width(), size.height()))
    form.addRow('Resolution / Auflösung', resolution)
    fov = QSpinBox()
    fov.setRange(60, 130)
    fov.setValue(96)
    form.addRow('FOV', fov)
    quality = QComboBox()
    for en, de in [('High / Hoch', 'hoch'), ('Medium / Mittel', 'mittel'), ('Low / Niedrig', 'niedrig')]:
        quality.addItem(en, de)
    form.addRow('Quality / Qualität', quality)
    fullscreen = QCheckBox('Fullscreen / Vollbild')
    fullscreen.setChecked(True)
    form.addRow('', fullscreen)
    configure = QCheckBox('Apply settings to existing configs / Vorhandene Einstellungen ändern')
    configure.setChecked(False)
    form.addRow('', configure)
    downloads = QLabel('Required if absent: base 1.04 GB + extras 0.92 GB; German language 0.66 GB.\n'
                       'Falls nicht vorhanden: Basis 1,04 GB + Zusätze 0,92 GB; Deutsch 0,66 GB.\n'
                       'Existing saves and personal settings are preserved. / Spielstände und Einstellungen bleiben erhalten.')
    downloads.setWordWrap(True)
    outer.addWidget(downloads)
    output = QPlainTextEdit()
    output.setReadOnly(True)
    outer.addWidget(output, 1)
    actions = QHBoxLayout()
    install = QPushButton('Install / Installieren')
    verify = QPushButton('Check / Prüfen')
    actions.addWidget(install)
    actions.addWidget(verify)
    rollback = QPushButton('Roll back / Zurücknehmen')
    actions.addWidget(rollback)
    outer.addLayout(actions)
    process = QProcess(window)
    process.setProcessChannelMode(QProcess.MergedChannels)
    process.readyReadStandardOutput.connect(lambda: output.insertPlainText(bytes(process.readAllStandardOutput()).decode('utf-8', 'replace')))

    def start(mode='install'):
        if not game.text().strip() or (mode == 'install' and not suite.text().strip()):
            QMessageBox.warning(window, 'Missing folder / Ordner fehlt', 'Select the game folder and the complete 0.6 payload.\nSpielordner und vollständiges 0.6-Paket auswählen.')
            return
        args = ['--game', game.text().strip()]
        if mode == 'check':
            args.append('--check')
        elif mode == 'rollback':
            answer = QMessageBox.question(window, 'Restore / Wiederherstellen', 'Restore the files from the last completed installation?\nDateien der letzten abgeschlossenen Installation wiederherstellen?')
            if answer != QMessageBox.Yes:
                return
            args.append('--rollback')
        else:
            answer = QMessageBox.question(window, 'Confirm / Bestätigen', downloads.text() + '\n\nInstall complete suite / Vollständig installieren?')
            if answer != QMessageBox.Yes:
                return
            args += ['--yes', '--suite-source', suite.text().strip(), '--language', language.currentData(),
                     '--name', name.text(), '--resolution', resolution.currentText(), '--fov', str(fov.value()),
                     '--quality', quality.currentData(), '--fullscreen' if fullscreen.isChecked() else '--windowed']
            if base.text().strip():
                args += ['--source', base.text().strip()]
            if configure.isChecked():
                args.append('--configure')
        output.clear()
        install.setEnabled(False)
        verify.setEnabled(False)
        rollback.setEnabled(False)
        if getattr(sys, 'frozen', False):
            process.start(sys.executable, ['--backend'] + args)
        else:
            process.start(sys.executable, [str(resource('install-linux.py'))] + args)

    def ended(code, status):
        install.setEnabled(True)
        verify.setEnabled(True)
        rollback.setEnabled(True)
        if status == QProcess.NormalExit and code == 0:
            output.appendPlainText('\nOperation completed / Vorgang abgeschlossen.')
        else:
            output.appendPlainText('\nFAILED — see errors above. / FEHLGESCHLAGEN — siehe Fehler oben.')
    process.finished.connect(ended)
    process.errorOccurred.connect(lambda _: ended(-1, QProcess.CrashExit))
    install.clicked.connect(lambda: start('install'))
    verify.clicked.connect(lambda: start('check'))
    rollback.clicked.connect(lambda: start('rollback'))
    def close_event(event):
        if process.state() != QProcess.NotRunning:
            QMessageBox.warning(window, 'Installation running / Installation läuft', 'Wait for the operation to finish. / Bitte bis zum Ende warten.')
            event.ignore()
        else:
            event.accept()
    window.closeEvent = close_event
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
