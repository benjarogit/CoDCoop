"""Actual launcher lobby UI; network worker and native application are separate."""
import json
from pathlib import Path
import tempfile

TEXT = {
'en': {'title':'United Fronts party', 'create':'Create party', 'join':'Join party', 'invite':'Invitation (share privately)',
       'address':'Advertised LAN IPv4', 'port':'Lobby port', 'submit':'Submit your saved equipment', 'confirm':'Confirm current choices',
       'unconfirm':'Withdraw confirmation', 'retry':'Retry connection', 'leave':'Leave lobby', 'cancel':'Cancel party', 'waiting':'Waiting for the authenticated party…',
       'blocked':'Lobby choices are synchronized. Starting with these kits is unavailable until the native roster/resource bootstrap is verified.',
       'member':'Player {slot}: {mode} — {ready}', 'yes':'choice confirmed', 'no':'waiting for confirmation',
       'world':'Mission: {map} · Revision {revision}', 'connected':'Connected', 'error':'Lobby request rejected',
       'host':'Host', 'peer':'Participant', 'native':'Start with party equipment (unavailable)', 'copy':'Copy invitation', 'you':'you', 'automatic':'original automatic kit', 'manual':'individual kit'},
'de': {'title':'United-Fronts-Gruppe', 'create':'Gruppe erstellen', 'join':'Gruppe beitreten', 'invite':'Einladung (privat weitergeben)',
       'address':'Bekanntgegebene LAN-IPv4', 'port':'Lobby-Port', 'submit':'Eigene gespeicherte Ausrüstung senden', 'confirm':'Aktuelle Auswahl bestätigen',
       'unconfirm':'Bestätigung zurücknehmen', 'retry':'Verbindung wiederholen', 'leave':'Lobby verlassen', 'cancel':'Gruppe abbrechen', 'waiting':'Warte auf die authentifizierte Gruppe…',
       'blocked':'Die Auswahl wird synchronisiert. Der Start mit diesen Ausrüstungen wartet auf die geprüfte native Gruppen-/Ressourcenanbindung.',
       'member':'Spieler {slot}: {mode} — {ready}', 'yes':'Auswahl bestätigt', 'no':'Bestätigung ausstehend',
       'world':'Mission: {map} · Stand {revision}', 'connected':'Verbunden', 'error':'Lobby-Anfrage abgelehnt',
       'host':'Host', 'peer':'Mitspieler', 'native':'Mit Gruppenausrüstung starten (noch nicht verfügbar)', 'copy':'Einladung kopieren', 'you':'du', 'automatic':'originale automatische Ausrüstung', 'manual':'eigene Ausrüstung'}}


def create_dialog(parent, *, language, game, map_name, difficulty, preferences, command_factory, settings_directory):
    from PySide6.QtCore import QProcess, QTimer, Qt
    from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QHBoxLayout,QLineEdit,QLabel,QPushButton,QPlainTextEdit,QSpinBox,QComboBox,QApplication
    words=TEXT[language]; dialog=QDialog(parent); dialog.setWindowTitle(words['title']); dialog.setMinimumWidth(600)
    layout=QVBoxLayout(dialog); form=QFormLayout(); layout.addLayout(form)
    dialog.address=QLineEdit('127.0.0.1'); form.addRow(words['address'],dialog.address)
    dialog.port=QSpinBox(); dialog.port.setRange(1024,65535); dialog.port.setValue(28961);form.addRow(words['port'],dialog.port)
    dialog.map=QLineEdit(map_name);form.addRow('Mission',dialog.map)
    dialog.campaign=QComboBox();dialog.campaign.addItem('Mission faction unresolved' if language=='en' else 'Missionsfraktion noch offen',None)
    for value,en,de in [('american','American','Amerikanisch'),('british','British','Britisch'),('russian','Russian','Russisch')]:dialog.campaign.addItem(en if language=='en' else de,value)
    form.addRow('Campaign faction' if language=='en' else 'Kampagnenfraktion',dialog.campaign)
    dialog.skill=QSpinBox();dialog.skill.setRange(0,3);dialog.skill.setValue(difficulty);form.addRow('Difficulty' if language=='en' else 'Schwierigkeit',dialog.skill)
    dialog.apply_world=QPushButton('Apply host mission settings' if language=='en' else 'Host-Missionseinstellungen übernehmen');layout.addWidget(dialog.apply_world);dialog.apply_world.setEnabled(False)
    dialog.invite=QLineEdit();dialog.invite.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit);form.addRow(words['invite'],dialog.invite)
    buttons=QHBoxLayout(); layout.addLayout(buttons)
    dialog.copy_invite=QPushButton(words['copy']);buttons.addWidget(dialog.copy_invite);dialog.copy_invite.clicked.connect(lambda:QApplication.clipboard().setText(dialog.invite.text()))
    dialog.create=QPushButton(words['create']);dialog.join=QPushButton(words['join']);buttons.addWidget(dialog.create);buttons.addWidget(dialog.join)
    dialog.status=QLabel(words['waiting']);dialog.status.setWordWrap(True);dialog.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(dialog.status)
    dialog.members=QPlainTextEdit();dialog.members.setReadOnly(True);dialog.members.setMaximumHeight(150);layout.addWidget(dialog.members)
    dialog.submit=QPushButton(words['submit']);dialog.confirm=QPushButton(words['confirm']);layout.addWidget(dialog.submit);layout.addWidget(dialog.confirm)
    dialog.blocked=QLabel(words['blocked']);dialog.blocked.setWordWrap(True);layout.addWidget(dialog.blocked)
    dialog.launch=QPushButton(words['native']);dialog.launch.setEnabled(False);layout.addWidget(dialog.launch)
    actions=QHBoxLayout();layout.addLayout(actions);dialog.retry=QPushButton(words['retry']);dialog.cancel=QPushButton(words['cancel']);dialog.leave=QPushButton(words['leave']);actions.addWidget(dialog.retry);actions.addWidget(dialog.cancel);actions.addWidget(dialog.leave)
    dialog.worker=QProcess(dialog);dialog.worker.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
    dialog.view=None;dialog.hosting=False;dialog.buffer='';dialog.invite_path=None
    dialog.submit.setEnabled(False);dialog.confirm.setEnabled(False);dialog.cancel.setEnabled(False)
    def send(value):
        if dialog.worker.state()==QProcess.ProcessState.Running:dialog.worker.write((json.dumps(value)+'\n').encode())
    def start(host):
        if dialog.worker.state()!=QProcess.ProcessState.NotRunning:return
        from coop_party import atomic_private
        folder=Path(settings_directory);folder.mkdir(parents=True,exist_ok=True)
        fd,path=tempfile.mkstemp(prefix='party-invitation-',suffix='.json',dir=folder)
        import os
        os.close(fd);dialog.invite_path=Path(path)
        if not host:atomic_private(dialog.invite_path,{'invitation':dialog.invite.text().strip()})
        args=['--game',str(game),'--invitation-file',str(dialog.invite_path)]
        if host:args+=['--host','--bind','0.0.0.0','--advertise',dialog.address.text().strip(),'--port',str(dialog.port.value()),'--map',dialog.map.text().strip(),'--difficulty',str(dialog.skill.value())]
        if host and dialog.campaign.currentData():args+=['--campaign',dialog.campaign.currentData()]
        command=command_factory('party',args);dialog.hosting=host;dialog.worker.setProgram(command[0]);dialog.worker.setArguments(command[1:]);dialog.worker.start()
        dialog.create.setEnabled(False);dialog.join.setEnabled(False);dialog.invite.setReadOnly(True);dialog.cancel.setEnabled(host);dialog.apply_world.setEnabled(host);dialog.address.setEnabled(False);dialog.port.setEnabled(False)
        for widget in (dialog.map,dialog.campaign,dialog.skill):widget.setEnabled(host)
    def receive():
        dialog.buffer+=bytes(dialog.worker.readAllStandardOutput()).decode('utf8',errors='replace')
        while '\n' in dialog.buffer:
            line,dialog.buffer=dialog.buffer.split('\n',1)
            try:value=json.loads(line)
            except ValueError:continue
            if value.get('phase')=='party':
                dialog.view=value;view=value['roster'];dialog.status.setText(words['world'].format(map=view['world']['map'],revision=view['revision']))
                if not dialog.hosting:
                    dialog.map.setText(view['world']['map']);dialog.skill.setValue(int(view['world'].get('difficulty','1')))
                    dialog.campaign.setCurrentIndex(max(0,dialog.campaign.findData(view['world'].get('campaign'))))
                confirmed=value['confirmed_slots'];dialog.confirm.setText(words['unconfirm' if value.get('local_slot') in confirmed else 'confirm']);dialog.members.setPlainText('\n'.join(words['member'].format(slot=m['slot_id']+1,mode=words['host' if m['slot_id']==view['host_slot'] else 'peer']+' / '+words[m['kit']['mode']] + (' ('+words['you']+')' if m['slot_id']==value.get('local_slot') else ''),ready=words['yes' if m['slot_id'] in confirmed else 'no']) for m in view['members']))
                if value['status']=='waiting':dialog.status.setText(words['waiting'])
                dialog.submit.setEnabled(value['status']!='cancelled');dialog.confirm.setEnabled(value['status']!='cancelled')
                if value['status']=='cancelled':dialog.status.setText(words['cancel']);dialog.launch.setEnabled(False)
            else:dialog.status.setText(words['waiting'] if value.get('phase')=='party_waiting' else words['error']+': '+str(value.get('error','')))
    def read_invitation():
        if dialog.hosting and dialog.invite_path and dialog.invite_path.stat().st_size:
            try:dialog.invite.setText(json.loads(dialog.invite_path.read_text())['invitation'])
            except (ValueError,KeyError,OSError):pass
    def own_kit():
        if not dialog.view:return
        value=preferences()
        kit={'mode':'automatic'} if value['mode']=='automatic' else {'mode':'manual',**value['manual']}
        send({'action':'kit','revision':dialog.view['roster']['revision'],'kit':kit})
    def confirm():
        if dialog.view:send({'action':'confirm','revision':dialog.view['roster']['revision'],'plan':dialog.view['roster']['plan_sha256'],'ready':dialog.view.get('local_slot') not in dialog.view['confirmed_slots']})
    def apply_world():
        if not dialog.view or not dialog.hosting:return
        world=dict(dialog.view['roster']['world'],map=dialog.map.text().strip(),difficulty=str(dialog.skill.value()))
        if dialog.campaign.currentData():world['campaign']=dialog.campaign.currentData()
        else:world.pop('campaign',None)
        send({'action':'world','revision':dialog.view['roster']['revision'],'world':world})
    dialog.apply_world.clicked.connect(apply_world)
    def cancel():
        if dialog.view:send({'action':'cancel','revision':dialog.view['roster']['revision']})
    def leave():send({'action':'stop'});dialog.reject()
    def finished():
        dialog.create.setEnabled(True);dialog.join.setEnabled(True);dialog.invite.setReadOnly(False);dialog.address.setEnabled(True);dialog.port.setEnabled(True);dialog.submit.setEnabled(False);dialog.confirm.setEnabled(False);dialog.apply_world.setEnabled(False)
    dialog.create.clicked.connect(lambda:start(True));dialog.join.clicked.connect(lambda:start(False));dialog.submit.clicked.connect(own_kit);dialog.confirm.clicked.connect(confirm);dialog.cancel.clicked.connect(cancel);dialog.retry.clicked.connect(lambda:send({'action':'retry'}));dialog.leave.clicked.connect(leave)
    dialog.worker.readyReadStandardOutput.connect(receive);dialog.worker.finished.connect(finished)
    dialog.worker.errorOccurred.connect(lambda error:dialog.status.setText(words['error']+': '+dialog.worker.errorString()))
    dialog.timer=QTimer(dialog);dialog.timer.timeout.connect(read_invitation);dialog.timer.start(300)
    def close():
        dialog.timer.stop();send({'action':'stop'})
        if not dialog.worker.waitForFinished(3000):dialog.worker.kill();dialog.worker.waitForFinished(1000)
        if dialog.invite_path:dialog.invite_path.unlink(missing_ok=True)
    dialog.finished.connect(close)
    return dialog
