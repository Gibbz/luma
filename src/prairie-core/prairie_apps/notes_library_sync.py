# SPDX-License-Identifier: Apache-2.0
"""Account-scoped rich Notes synchronization with durable acknowledgement state."""
import hashlib
import json
from pathlib import Path
import time
import uuid

from .connect_notes import note_etag
from .connect_sync import ConnectError
from .notes_account import NotesBlobClient
from .notes_attachments import MIME_TYPES, store_picture
from .notes_backend import NotesStore
from .notes_sync_metadata import attachment_references, digest, encoded, identifier, payload, validate, SHA256


class NotesLibrarySync:
    def __init__(self, session, client, directory, *, cancel=None):
        self.session = session.validate()
        if client.origin != self.session.hub:
            raise ConnectError('The Notes credential belongs to a different Hub.')
        self.client = client
        self.directory = Path(directory)
        self.blobs = NotesBlobClient(client)
        self.cancel = cancel

    def _check_cancelled(self):
        if self.cancel is not None and self.cancel.is_set():
            raise ConnectError('Sync paused. Your local notes are kept.')

    def _request(self, method, path, value=None):
        self._check_cancelled()
        return self.client.request(method, '/api/hub/sync/' + path,
                                   token=self.session.access_token, payload=value)

    @staticmethod
    def _ack(store, note_id):
        row = store.connection.execute('SELECT value FROM metadata WHERE key=?',
                                       ('cloud-ack:' + note_id,)).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def _remember(store, note_id, value):
        store.connection.execute('INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)',
                                 ('cloud-ack:' + note_id, json.dumps(value, allow_nan=False)))

    def _attachments(self, item, *, upload, store=None, force=False):
        for name, run in attachment_references(item['meta']).items():
            self._check_cancelled()
            sha = name.split('.', 1)[0]
            folder = self.directory / ('files' if run['style'] == 'file' else 'attachments')
            from .notes_files import file_path
            target = file_path(name,folder)
            if upload:
                cache_key = 'cloud-blob:' + sha
                if store is not None and not force:
                    row = store.connection.execute('SELECT value FROM metadata WHERE key=?',(cache_key,)).fetchone()
                    if row and 0 <= time.time()-float(row[0]) < 600:
                        continue
                with target.open('rb') as stream:
                    data = stream.read(self.blobs.MAX_BYTES + 1)
                if run['style'] == 'file' and len(data) != run['size']:
                    raise ConnectError('A Notes attachment changed on this computer. The page has not been uploaded.')
                mime = 'application/octet-stream' if run['style'] == 'file' else MIME_TYPES[name.rsplit('.', 1)[1]]
                self.blobs.transfer('PUT', sha, self.session.access_token, data=data, mime=mime)
                if store is not None:
                    with store.connection:
                        store.connection.execute('INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)',(cache_key,str(time.time())))
                        store.connection.execute('DELETE FROM metadata WHERE key=?',('cloud-blob-pending:'+sha,))
            else:
                if target.is_file():
                    with target.open('rb') as stream:
                        data = stream.read(self.blobs.MAX_BYTES + 1)
                    if (len(data) <= self.blobs.MAX_BYTES and hashlib.sha256(data).hexdigest() == sha
                            and (run['style'] != 'file' or len(data) == run['size'])):
                        continue
                data = self.blobs.transfer('GET', sha, self.session.access_token)
                if run['style'] == 'file':
                    if len(data) != run['size']:
                        raise ConnectError('The downloaded Notes file has an invalid size.')
                    self._store_bytes(target, data)
                elif store_picture(data, folder) != name:
                    raise ConnectError('The downloaded Notes picture has an invalid format.')

    @staticmethod
    def _store_bytes(target, data):
        import os, tempfile
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.download-', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(data); output.flush(); os.fsync(output.fileno())
            os.replace(temporary, target)
            directory_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def _validate_remote(self, item):
        if not isinstance(item, dict):
            raise ConnectError('The Hub returned an invalid Notes page.')
        try:
            identifier(item['id']); identifier(item.get('folder_id'), optional=True)
            if (not all(isinstance(item.get(key), str) for key in ('title','body','created_at','modified_at'))
                    or type(item.get('favorite')) is not bool or not isinstance(item.get('attachments'), list)):
                raise ValueError()
            if len(item['title']) > 240 or len(item['body'].encode('utf-16-le'))//2 > 256 * 1024:
                raise ValueError()
            legacy = item.get('meta') is None
            if legacy and (item['attachments'] or '\ufffc' in item['body']):
                raise ValueError()
            meta = validate(item['body'], item['meta'] if not legacy else {
                'version':1, 'runs':[], 'mark':None, 'order':0, 'parent':None})
            refs = sorted({name.split('.',1)[0] for name in attachment_references(meta)})
            if refs != item['attachments']:
                raise ValueError()
            if note_etag(item['title'], item['body'], item.get('folder_id'), item['favorite'], refs) != item['etag']:
                raise ValueError()
            if (item.get('meta_etag') is not None if legacy else
                    not isinstance(item.get('meta_etag'), str) or not SHA256.fullmatch(item['meta_etag'])):
                raise ValueError()
            return {key:item[key] for key in ('id','title','body','folder_id','favorite','created_at','modified_at','attachments')} | {
                'meta':meta, 'folder_name':str(item.get('folder_name') or ''),
                'etag':item['etag'], 'meta_etag':item.get('meta_etag')}
        except (KeyError, TypeError, ValueError):
            raise ConnectError('A cloud page uses unsupported or invalid Notes metadata. Local notes are unchanged.') from None

    @staticmethod
    def _fingerprint(item):
        return digest({key:value for key,value in item.items() if key not in ('etag','meta_etag','base_etag','base_meta_etag')})

    @staticmethod
    def _content(item):
        return digest({key:item[key] for key in ('title','body','folder_id','favorite','attachments','meta')})

    def _write(self, store, item, expected, *, copy=False, guard=None):
        """Keep page content, formatting, mark, order and receipt atomically."""
        self._attachments(item, upload=False)
        store._backup_before_v70_write()
        if any(run['style']=='file' for run in item['meta']['runs']):
            store._backup_before_v70_write('files')
        connection = store.connection
        connection.execute('BEGIN IMMEDIATE')
        try:
            current = connection.execute('SELECT * FROM notes WHERE id=?', (item['id'],)).fetchone()
            current_note = store.get_note(item['id']) if current else None
            if (self._fingerprint(payload(store, current_note)) if current_note else None) != expected:
                connection.rollback()
                return False
            if guard and store.has_kept_version(guard):
                connection.rollback()
                return True
            target_id = str(uuid.uuid4()) if copy else item['id']
            title = item['title'][:227] + ' (other copy)' if copy else item['title']
            folder = item.get('folder_id')
            if folder is not None:
                connection.execute('INSERT OR IGNORE INTO folders(id,name,favorite,sort_order,expanded) VALUES(?,?,0,0,1)',
                                   (folder, item['folder_name'].strip()[:240] or 'Notes'))
            values = (target_id, title, item['body'], encoded(item['meta']['runs']).decode(),
                      item['created_at'],item['modified_at'],folder,int(item['favorite']),item['meta']['order'])
            connection.execute('''INSERT INTO notes(id,title,body,runs_json,created_at,modified_at,folder_id,favorite,sort_order)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,body=excluded.body,
                runs_json=excluded.runs_json,created_at=excluded.created_at,modified_at=excluded.modified_at,
                folder_id=excluded.folder_id,favorite=excluded.favorite,sort_order=excluded.sort_order,deleted_at=NULL''', values)
            mark_key = 'mark:note:' + target_id
            if item['meta']['mark'] is None:
                connection.execute('DELETE FROM metadata WHERE key=?', (mark_key,))
            else:
                connection.execute('INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)',
                                   (mark_key, encoded(item['meta']['mark']).decode()))
            connection.execute('INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)',
                               ('cloud-parent:' + target_id,json.dumps(None if copy else item['meta']['parent'])))
            if not copy:
                self._remember(store, target_id, {'etag':item['etag'],'meta_etag':item['meta_etag'],
                                                 'sent':self._fingerprint(item),'content':self._content(item)})
            if guard:
                connection.execute('INSERT OR IGNORE INTO kept_versions(version,kept_at) VALUES(?,?)',
                                   (guard, item['modified_at']))
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise

    def run(self):
        cap = self._request('GET', 'capabilities')
        if any(cap.get(key,0) < minimum for key,minimum in (('notes_delta',1),('notes_meta',2),('notes_files',1),('notes_layout',2))):
            raise ConnectError('This Hub needs an update before it can safely sync this version of Notes.')
        reply = self._request('GET','notes')
        items = reply.get('items')
        if not isinstance(items,list) or len(items) >= 5000:
            raise ConnectError('The Hub did not return a complete Notes library. Local notes are unchanged.')
        remote = {item['id']:item for item in (self._validate_remote(raw) for raw in items)}
        if len(remote) != len(items):
            raise ConnectError('The Hub returned duplicate Notes identifiers.')
        store = NotesStore(self.directory / 'notes.sqlite3')
        pending = 0
        try:
            for key,value in store.connection.execute("SELECT key,value FROM metadata WHERE key LIKE 'cloud-blob-pending:%'").fetchall():
                run = json.loads(value)
                self._attachments({'meta':{'runs':[run]}},upload=True,store=store,force=True)
            from .notes_layout_sync import NotesLayoutSync
            NotesLayoutSync(self._request).run(store,publish=False)
            for note_id,item in remote.items():
                try:
                    mine = store.get_note(note_id)
                except KeyError:
                    mine = None
                expected = self._fingerprint(payload(store,mine)) if mine else None
                known = self._ack(store,note_id)
                changed_remote = not known or (known['etag'],known['meta_etag']) != (item['etag'],item['meta_etag'])
                if not changed_remote:
                    continue
                if mine is not None and mine.deleted_at is not None:
                    self._write(store,item,expected)
                    continue
                mine_content = self._content(payload(store,mine)) if mine else None
                if mine and mine_content != (known or {}).get('content') and mine_content != self._content(item):
                    # Keep the remote version exactly before rebasing local changes.
                    guard = note_id + '|' + item['etag'] + '|' + (item['meta_etag'] or 'plain')
                    if not store.has_kept_version(guard):
                        if not self._write(store,item,expected,copy=True,guard=guard):
                            continue
                    with store.connection:
                        self._remember(store,note_id,{'etag':item['etag'],'meta_etag':item['meta_etag'],'sent':'','content':self._content(item)})
                elif mine is None or expected != self._fingerprint(item):
                    self._write(store,item,expected)
                else:
                    with store.connection:
                        self._remember(store,note_id,{'etag':item['etag'],'meta_etag':item['meta_etag'],'sent':expected,'content':self._content(item)})
            self._parents(store)
            live = store.list_notes()
            missing = [note for note in live if note.id not in remote and self._ack(store,note.id)]
            if not remote and len(missing) >= 3:
                raise ConnectError('The cloud returned an empty library unexpectedly. No local pages were removed.')
            for note in missing:
                known = self._ack(store,note.id)
                if known['sent'] == self._fingerprint(payload(store,note)):
                    store.soft_delete_note(note.id)
                with store.connection:
                    store.connection.execute('DELETE FROM metadata WHERE key=?',('cloud-ack:'+note.id,))
            # Only explicit local trash entries become remote deletions.
            for note in store.list_notes(deleted=True):
                known = self._ack(store,note.id)
                if known is None:
                    continue
                result = self._request('POST','notes/changes',{'device_id':self.session.device_id,'observed_at':int(time.time()*1000),
                    'upserts':[],'deletes':[{'id':note.id,'base_etag':known['etag'],'base_meta_etag':known['meta_etag']}]})
                if note.id in result.get('deleted',[]):
                    with store.connection:
                        store.connection.execute('DELETE FROM metadata WHERE key=?',('cloud-ack:'+note.id,))
            batch, batch_bytes = [], 0
            def publish():
                nonlocal pending, batch, batch_bytes
                if not batch:
                    return
                result = self._request('POST','notes/changes',{'device_id':self.session.device_id,'observed_at':int(time.time()*1000),
                    'upserts':[change for change,_sent in batch],'deletes':[]})
                accepted,conflicts,missing = result.get('accepted'),result.get('conflicts',[]),result.get('missing_blobs',[])
                if not isinstance(accepted,list) or not isinstance(conflicts,list) or not isinstance(missing,list):
                    raise ConnectError('The Hub returned an invalid Notes receipt.')
                receipts = {row.get('id'):row for row in accepted if isinstance(row,dict)}
                refused = {row.get('id') for row in conflicts if isinstance(row,dict)}
                references = {name.split('.',1)[0]:run for change,_sent in batch for name,run in attachment_references(change['meta']).items()}
                with store.connection:
                    for sha in missing:
                        if sha not in references:
                            raise ConnectError('The Hub requested an attachment outside this change.')
                        store.connection.execute('INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)',
                                                 ('cloud-blob-pending:'+sha,json.dumps(references[sha])))
                for sha in missing:
                    self._attachments({'meta':{'runs':[references[sha]]}},upload=True,store=store,force=True)
                for change,sent in batch:
                    note_id = change['id']
                    if note_id in refused:
                        pending += 1
                        continue
                    receipt = receipts.get(note_id)
                    if (not receipt or not isinstance(receipt.get('meta_etag'),str) or not SHA256.fullmatch(receipt['meta_etag'])
                            or receipt.get('etag') != note_etag(change['title'],change['body'],change['folder_id'],change['favorite'],change['attachments'])):
                        raise ConnectError('The Hub did not confirm this Notes page.')
                    with store.connection:
                        self._remember(store,note_id,{'etag':receipt['etag'],'meta_etag':receipt['meta_etag'],'sent':sent,'content':self._content(change)})
                batch, batch_bytes = [], 0
            for note in store.list_notes():
                item = payload(store,note)
                sent = self._fingerprint(item)
                known = self._ack(store,note.id)
                if known and known.get('sent') == sent:
                    continue
                change = dict(item,base_etag=(known or {}).get('etag'),base_meta_etag=(known or {}).get('meta_etag'))
                size = len(encoded(change))
                if batch and (len(batch)>=200 or batch_bytes+size>4*1024*1024):
                    publish()
                self._attachments(item,upload=True,store=store)
                batch.append((change,sent));batch_bytes += size
            publish()
            NotesLayoutSync(self._request).run(store)
            if pending:
                raise ConnectError('Notes changed on another device during sync. The next sync will preserve both versions.')
            return 'Notes synced'
        finally:
            store.close()

    @staticmethod
    def _parents(store):
        rows = store.connection.execute("SELECT key,value FROM metadata WHERE key LIKE 'cloud-parent:%'").fetchall()
        parents = store.note_parents()
        desired = {key.removeprefix('cloud-parent:'):json.loads(value) for key,value in rows}
        for child,parent in desired.items():
            if parent is None:
                parents.pop(child,None)
            else:
                parents[child] = parent
        for child,parent in desired.items():
            note = store.get_note(child)
            if parent is not None:
                try:
                    ancestor = store.get_note(parent)
                except KeyError:
                    raise ConnectError('A cloud page is waiting for its parent. It has not been uploaded.') from None
                if ancestor.deleted_at is not None or ancestor.folder_id != note.folder_id:
                    raise ConnectError('The cloud Notes hierarchy has incompatible page locations.')
            current,visited = child,set()
            while current in parents:
                if current in visited:
                    raise ConnectError('The cloud Notes hierarchy contains a cycle.')
                visited.add(current)
                current = parents[current]
        with store.connection:
            for child,parent in desired.items():
                store.connection.execute('DELETE FROM note_hierarchy WHERE child_id=?',(child,))
                if parent is not None:
                    store.connection.execute('INSERT INTO note_hierarchy(child_id,parent_id) VALUES(?,?)',(child,parent))
                store.connection.execute('DELETE FROM metadata WHERE key=?',('cloud-parent:'+child,))
