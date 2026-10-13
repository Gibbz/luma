# SPDX-License-Identifier: Apache-2.0
import http.server
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request
from luma_leaf import opds

class Transport(unittest.TestCase):
    def setUp(self):
        self.seen=[]
        seen=self.seen
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.server.server_port,self.path,self.headers.get('Authorization')))
                if self.path.startswith('/redirect/'):
                    self.send_response(302)
                    self.send_header('Location',self.path.removeprefix('/redirect/'))
                    self.end_headers()
                else:
                    self.send_response(200);self.end_headers();self.wfile.write(b'book')
            def log_message(self,*args):pass
        self.servers=[http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler) for _ in range(2)]
        for server in self.servers:threading.Thread(target=server.serve_forever,daemon=True).start()
        self.origins=[f'http://127.0.0.1:{s.server_port}' for s in self.servers]
    def tearDown(self):
        for server in self.servers:server.shutdown();server.server_close()
    def test_same_origin_redirect_keeps_authentication(self):
        opds._fetch(self.origins[0]+'/redirect/'+self.origins[0]+'/book','reader','fixture')
        self.assertTrue(all(item[2] for item in self.seen))
    def test_cross_origin_redirect_does_not_receive_credentials(self):
        opds._fetch(self.origins[0]+'/redirect/'+self.origins[1]+'/book','reader','fixture')
        self.assertTrue(self.seen[0][2]);self.assertIsNone(self.seen[1][2])
    def test_catalogue_external_download_does_not_receive_credentials(self):
        opds._fetch(self.origins[1]+'/book','reader','fixture',auth_origin=self.origins[0])
        self.assertIsNone(self.seen[0][2])
    def test_https_links_and_redirects_cannot_downgrade(self):
        with self.assertRaises(opds.SourceError):
            opds._fetch(self.origins[0]+'/book','reader','fixture',auth_origin='https://example.com/catalogue')
        request=Request('https://example.com/book',headers={'Authorization':'Basic fixture'})
        with self.assertRaises(opds.SourceError):
            opds._LibraryRedirects().redirect_request(request,None,302,'Found',{},'http://example.com/book')
    def test_embedded_password_is_refused(self):
        with self.assertRaises(opds.SourceError):opds._fetch('https://reader:fixture@example.com/book','','')

class KeyringFailures(unittest.TestCase):
    def test_refused_storage_is_not_success(self):
        class Secret:
            COLLECTION_DEFAULT='default'
            @staticmethod
            def password_store_sync(*args):return False
        with patch.object(opds,'_secret',return_value=(Secret,object())):
            with self.assertRaises(opds.SourceError):opds.store_password('fixture','fixture')
    def test_missing_service_has_a_readable_error(self):
        with patch.object(opds,'_secret',side_effect=RuntimeError('unavailable')):
            with self.assertRaises(opds.SourceError):opds.store_password('fixture','fixture')
