# SPDX-License-Identifier: Apache-2.0
"""Validated, versioned Notes document metadata for cloud synchronization."""
from copy import deepcopy
import hashlib
import json
import math
import re

from .notes_backend import _validate_mark, _validate_runs
from .notes_files import validate_file

MAX_META_BYTES = 64 * 1024
IDENTIFIER = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
SHA256 = re.compile(r'^[0-9a-f]{64}$')


def identifier(value, *, optional=False):
    if optional and value is None:
        return None
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError('Invalid Notes identifier')
    return value


def _numbers(value):
    """Use integral JSON numbers consistently across Python and JavaScript."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('Notes metadata contains a non-finite number')
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {key: _numbers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_numbers(item) for item in value]
    return value


def encoded(value):
    return json.dumps(_numbers(value), ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def metadata(store, note):
    value = {'version': 1, 'runs': deepcopy(list(note.runs)),
             'mark': store.get_mark('note', note.id), 'order': note.sort_order,
             'parent': store.parent_of(note.id)}
    return validate(note.body, value)


def validate(body, value):
    """Validate all received fields before making any local storage changes."""
    if (not isinstance(body, str) or not isinstance(value, dict)
            or type(value.get('version')) is not int or value['version'] != 1
            or set(value) != {'version', 'runs', 'mark', 'order', 'parent'}):
        raise ValueError('Unsupported Notes document metadata')
    if len(encoded(value)) > MAX_META_BYTES:
        raise ValueError('Notes document metadata exceeds the sync limit')
    runs = value['runs']
    if not isinstance(runs, list) or any(not isinstance(run, dict) for run in runs):
        raise ValueError('Invalid Notes formatting')
    # Booleans are integers in Python, but are not document positions.
    for run in runs:
        if type(run.get('start')) is not int or type(run.get('end')) is not int:
            raise ValueError('Invalid Notes formatting position')
        if run.get('style') == 'image' and type(run.get('width',0)) is not int:
            raise ValueError('Invalid Notes picture width')
        if run.get('style') == 'link':
            href = run.get('href')
            if (not isinstance(href,str) or not href.lower().startswith(('https://','http://','mailto:'))
                    or any(ord(character)<32 for character in href)):
                raise ValueError('Unsupported Notes link')
        if run.get('style') == 'file':
            validate_file(run)
    _validate_runs(body, tuple(runs))
    mark = value['mark']
    if mark is not None and not isinstance(mark, dict):
        raise ValueError('Invalid Notes mark')
    _validate_mark(mark)
    if type(value['order']) is not int or not -(2**53 - 1) <= value['order'] <= 2**53 - 1:
        raise ValueError('Invalid Notes order')
    identifier(value['parent'], optional=True)
    return _numbers(deepcopy(value))


def attachment_references(value):
    """Validated metadata names pictures and files by their content hashes."""
    return {run['src']: run for run in value['runs'] if run['style'] in ('image', 'file')}


def payload(store, note):
    value = metadata(store, note)
    folder = store.get_folder(note.folder_id) if note.folder_id is not None else None
    return {'id': identifier(note.id), 'title': note.title, 'body': note.body,
            'folder_id': identifier(note.folder_id, optional=True),
            'folder_name': folder.name if folder else '', 'favorite': bool(note.favorite),
            'created_at': note.created_at, 'modified_at': note.modified_at,
            'attachments': sorted({name.split('.', 1)[0] for name in attachment_references(value)}),
            'meta': value}


def version(item):
    """Content and formatting have separate compare-and-swap versions."""
    from .connect_notes import note_etag
    return (note_etag(item['title'], item['body'], item['folder_id'], item['favorite'],
                      item['attachments']), digest(item['meta']))
