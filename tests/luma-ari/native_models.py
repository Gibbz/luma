# SPDX-License-Identifier: Apache-2.0
"""Private bus/display: real Models -> Get -> verified file -> Use, then restart.

Only the fixture daemon's catalogue points to a tiny loopback HTTP payload.
Production catalogue pins and caller authentication are unchanged. No inference
is claimed; the payload deliberately is not a runnable language model.
"""
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

PAYLOAD = b"Ari transport fixture, not a language model.\n" * 4096


def daemon(port):
    from dataclasses import replace
    from ari import cloud, models, service
    d = service.Daemon()
    d.catalogue = [replace(d.catalogue[0], url=f"http://127.0.0.1:{port}/fixture.gguf",
                          size=len(PAYLOAD), sha256=hashlib.sha256(PAYLOAD).hexdigest())]
    d.config.update(brain="openrouter", cloud_model="unavailable/cloud")
    # Reproduce a stalled online refresh without waiting for network timeouts.
    # The main-loop Models method must still answer while this lock is held.
    cloud._catalogue_lock.acquire()
    d.run()


def main():
    if os.getuid() == 0:
        raise RuntimeError("Run the fixture as an ordinary disposable user")
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import GLib, Gtk
    from ari import models, paths
    from ari_ui.lumaui_app import AriApplication, AriWindow

    def settle(predicate, seconds=8):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            if predicate():
                return
            time.sleep(.01)
        raise AssertionError("Ari did not reach the expected state")

    def descendants(widget):
        yield widget
        child = widget.get_first_child()
        while child:
            yield from descendants(child)
            child = child.get_next_sibling()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(PAYLOAD)))
            self.end_headers()
            self.wfile.write(PAYLOAD)
        def log_message(self, *_):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    children = []
    def start():
        p = subprocess.Popen([sys.executable, __file__, "--daemon", str(server.server_port)])
        children.append(p)
        return p
    app = AriApplication()
    assert app.register(None)
    window = AriWindow(app)
    window.state.update(view="models", store="All", q="")
    window.present()
    try:
        # An absent service must offer recovery instead of an empty store.
        settle(lambda: bool(window.models_error))
        assert any(w.get_name() == "ari-retry-models" for w in descendants(window.page))
        service_process = start()
        settle(lambda: not window.models_loading and not window.models_error and bool(window.data["local_models"]))
        identity = window.data["local_models"][0]["id"]
        button = next(w for w in descendants(window.page) if w.get_name() == "ari-get-" + identity)
        assert button.get_sensitive()
        button.emit("clicked")
        settle(lambda: window.data["local_models"][0].get("have"))
        model = models.catalogue()[0]
        assert model.path().read_bytes() == PAYLOAD
        assert model.path().with_suffix(".verified").read_text() == hashlib.sha256(PAYLOAD).hexdigest()
        button = next(w for w in descendants(window.page) if w.get_name() == "ari-use-" + identity)
        button.emit("clicked")
        settle(lambda: window.state["model"] == identity)
        assert json.loads(paths.config_path().read_text())["active_model"] == identity
        print("ARI REAL BUS: offline catalogue, Get, checksum verification and Use PASS", flush=True)
        service_process.terminate()
        service_process.wait(timeout=5)
        settle(lambda: window.daemon.proxy.get_name_owner() is None)
        assert not window.models_error  # normal idle exit retains usable cards
        generation = window.read_generation
        start()
        settle(lambda: window.read_generation > generation and not window.models_loading and not window.models_error)
        assert window.data["local_models"][0]["have"]
        print("ARI REAL BUS: absent service, visible retry and owner restart recovery PASS", flush=True)
    finally:
        window.close()
        for process in children:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        server.shutdown()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        daemon(int(sys.argv[2]))
    else:
        main()
