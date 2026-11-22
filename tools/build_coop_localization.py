#!/usr/bin/env python3
"""Build owned, deterministic CoDCoop native center-print locale assets.

The prepared DE game uses the native English resource path with German
LANG_ENGLISH values. Both reviewed locale bytes use one installed path and
must be explicitly approved by the content manifest; arbitrary PK3s are never
excluded from gameplay fingerprints. This builder does not install anything,
change Core output or establish native rendering acceptance.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

INSTALLED_PATH = 'Main/localized_english_codcoop_ui.pk3'
RESOURCE_PATH = 'localizedstrings/english/codcoop.str'
NAMESPACE = 'CODCOOP'
MAX_DISPLAY_CHARS = 37  # Both native center-print drawers cap raw lines at40.
# Owned CoDCoop copy, not extracted or redistributed original game assets.
# Native localized-message templates use %s, not printf %d or &&1.
MESSAGES = (
    ('DOWNED_TITLE', 'YOU ARE DOWN', 'DU BIST NIEDERGESCHLAGEN'),
    ('DOWNED_HINT', 'Wait for a teammate to revive you', 'Mitspieler können dich wiederbeleben'),
    ('OTHER_DOWNED', 'Player %s is down', 'Spieler %s ist niedergeschlagen'),
    ('OTHER_DOWNED_HINT', 'Get close and hold Use for 3 seconds', 'Komm näher und halte Benutzen 3 s'),
    ('REVIVED_SELF', 'You were revived', 'Du wurdest wiederbelebt'),
    ('REVIVED_OTHER', 'Player %s is back up', 'Spieler %s ist wieder auf den Beinen'),
    ('BEING_REVIVED', 'Being revived', 'Du wirst wiederbelebt'),
    ('REVIVING_PLAYER', 'Reviving player %s', 'Spieler %s wird wiederbelebt'),
    ('CATCHUP', 'Moved to the host: you fell behind', 'Zum Host gebracht: Du lagst zurück'),
    ('DISCONNECTED', 'Player %s disconnected', 'Verbindung zu Spieler %s getrennt'),
)
KEYS = tuple(NAMESPACE + '_' + message[0] for message in MESSAGES)


def string_resource(language='en'):
    if language not in ('en', 'de'):
        raise ValueError('CoDCoop locale must be en or de')
    templates = {'OTHER_DOWNED', 'REVIVED_OTHER', 'REVIVING_PLAYER', 'DISCONNECTED'}
    for reference, english, german in MESSAGES:
        for value in (english, german):
            if value.count('%s') != int(reference in templates) or '%' in value.replace('%s', ''):
                raise ValueError('Unexpected native message substitution: ' + reference)
            for number in ('1', '2', '3', '4'):
                rendered = value.replace('%s', number)
                if (len(rendered.encode('latin-1')) > MAX_DISPLAY_CHARS
                        or any(ord(c) < 32 for c in rendered)):
                    raise ValueError('Native center-print line exceeds safe display bound: ' + reference)
    lines = [
        '// Owned CoDCoop center-print strings; project MIT license.',
        '// Installed language: ' + language + '. Native resource channel: English.',
        'VERSION "1"', 'CONFIG ""', 'FILENOTES "CoDCoop native center-print UI"', '',
    ]
    for reference, english, german in MESSAGES:
        value = english if language == 'en' else german
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        lines += ['REFERENCE ' + reference, 'LANG_ENGLISH "' + escaped + '"', '']
    lines += ['ENDMARKER', '']
    # Existing native German STR assets use these legacy one-byte glyphs.
    # No UTF-8 BOM or host-dependent encoding/newline conversion.
    return '\r\n'.join(lines).encode('latin-1')


def package_bytes(language='en'):
    data = string_resource(language)
    stream = io.BytesIO()
    info = zipfile.ZipInfo(RESOURCE_PATH, (2000, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(info, data)
    return stream.getvalue()


def build(output, language='en'):
    """Write exactly the owned STR resource, returning reviewable file hashes."""
    data = package_bytes(language)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.part')
    temporary.write_bytes(data)
    temporary.replace(output)
    return {'schema': 1, 'language': language, 'native_channel': 'english',
            'installed_path': INSTALLED_PATH, 'sha256': hashlib.sha256(data).hexdigest(),
            'size': len(data), 'entries': {RESOURCE_PATH: hashlib.sha256(string_resource(language)).hexdigest()},
            'keys': list(KEYS), 'native_rendering_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language', choices=('en', 'de'), default='en')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.language), indent=2))


if __name__ == '__main__':
    main()
