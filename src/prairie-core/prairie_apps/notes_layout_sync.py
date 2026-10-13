# SPDX-License-Identifier: Apache-2.0
"""Folder and sidebar synchronization with versioned whole-layout publication."""
from copy import deepcopy
import json

from .connect_sync import ConnectError
from .notes_backend import _validate_mark
from .notes_sync_metadata import digest, encoded, identifier


class NotesLayoutSync:
    def __init__(self, request):
        self.request = request

    @staticmethod
    def snapshot(store):
        parents = store.folder_parents()
        result = {folder.id:{'kind':'folder','id':folder.id,'name':folder.name,
                  'parent':parents.get(folder.id),'mark':store.get_mark('folder',folder.id),
                  'order':folder.sort_order,'favorite':bool(folder.favorite)}
                  for folder in store.list_folders()}
        result['root'] = {'kind':'root','id':'root','order':[store.root_key(item) for item in store.root_items()]}
        return result

    @staticmethod
    def validate(items):
        if not isinstance(items,list) or len(items)>1000:
            raise ConnectError('The cloud folder list could not be read.')
        result = {}
        try:
            for row in items:
                item = row['data']
                if not isinstance(item,dict) or len(encoded(item))>64*1024:
                    raise ValueError()
                key = identifier(item['id'])
                if key in result or row['uid'] != key:
                    raise ValueError()
                if item['kind']=='root':
                    if key!='root' or set(item)!={'kind','id','order'} or not isinstance(item['order'],list) or len(item['order'])>10000:
                        raise ValueError()
                    for entry in item['order']:
                        if not isinstance(entry,str):
                            raise ValueError()
                        kind,separator,subject = entry.partition(':')
                        if kind not in ('note','folder') or not separator:
                            raise ValueError()
                        identifier(subject)
                    if len(set(item['order']))!=len(item['order']):
                        raise ValueError()
                elif item['kind']=='folder':
                    if (set(item)!={'kind','id','name','parent','mark','order','favorite'}
                            or not isinstance(item['name'],str) or not item['name'].strip() or len(item['name'])>240
                            or type(item['order']) is not int or abs(item['order'])>2**53-1
                            or type(item['favorite']) is not bool):
                        raise ValueError()
                    identifier(item['parent'],optional=True)
                    if item['mark'] is not None and not isinstance(item['mark'],dict):
                        raise ValueError()
                    _validate_mark(item['mark'])
                else:
                    raise ValueError()
                result[key] = deepcopy(item)
            for key,item in result.items():
                if item['kind']!='folder':
                    continue
                ancestor,visited = item['parent'],{key}
                while ancestor is not None:
                    if ancestor in visited or ancestor not in result or result[ancestor]['kind']!='folder':
                        raise ValueError()
                    visited.add(ancestor);ancestor = result[ancestor]['parent']
        except (KeyError,TypeError,ValueError):
            raise ConnectError('The cloud folder layout is invalid. Local folders are unchanged.') from None
        return result

    def run(self,store,*,publish=True):
        reply = self.request('GET','collections/notes-layout')
        remote = self.validate(reply.get('items'))
        if type(reply.get('revision')) is not int or reply['revision']<0:
            raise ConnectError('The cloud folder revision could not be read.')
        row = store.connection.execute("SELECT value FROM metadata WHERE key='cloud-layout'").fetchone()
        known = json.loads(row[0]) if row else {}
        local = self.snapshot(store)
        incoming = {}
        for key,item in remote.items():
            if local.get(key)==item:
                continue
            if key not in local or local[key]==known.get(key):
                incoming[key] = item
            elif item!=known.get(key):
                # Keep a concurrent local folder version before taking the cloud
                # name/icon. Its pages remain in the original stable folder.
                if item['kind']=='folder':
                    existing = local[key]
                    store.create_folder(existing['name'][:227]+' (other copy)',mark=existing['mark'])
                    incoming[key] = item
                else:
                    # Root order is a preference; retain the local order until
                    # its publication against the newly read layout revision.
                    continue
        if incoming:
            store._backup_before_v70_write()
            with store.connection:
                for key,item in incoming.items():
                    if item['kind']=='root':
                        store.connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('sidebar-root-order',?)",
                                                 (json.dumps(item['order']),))
                        continue
                    store.connection.execute('''INSERT INTO folders(id,name,favorite,sort_order,expanded)
                        VALUES(?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET name=excluded.name,favorite=excluded.favorite,sort_order=excluded.sort_order''',
                        (key,item['name'],int(item['favorite']),item['order']))
                    for prefix,value in (('folder-parent:',item['parent']),('mark:folder:',item['mark'])):
                        if value is None:
                            store.connection.execute('DELETE FROM metadata WHERE key=?',(prefix+key,))
                        else:
                            store.connection.execute('INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)',
                                (prefix+key, json.dumps(value) if prefix=='mark:folder:' else value))
        # An absent previously synchronized folder is removed only if it was
        # already empty locally. Pages never disappear because a folder did.
        for key,item in known.items():
            if key not in remote and item.get('kind')=='folder' and local.get(key)==item:
                if not store.list_notes(folder_id=key) and not any(parent==key for parent in store.folder_parents().values()):
                    store.delete_folder(key)
        if not publish:
            return
        current = self.snapshot(store)
        changes = [{'op':'upsert','uid':key,'data':item} for key,item in current.items() if remote.get(key)!=item]
        changes += [{'op':'delete','uid':key} for key in remote if key not in current and key in known]
        if changes:
            result = self.request('POST','collections/notes-layout',{'base_revision':reply['revision'],'changes':changes})
            if result.get('conflict'):
                raise ConnectError('Folders changed on another device during sync. The next sync will merge them.')
            accepted = self.validate(result.get('items'))
            if any(accepted.get(key)!=item for key,item in current.items()):
                raise ConnectError('The Hub did not confirm the folder layout.')
        with store.connection:
            store.connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('cloud-layout',?)",(json.dumps(current,allow_nan=False),))
