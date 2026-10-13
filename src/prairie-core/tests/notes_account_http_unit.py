# SPDX-License-Identifier: Apache-2.0
"""Real loopback HTTP checks for credential redirect and response boundaries."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import unittest
from prairie_apps.notes_account import NotesHubClient
from prairie_apps.connect_sync import ConnectError, HubResponseError


@contextmanager
def serve(handler):
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try: yield 'http://127.0.0.1:'+str(server.server_port)
    finally: server.shutdown();server.server_close();thread.join(2)


class QuietHandler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass


class TransportTests(unittest.TestCase):
    def test_cross_origin_redirect_never_receives_a_device_bearer(self):
        received=[]
        class Destination(QuietHandler):
            def do_GET(self):
                received.append(self.headers.get('Authorization'));self.send_response(200);self.end_headers()
        with serve(Destination) as destination:
            class Redirect(QuietHandler):
                def do_GET(self):
                    self.send_response(302);self.send_header('Location',destination+'/api/hub/sync/account');self.end_headers()
            with serve(Redirect) as origin:
                client=NotesHubClient(origin)
                with self.assertRaises(HubResponseError) as error:
                    client.request('GET','/api/hub/sync/account',token='synthetic-credential')
                self.assertEqual(error.exception.status,302)
        self.assertEqual(received,[])

    def test_invalid_json_response_never_becomes_an_account(self):
        class Invalid(QuietHandler):
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'[]')
        with serve(Invalid) as origin:
            with self.assertRaises(ConnectError): NotesHubClient(origin).request('GET','/api/hub/sync/account')

    def test_html_fallback_is_refused(self):
        class Html(QuietHandler):
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(b'Account sign-in')
        with serve(Html) as origin:
            with self.assertRaises(ConnectError): NotesHubClient(origin).request('GET','/api/hub/sync/account')

    def test_rate_limit_is_preserved_without_exposing_server_response(self):
        class Limited(QuietHandler):
            def do_GET(self):
                self.send_response(429);self.send_header('Retry-After','120');self.end_headers();self.wfile.write(b'Private response content')
        with serve(Limited) as origin:
            with self.assertRaises(HubResponseError) as error: NotesHubClient(origin).request('GET','/api/hub/sync/account')
            self.assertEqual(error.exception.retry_after,120)
            self.assertNotIn('Private response content',str(error.exception))


if __name__=='__main__': unittest.main(verbosity=2)
