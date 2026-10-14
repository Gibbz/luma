# SPDX-License-Identifier: Apache-2.0
"""App-scoped Messages enrolment and Secret Service storage."""
import re,uuid,json
from .notes_account import HUB, NotesHubClient, NotesSession, NotesAccount, NotesKeyring
from .connect_sync import ConnectError

class MessagesKeyring(NotesKeyring):
    def __init__(self,origin=HUB):
        super().__init__(origin)
        Secret=self.secret
        self.schema=Secret.Schema.new('org.projectluma.Messages.Device',Secret.SchemaFlags.NONE,
            {'hub':Secret.SchemaAttributeType.STRING,'app':Secret.SchemaAttributeType.STRING})
        self.attributes['app']='org.projectluma.Messages'
    def put(self,record):
        NotesSession(**record).validate()
        if self._locked(self._collection()):raise ConnectError('Unlock the desktop keyring before signing in.')
        raw=json.dumps(record,allow_nan=False)
        if len(raw)>32768:raise ConnectError('The sign-in is too large to store.')
        if not self._call(self.secret.password_store_sync,self.schema,self.attributes,self.secret.COLLECTION_DEFAULT,'Messages — Luma Hub',raw,timeout=120):
            raise ConnectError('The sign-in could not be saved securely.')

class MessagesAccount(NotesAccount):
    def connect(self,code,name='Messages on this device'):
        if not isinstance(code,str) or not re.fullmatch(r'[A-Z0-9-]{4,128}',code.strip().upper()):
            raise ConnectError('Enter the connection code from Luma Hub.')
        if self.secrets.get() is not None:raise ConnectError('Sign out before connecting another account.')
        device_id=str(uuid.uuid4())
        reply=self.client.request('POST','/api/hub/connect/devices',payload={'code':code.strip().upper(),'name':name[:60],'device_id':device_id,'scope':'messages'})
        token=reply.get('token')
        if reply.get('device_id',device_id)!=device_id or not isinstance(token,str) or not 1<=len(token)<=16384 or any(ord(c)<33 or ord(c)>126 for c in token):
            raise ConnectError('The Hub returned an invalid device registration.')
        try:
            identity=self.client.request('GET','/api/hub/sync/account',token=token)
            device=identity.get('device',{})
            if device.get('id')!=device_id or device.get('scope')!='messages':raise ConnectError('This server does not offer a Messages-only sign-in.')
            capabilities=self.client.request('GET','/api/hub/sync/capabilities',token=token)
            if capabilities.get('messages_device_scope')!=1:raise ConnectError('Luma Messages is not available on this server yet.')
            account=identity.get('account',{})
            session=NotesSession(device_id,token,account.get('id'),name[:240],self.client.origin).validate()
            self.secrets.put(session.__dict__)
            return session
        except Exception:
            try:self.client.request('POST',f'/api/hub/sync/devices/{device_id}/revoke',token=token,payload={})
            except ConnectError:pass
            raise
