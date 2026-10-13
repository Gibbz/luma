# SPDX-License-Identifier: Apache-2.0
"""Standalone Notes enrollment with private keyring storage and account profiles."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
import uuid

from .connect_sync import ConnectError, HubResponseError, hub_url

HUB = 'https://hub.simplyluma.com'
MAX_REPLY = 8 * 1024 * 1024


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        # A device bearer must never follow a redirect to another endpoint.
        return None


class NotesHubClient:
    """Bounded JSON requests to one explicitly chosen HTTPS Hub origin."""
    def __init__(self, origin=HUB):
        self.origin = hub_url(origin)
        parsed = urlsplit(self.origin)
        if parsed.path or parsed.query or parsed.fragment:
            raise ConnectError('An exact Hub origin is required.')
        self.opener = build_opener(_NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))

    def request(self, method, path, *, token='', payload=None):
        if token and (not isinstance(token, str) or len(token) > 16384 or any(ord(c) < 33 or ord(c) > 126 for c in token)):
            raise ConnectError('Invalid Notes authorization credential.')
        if not path.startswith('/api/hub/') or '?' in path or '#' in path:
            raise ConnectError('Unsupported Notes account request.')
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode('utf-8')
        if body is not None and len(body) > MAX_REPLY:
            raise ConnectError('The Notes request is too large.')
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = Request(self.origin + path, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=20) as response:
                raw = response.read(MAX_REPLY + 1)
                if len(raw) > MAX_REPLY or response.headers.get_content_type() != 'application/json':
                    raise ConnectError('The Hub returned an unsupported Notes response.')
            reply = json.loads(raw)
            if not isinstance(reply, dict):
                raise ValueError('Expected an object')
            return reply
        except HTTPError as error:
            # Do not copy upstream response text into logs or user-facing errors.
            retry = error.headers.get('Retry-After', '')
            retry_after = min(int(retry), 3600) if retry.isdigit() else 0.0
            status = error.code
            error.close()
            raise HubResponseError(status, 'The Hub refused the Notes request', retry_after=retry_after) from None
        except (URLError, TimeoutError, OSError):
            raise ConnectError('Luma Hub could not be reached. Your notes are kept on this computer.') from None
        except (ValueError, UnicodeError):
            raise ConnectError('Luma Hub returned an invalid Notes response.') from None


@dataclass(frozen=True)
class NotesSession:
    device_id: str
    access_token: str
    account_id: str
    name: str
    hub: str = HUB

    def profile_directory(self, root):
        # Display names and email addresses can change; the server's account
        # identifier determines storage, and never becomes a filesystem name.
        key = hashlib.sha256((self.hub + '\0' + self.account_id).encode()).hexdigest()
        return Path(root) / 'accounts' / key

    def validate(self):
        try:
            uuid.UUID(self.device_id)
        except (ValueError, TypeError, AttributeError):
            raise ConnectError('Invalid Notes device registration.') from None
        if (not isinstance(self.access_token, str) or not 1 <= len(self.access_token) <= 16384
                or any(ord(c) < 33 or ord(c) > 126 for c in self.access_token)
                or not isinstance(self.account_id, str) or not re.fullmatch(r'[0-9a-f]{64}', self.account_id)
                or not isinstance(self.name, str) or len(self.name) > 240 or any(ord(c)<32 for c in self.name)
                or self.hub != hub_url(self.hub)):
            raise ConnectError('Invalid Notes account registration.')
        return self


class NotesAccount:
    """Validate enrollment before persisting it; never mix account libraries."""
    def __init__(self, secrets, client=None):
        self.secrets = secrets
        self.client = client or NotesHubClient()

    def connect(self, code, name='Notes on this computer'):
        if not isinstance(code, str):
            raise ConnectError('Enter the connection code from Luma Hub.')
        code = code.strip().upper()
        if not re.fullmatch(r'[A-Z0-9-]{4,128}', code):
            raise ConnectError('Enter the connection code from Luma Hub.')
        if self.secrets.get() is not None:
            raise ConnectError('Sign out before connecting another Notes account.')
        device_id = str(uuid.uuid4())
        reply = self.client.request('POST', '/api/hub/connect/devices', payload={
            'code': code, 'name': name[:60], 'device_id': device_id, 'scope':'notes'})
        token = reply.get('token')
        if (reply.get('device_id', device_id) != device_id or not isinstance(token, str)
                or not 1 <= len(token) <= 16384 or any(ord(c) < 33 or ord(c) > 126 for c in token)):
            raise ConnectError('The Hub returned an invalid Notes device registration.')
        try:
            account = self.client.request('GET', '/api/hub/sync/account', token=token)
            device = account.get('device')
            if not isinstance(device, dict) or device.get('id') != device_id or device.get('scope') != 'notes':
                raise ConnectError('The Hub returned a different Notes device identity.')
            profile = account.get('profile') or {}
            if not isinstance(profile, dict):
                raise ConnectError('The Hub returned an invalid account profile.')
            identity = account.get('account')
            if not isinstance(identity, dict):
                raise ConnectError('The Hub returned an invalid account identity.')
            name = profile.get('name') or 'Luma account'
            if not isinstance(name,str):
                raise ConnectError('The Hub returned an invalid account name.')
            session = NotesSession(device_id, token, identity.get('id'), name[:240], self.client.origin).validate()
            self.secrets.put(session.__dict__)
            return session
        except Exception:
            # An enrollment which cannot be validated or stored must not leave
            # a usable orphan credential. A network failure never stores it.
            try:
                self.client.request('POST', f'/api/hub/sync/devices/{device_id}/revoke', token=token, payload={})
            except ConnectError:
                pass
            raise

    def saved_session(self):
        value = self.secrets.get()
        if value is None:
            return None
        try:
            session = NotesSession(**value).validate()
        except (TypeError, ValueError):
            raise ConnectError('The saved Notes sign-in could not be read.') from None
        if session.hub != self.client.origin:
            raise ConnectError('The saved Notes sign-in belongs to a different Hub.')
        return session

    def sign_out(self):
        session = self.saved_session()
        if session is None:
            return
        try:
            self.client.request('POST', f'/api/hub/sync/devices/{session.device_id}/revoke',
                                token=session.access_token, payload={})
        except HubResponseError as error:
            if error.status != 401:
                raise
        # A network failure leaves the sign-in available for retry. This method
        # only removes credentials after revocation; it never removes notes.
        self.secrets.delete()


class NotesKeyring:
    """Notes credentials live only in Secret Service, with bounded calls."""
    def __init__(self, origin=HUB):
        import gi
        gi.require_version('Secret', '1')
        from gi.repository import Secret
        self.secret = Secret
        self.schema = Secret.Schema.new('org.projectluma.Notes.Device', Secret.SchemaFlags.NONE,
            {'hub': Secret.SchemaAttributeType.STRING, 'app': Secret.SchemaAttributeType.STRING})
        self.attributes = {'hub': hub_url(origin), 'app': 'org.projectluma.Notes'}

    def _call(self, operation, *args, timeout=5):
        import threading
        from gi.repository import Gio
        cancellable = Gio.Cancellable()
        timer = threading.Timer(timeout, cancellable.cancel)
        timer.daemon = True
        timer.start()
        try:
            return operation(*args, cancellable)
        except Exception:
            raise ConnectError('The desktop keyring is unavailable. Unlock it and try again.') from None
        finally:
            timer.cancel()

    def _collection(self):
        service = self._call(self.secret.Service.get_sync, self.secret.ServiceFlags.OPEN_SESSION)
        return self._call(self.secret.Collection.for_alias_sync, service, 'default', self.secret.CollectionFlags.NONE)

    def _locked(self, collection):
        from gi.repository import Gio, GLib
        if collection is None:
            return False
        # Read the service directly; a proxy cache can lag lock/sign-out events.
        try:
            return collection.call_sync('org.freedesktop.DBus.Properties.Get',
                GLib.Variant('(ss)', ('org.freedesktop.Secret.Collection', 'Locked')),
                Gio.DBusCallFlags.NONE, 1500, None).unpack()[0]
        except GLib.Error:
            raise ConnectError('The desktop keyring is unavailable.') from None

    def get(self):
        collection = self._collection()
        if self._locked(collection):
            raise ConnectError('Unlock the desktop keyring to use your saved Notes sign-in.')
        raw = self._call(self.secret.password_lookup_sync, self.schema, self.attributes)
        if self._locked(collection):
            raise ConnectError('Unlock the desktop keyring to use your saved Notes sign-in.')
        if raw is None:
            return None
        if len(raw) > 32768:
            raise ConnectError('The saved Notes sign-in could not be read.')
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            raise ConnectError('The saved Notes sign-in could not be read.') from None
        if not isinstance(value, dict):
            raise ConnectError('The saved Notes sign-in could not be read.')
        return value

    def put(self, record):
        NotesSession(**record).validate()
        if self._locked(self._collection()):
            raise ConnectError('Unlock the desktop keyring before connecting Notes.')
        raw = json.dumps(record, allow_nan=False)
        if len(raw) > 32768:
            raise ConnectError('The Notes sign-in is too large to store.')
        stored = self._call(self.secret.password_store_sync, self.schema, self.attributes,
            self.secret.COLLECTION_DEFAULT, 'Notes — Luma Hub', raw, timeout=120)
        if not stored:
            raise ConnectError('The Notes sign-in could not be saved in the desktop keyring.')

    def delete(self):
        if self._locked(self._collection()):
            raise ConnectError('Unlock the desktop keyring before signing out of Notes.')
        self._call(self.secret.password_clear_sync, self.schema, self.attributes)

    def unlock(self):
        collection = self._collection()
        if collection is not None and self._locked(collection):
            self._call(self.secret.Service.unlock_sync, collection.get_service(), [collection], timeout=120)
            if self._locked(collection):
                raise ConnectError('The desktop keyring is still locked.')


class NotesBlobClient:
    """Bounded content-addressed attachment transfer on the same Hub origin."""
    MAX_BYTES = 20 * 1024 * 1024

    def __init__(self, client):
        self.client = client

    def transfer(self, method, sha, token, *, data=None, mime='application/octet-stream'):
        if (method not in ('GET', 'PUT') or not isinstance(sha, str)
                or not re.fullmatch(r'[0-9a-f]{64}', sha)
                or not isinstance(token, str) or not 1 <= len(token) <= 16384
                or any(ord(c) < 33 or ord(c) > 126 for c in token)):
            raise ConnectError('Invalid Notes attachment request.')
        if mime not in ('application/octet-stream', 'image/png', 'image/jpeg', 'image/gif', 'image/webp'):
            raise ConnectError('Unsupported Notes attachment type.')
        if method == 'PUT' and (not isinstance(data, bytes) or len(data) > self.MAX_BYTES
                               or hashlib.sha256(data).hexdigest() != sha):
            raise ConnectError('The Notes attachment does not match its reference.')
        request = Request(self.client.origin + '/api/hub/sync/notes/blobs/' + sha,
                          data=data, method=method,
                          headers={'Authorization':'Bearer ' + token, 'Content-Type':mime})
        try:
            with self.client.opener.open(request, timeout=30) as response:
                raw = response.read(self.MAX_BYTES + 1 if method == 'GET' else MAX_REPLY + 1)
                if method == 'GET':
                    if len(raw) > self.MAX_BYTES or hashlib.sha256(raw).hexdigest() != sha:
                        raise ConnectError('The downloaded Notes attachment failed verification.')
                    return raw
                if len(raw) > MAX_REPLY or response.headers.get_content_type() != 'application/json':
                    raise ConnectError('The Hub returned an invalid attachment receipt.')
                receipt = json.loads(raw)
                if not isinstance(receipt, dict) or receipt.get('stored') is not True or receipt.get('sha256') != sha:
                    raise ConnectError('The Hub did not confirm attachment storage.')
                return receipt
        except HTTPError as error:
            status = error.code
            retry = error.headers.get('Retry-After', '')
            retry_after = min(int(retry), 3600) if retry.isdigit() else 0.0
            error.close()
            raise HubResponseError(status, 'The Hub refused the Notes attachment', retry_after=retry_after) from None
        except (URLError, TimeoutError, OSError):
            raise ConnectError('The Notes attachment could not be transferred. It is kept on this computer.') from None
        except (ValueError, UnicodeError):
            raise ConnectError('The Hub returned an invalid attachment receipt.') from None
