# SPDX-License-Identifier: Apache-2.0
"""Rich Notes document versioning and untrusted metadata validation."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from prairie_apps.notes_backend import NotesStore
from prairie_apps.notes_sync_metadata import validate, version, payload, encoded


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store = NotesStore(Path(self.temp.name) / 'notes.sqlite3')
        self.note = self.store.create_note(title='Title')
        self.note = self.store.update_note(self.note.id, title='Title', body='hello', runs=())
    def tearDown(self):
        self.store.close()
        self.temp.cleanup()
    def test_formatting_changes_have_a_separate_version(self):
        plain = payload(self.store, self.note)
        bold = deepcopy(plain)
        bold['meta']['runs'] = [{'style':'bold','start':0,'end':5}]
        self.assertEqual(version(plain)[0], version(bold)[0])
        self.assertNotEqual(version(plain)[1], version(bold)[1])
    def test_marks_and_positions_change_metadata_version(self):
        plain = payload(self.store, self.note)
        self.store.set_mark('note', self.note.id, {'kind':'emoji','value':'🌊','hue':175.0})
        marked = payload(self.store, self.note)
        self.assertNotEqual(version(plain)[1], version(marked)[1])
        self.assertIn('🌊'.encode(), encoded(marked['meta']))
        self.assertNotIn(b'175.0', encoded(marked['meta']))
    def test_invalid_runs_are_rejected_before_storage(self):
        original = payload(self.store, self.note)['meta']
        for run in ({'style':'bold','start':False,'end':5},
                    {'style':'bold','start':0,'end':6},
                    {'style':'unknown','start':0,'end':5},
                    {'style':'image','start':0,'end':1,'src':'../../secret.png'}):
            with self.subTest(run=run), self.assertRaises(ValueError):
                validate('hello', dict(original,runs=[run]))
        self.assertEqual(self.store.get_note(self.note.id), self.note)
    def test_unsupported_or_unbounded_metadata_is_rejected(self):
        original = payload(self.store, self.note)['meta']
        for changed in ({'version':True}, {'version':2}, {'parent':'../../other'},
                        {'order':True}, {'order':2**53}, {'mark':{'kind':'dot','hue':float('nan')}},
                        {'mark':{'kind':'emoji','value':'x'*65536,'hue':0}}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate('hello', dict(original,**changed))
    def test_file_references_affect_content_and_validate_offsets(self):
        note = self.store.update_note(self.note.id, title='Title', body='\ufffc', runs=())
        plain = payload(self.store, note)
        attached = deepcopy(plain)
        attached['meta']['runs'] = [{'style':'file','start':0,'end':1,'src':'a'*64+'.pdf','name':'Document.pdf','size':12}]
        validate(attached['body'], attached['meta'])
        attached['attachments'] = ['a'*64]
        self.assertNotEqual(version(plain), version(attached))
        attached['meta']['runs'][0]['src'] = '../Document.pdf'
        with self.assertRaises(ValueError):
            validate(attached['body'], attached['meta'])


if __name__ == '__main__':
    unittest.main()
