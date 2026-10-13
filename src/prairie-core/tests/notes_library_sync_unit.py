# SPDX-License-Identifier: Apache-2.0
"""Notes sync failure boundaries and preservation of concurrent local edits."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import threading
from prairie_apps.connect_sync import ConnectError, HubResponseError
from prairie_apps.notes_account import NotesSession
from prairie_apps.notes_backend import NotesStore
from prairie_apps.notes_library_sync import NotesLibrarySync
from prairie_apps.notes_sync_metadata import payload, version


class FixtureClient:
    origin = 'http://127.0.0.1:3017'
    def __init__(self):
        self.items=[]
        self.cap={'notes_delta':1,'notes_meta':2,'notes_files':1,'notes_layout':2}
    def request(self,method,path,*,token,payload=None):
        if path.endswith('/capabilities'):return self.cap
        if path.endswith('/collections/notes-layout') and method=='GET':return {'items':[],'revision':0}
        if path.endswith('/notes') and method=='GET':return {'items':self.items}
        raise AssertionError('No mutation should occur before the failing boundary')


class SyncBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.directory=Path(self.temp.name)
        self.store=NotesStore(self.directory/'notes.sqlite3')
        self.client=FixtureClient()
        self.session=NotesSession('00000000-0000-0000-0000-000000000001', 'synthetic-notes-token', 'a'*64,'Notes fixture',self.client.origin)
        self.sync=NotesLibrarySync(self.session,self.client,self.directory)
        self.note=self.store.create_note(title='Local edit')
        self.note=self.store.update_note(self.note.id,title='Local edit',body='hello',runs=({'style':'bold','start':0,'end':5},))
    def tearDown(self):
        self.store.close();self.temp.cleanup()
    def remote(self):
        item=payload(self.store,self.note)
        item['etag'],item['meta_etag']=version(item)
        return item
    def test_origin_mismatch_is_rejected_before_using_credentials(self):
        self.client.origin='http://127.0.0.1:3018'
        with self.assertRaises(ConnectError):NotesLibrarySync(self.session,self.client,self.directory)

    def test_cancelled_sync_never_contacts_the_hub(self):
        cancel=threading.Event();cancel.set()
        self.client.request=lambda *args,**kwargs:self.fail('Cancelled sync sent credentials')
        with self.assertRaises(ConnectError):NotesLibrarySync(self.session,self.client,self.directory,cancel=cancel).run()

    def test_plain_text_legacy_page_import_preserves_content(self):
        item=self.remote();item['meta']=None;item['meta_etag']=None
        validated=self.sync._validate_remote(item)
        self.assertEqual(validated['body'],'hello')
        self.assertEqual(validated['meta']['runs'],[])
        self.assertIsNone(validated['meta_etag'])

    def test_legacy_attachment_without_position_is_not_guessed(self):
        item=self.remote();item['meta']=None;item['meta_etag']=None;item['attachments']=['b'*64]
        with self.assertRaises(ConnectError):self.sync._validate_remote(item)

    def test_body_limit_matches_hub_utf16_units(self):
        item=self.remote();item['body']='\u754c'*(256*1024);item['meta']['runs']=[]
        item['etag'],item['meta_etag']=version(item)
        self.assertEqual(self.sync._validate_remote(item)['body'],item['body'])
        item['body']='\U0001f30a'*(128*1024+1)
        item['etag'],item['meta_etag']=version(item)
        with self.assertRaises(ConnectError):self.sync._validate_remote(item)
    def test_unsupported_capability_keeps_local_content(self):
        self.client.cap['notes_meta']=1
        with self.assertRaises(ConnectError):self.sync.run()
        self.assertEqual(self.store.get_note(self.note.id),self.note)
        self.assertIsNone(self.sync._ack(self.store,self.note.id))
    def test_incomplete_library_cannot_remove_or_publish_notes(self):
        self.client.items=[{}]*5000
        with self.assertRaises(ConnectError):self.sync.run()
        self.assertEqual(self.store.get_note(self.note.id),self.note)
    def test_invalid_cloud_metadata_cannot_replace_local_formatting(self):
        remote=self.remote();remote['meta']['runs'][0]['end']=999
        self.client.items=[remote]
        with self.assertRaises(ConnectError):self.sync.run()
        self.assertEqual(self.store.get_note(self.note.id),self.note)
    def test_a_save_between_read_and_apply_wins(self):
        item=self.remote()
        expected=self.sync._fingerprint(item)
        item['title']='Remote change'
        saved=self.store.update_note(self.note.id,title='Newer local edit',body=self.note.body,runs=self.note.runs)
        self.assertFalse(self.sync._write(self.store,item,expected))
        self.assertEqual(self.store.get_note(self.note.id),saved)
        self.assertIsNone(self.sync._ack(self.store,self.note.id))
    def test_missing_attachment_cannot_commit_a_partial_page(self):
        item=self.remote();item['body']='\ufffc';item['attachments']=['b'*64]
        item['meta']['runs']=[{'style':'image','start':0,'end':1,'src':'b'*64+'.png','width':200}]
        item['etag'],item['meta_etag']=version(item)
        def refused(*args,**kwargs):raise HubResponseError(404,'Missing fixture attachment')
        self.sync.blobs.transfer=refused
        with self.assertRaises(HubResponseError):self.sync._write(self.store,item,self.sync._fingerprint(payload(self.store,self.note)))
        self.assertEqual(self.store.get_note(self.note.id),self.note)
        self.assertIsNone(self.sync._ack(self.store,self.note.id))
    def test_conflict_copy_and_guard_are_kept_once(self):
        item=self.remote();item['title']='Other version'
        expected=self.sync._fingerprint(payload(self.store,self.note))
        guard='fixture-version'
        self.assertTrue(self.sync._write(self.store,item,expected,copy=True,guard=guard))
        self.assertTrue(self.sync._write(self.store,item,expected,copy=True,guard=guard))
        self.assertEqual(len(self.store.list_notes()),2)
        self.assertTrue(self.store.has_kept_version(guard))
        self.assertEqual(self.store.get_note(self.note.id),self.note)


if __name__=='__main__':unittest.main()
