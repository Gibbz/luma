# SPDX-License-Identifier: Apache-2.0
"""Standalone account boundaries; test credentials never leave private fixtures."""
import unittest
from prairie_apps.notes_account import NotesAccount, NotesSession, NotesHubClient
from prairie_apps.connect_sync import ConnectError, HubResponseError


class MemorySecrets:
    def __init__(self):
        self.value = None
        self.error = None
    def get(self): return self.value
    def put(self, value):
        if self.error: raise self.error
        self.value = value
    def delete(self): self.value = None


class TestHub:
    origin = 'https://hub.simplyluma.com'
    def __init__(self):
        self.calls = []
        self.account = 'a'*64
        self.device = None
        self.error = None
        self.token = 'synthetic-not-a-real-credential'
        self.scope = 'notes'
        self.name = 'Notes test'
    def request(self, method, path, *, token='', payload=None):
        self.calls.append((method, path, token, payload))
        if self.error: raise self.error
        if path == '/api/hub/connect/devices':
            self.device = payload['device_id']
            return {'device_id':self.device, 'token':self.token}
        if path == '/api/hub/sync/account':
            return {'device':{'id':self.device,'scope':self.scope},'account':{'id':self.account},'profile':{'name':self.name}}
        if path.startswith('/api/hub/sync/devices/') and path.endswith('/revoke'): return {'revoked':True}
        raise AssertionError(path)


class NotesAccountTests(unittest.TestCase):
    def setUp(self):
        self.secrets=MemorySecrets();self.hub=TestHub();self.model=NotesAccount(self.secrets,self.hub)

    def test_enrollment_persists_only_validated_device_and_account(self):
        session=self.model.connect('ABCD-EFGH')
        self.assertEqual(self.model.saved_session(),session)
        self.assertEqual(session.account_id,'a'*64)
        self.assertEqual([c[1] for c in self.hub.calls],['/api/hub/connect/devices','/api/hub/sync/account'])

    def test_missing_stable_account_identity_never_saves_credentials(self):
        self.hub.account=None
        with self.assertRaises(ConnectError): self.model.connect('ABCD')
        self.assertIsNone(self.secrets.value)
        self.assertTrue(self.hub.calls[-1][1].endswith('/revoke'))

    def test_overprivileged_device_is_revoked_and_never_saved(self):
        self.hub.scope='all'
        with self.assertRaises(ConnectError):self.model.connect('ABCD')
        self.assertIsNone(self.secrets.value)
        self.assertTrue(self.hub.calls[-1][1].endswith('/revoke'))

    def test_invalid_profile_names_are_never_saved(self):
        for name in [{'name':'nested'}, 'Invalid\nname']:
            self.hub.name=name
            with self.assertRaises(ConnectError):self.model.connect('ABCD')
            self.assertIsNone(self.secrets.value)
            self.assertTrue(self.hub.calls[-1][1].endswith('/revoke'))

    def test_keyring_failure_revokes_new_registration_without_token_file_fallback(self):
        self.secrets.error=ConnectError('Keyring locked')
        with self.assertRaises(ConnectError): self.model.connect('ABCD')
        self.assertIsNone(self.secrets.value)
        self.assertTrue(self.hub.calls[-1][1].startswith('/api/hub/sync/devices/'))

    def test_existing_account_is_not_silently_replaced(self):
        self.model.connect('ABCD');before=len(self.hub.calls)
        with self.assertRaises(ConnectError): self.model.connect('EFGH')
        self.assertEqual(len(self.hub.calls),before)

    def test_account_profile_paths_do_not_depend_on_display_names(self):
        a=self.model.connect('ABCD')
        b=NotesSession(a.device_id,a.access_token,'b'*64,a.name)
        renamed=NotesSession(a.device_id,a.access_token,a.account_id,'Renamed')
        self.assertNotEqual(a.profile_directory('/profiles'),b.profile_directory('/profiles'))
        self.assertEqual(a.profile_directory('/profiles'),renamed.profile_directory('/profiles'))

    def test_network_failure_keeps_sign_in_for_revocation_retry(self):
        session=self.model.connect('ABCD');self.hub.error=ConnectError('Offline')
        with self.assertRaises(ConnectError): self.model.sign_out()
        self.assertEqual(self.model.saved_session(),session)

    def test_revoked_device_can_remove_stale_local_credentials(self):
        self.model.connect('ABCD');self.hub.error=HubResponseError(401,'Revoked')
        self.model.sign_out();self.assertIsNone(self.model.saved_session())

    def test_other_revocation_refusals_never_claim_success(self):
        self.model.connect('ABCD');self.hub.error=HubResponseError(403,'Denied')
        with self.assertRaises(HubResponseError): self.model.sign_out()
        self.assertIsNotNone(self.model.saved_session())

    def test_invalid_token_cannot_become_an_authorization_header(self):
        self.hub.token='invalid\r\nAuthorization: injected'
        with self.assertRaises(ConnectError): self.model.connect('ABCD')
        self.assertEqual(len(self.hub.calls),1)
        self.assertIsNone(self.secrets.value)

    def test_saved_credentials_cannot_move_to_another_origin(self):
        self.model.connect('ABCD');self.hub.origin='https://other.example'
        with self.assertRaises(ConnectError): self.model.saved_session()

    def test_origin_with_path_or_query_is_refused(self):
        for origin in ['https://hub.simplyluma.com/path','https://hub.simplyluma.com?q=1']:
            with self.assertRaises(ConnectError): NotesHubClient(origin)


if __name__=='__main__': unittest.main(verbosity=2)
