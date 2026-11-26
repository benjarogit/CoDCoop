#!/usr/bin/env python3
"""Linux graphical full-suite setup. Shares the exact command-line backend."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
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
    from PySide6.QtCore import QProcess, QProcessEnvironment, Qt
    from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                                   QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                                   QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                                   QSpinBox, QVBoxLayout, QWidget)
    app = QApplication(sys.argv)
    found = bundled_suite()
    window = QWidget()
    window.setWindowTitle('CoDCoop — Setup')
    window.resize(740, 670)
    outer = QVBoxLayout(window)
    heading = QLabel('CoDCoop — full campaign suite / vollständiges Kampagnenpaket')
    heading.setWordWrap(True)
    outer.addWidget(heading)
    info = QLabel('Select your existing Call of Duty folder and click Install.\n'
                  'Vorhandenen Call-of-Duty-Ordner wählen und auf Installieren klicken.' if found else
                  'Select your Call of Duty folder and a complete suite payload.\n'
                  'Call-of-Duty-Ordner und vollständiges Paket auswählen.')
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
    suite = None if found else folder_row('Suite payload / Paketordner')
    base = folder_row('Offline base (optional) / Basis (optional)')
    installer = backend()
    detected = installer.detect_games()
    if len(detected) == 1:
        game.setText(detected[0])
        kind = installer.installation_info(detected[0])['kind']
        if kind in ('Steam', 'AnkerGames'):
            form.insertRow(0, 'Detected / Gefunden', QLabel(kind))
    elif detected:
        choices = QComboBox()
        choices.addItem('Choose an installation / Installation wählen', '')
        for path in detected:
            kind = installer.installation_info(path)['kind']
            choices.addItem(f'{kind} — {path}' if kind in ('Steam', 'AnkerGames') else path, path)
        choices.currentIndexChanged.connect(lambda _: game.setText(choices.currentData() or ''))
        form.insertRow(0, 'Detected / Gefunden', choices)
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
    status_label = QLabel()
    status_label.setTextFormat(Qt.PlainText)
    status_label.setWordWrap(True)
    outer.addWidget(status_label)
    progress = QProgressBar()
    progress.hide()
    outer.addWidget(progress)
    output = QPlainTextEdit()
    output.setReadOnly(True)
    outer.addWidget(output, 1)
    actions = QHBoxLayout()
    install = QPushButton('Install / Installieren')
    play = QPushButton('Open CoDCoop / CoDCoop öffnen')
    play.hide()
    verify = QPushButton('Check / Prüfen')
    actions.addWidget(install)
    actions.addWidget(verify)
    rollback = QPushButton('Roll back / Zurücknehmen')
    actions.addWidget(rollback)
    actions.addWidget(play)
    outer.addLayout(actions)
    process = QProcess(window)
    process.setProcessChannelMode(QProcess.MergedChannels)
    environment = QProcessEnvironment.systemEnvironment()
    environment.insert('CODCOOP_INSTALL_PROGRESS', '1')
    process.setProcessEnvironment(environment)
    operation, target = '', ''

    def show_progress(en, de, percent=-1):
        status_label.setText(f'{en}\n{de}')
        progress.setRange(0, 0 if percent < 0 else 100)
        if percent >= 0:
            progress.setValue(percent)
        progress.show()

    def read_output():
        while process.canReadLine():
            line = bytes(process.readLine()).decode('utf-8', 'replace').rstrip('\r\n')
            if line.startswith('CODCOOP_PROGRESS '):
                try:
                    show_progress(*json.loads(line.removeprefix('CODCOOP_PROGRESS ')))
                    continue
                except (TypeError, ValueError):
                    pass
            output.appendPlainText(line)

    process.readyReadStandardOutput.connect(read_output)

    def start(mode='install'):
        nonlocal operation, target
        payload = str(found) if found else suite.text().strip()
        if not game.text().strip():
            QMessageBox.warning(window, 'Missing folder / Ordner fehlt', 'Select the Call of Duty game folder.\nCall-of-Duty-Spielordner auswählen.')
            return
        if mode == 'install' and not payload:
            QMessageBox.warning(window, 'Missing payload / Paket fehlt', 'Select the complete suite payload.\nVollständiges Coop-Paket auswählen.')
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
            args += ['--yes', '--suite-source', payload, '--language', language.currentData(),
                     '--name', name.text(), '--resolution', resolution.currentText(), '--fov', str(fov.value()),
                     '--quality', quality.currentData(), '--fullscreen' if fullscreen.isChecked() else '--windowed']
            if base.text().strip():
                args += ['--source', base.text().strip()]
            if configure.isChecked():
                args.append('--configure')
        output.clear()
        operation, target = mode, str(Path(game.text().strip()).expanduser().resolve())
        if mode == 'check':
            show_progress('Verifying the installation', 'Installation wird geprüft')
        elif mode == 'rollback':
            show_progress('Restoring the previous installation', 'Vorherige Installation wird wiederhergestellt')
        else:
            show_progress('Preparing the installation', 'Installation wird vorbereitet')
        play.hide()
        install.setEnabled(False)
        verify.setEnabled(False)
        rollback.setEnabled(False)
        if getattr(sys, 'frozen', False):
            process.start(sys.executable, ['--backend'] + args)
        else:
            process.start(sys.executable, [str(resource('install-linux.py'))] + args)

    def ended(code, status):
        read_output()
        rest = bytes(process.readAllStandardOutput()).decode('utf-8', 'replace').strip()
        if rest:
            output.appendPlainText(rest)
        install.setEnabled(True)
        verify.setEnabled(True)
        rollback.setEnabled(True)
        if status == QProcess.NormalExit and code == 0:
            show_progress('Finished', 'Fertig', 100)
            play.setVisible(operation == 'install')
        else:
            show_progress('Failed. See details below.', 'Fehlgeschlagen. Details siehe unten.', 0)
            progress.hide()
    process.finished.connect(ended)
    process.errorOccurred.connect(lambda error: ended(-1, QProcess.CrashExit) if error == QProcess.FailedToStart else None)

    def open_launcher():
        try:
            subprocess.Popen([str(Path(target) / 'Start-CoD-Coop.sh')],
                             env=installer.external_environment(), start_new_session=True)
        except OSError as error:
            QMessageBox.warning(window, 'CoDCoop', str(error))

    play.clicked.connect(open_launcher)
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
