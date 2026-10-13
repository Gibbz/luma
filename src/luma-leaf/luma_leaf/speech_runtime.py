# SPDX-License-Identifier: Apache-2.0
"""Connect to the desktop voice service or the standalone basic-voice helper."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import time


def connect(client):
    root = os.environ.get('LUMA_LEAF_SPEECH_ROOT')
    if not root:
        return client.SSIPClient('leaf')
    try:
        return client.SSIPClient('leaf', autospawn=False)
    except Exception:
        pass
    from gi.repository import GLib
    directory = Path(GLib.get_user_runtime_dir()) / 'leaf-voice'
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise RuntimeError('The private voice directory is unavailable.')
    directory.chmod(0o700)
    socket = str(directory / 'speechd.sock')
    try:
        return client.SSIPClient('leaf', autospawn=False, address='unix_socket:' + socket)
    except Exception:
        pass
    base = Path(root)
    environment = os.environ.copy()
    environment['SPEECHD_PLUGIN_DIR'] = str(base / 'usr/lib64/speech-dispatcher')
    process = subprocess.Popen([
        str(base / 'usr/lib64/ld-linux-x86-64.so.2'), '--inhibit-cache',
        '--library-path', str(base / 'usr/lib64'),
        str(base / 'usr/bin/speech-dispatcher'), '--run-single', '--timeout=45',
        '--communication-method=unix_socket', '--socket-path=' + socket,
        '--pid-file=' + str(directory / 'speechd.pid'),
        '--config-dir=' + str(base / 'speech-config'),
        '--module-dir=' + str(base / 'speech-modules'),
        '--log-dir=' + str(directory), '--log-level=0',
    ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True, env=environment)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            return client.SSIPClient('leaf', autospawn=False, address='unix_socket:' + socket)
        except Exception:
            time.sleep(0.1)
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    raise RuntimeError('The basic voice service could not start.')
