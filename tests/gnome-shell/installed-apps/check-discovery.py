#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise Applications and Search discovery against live desktop exports."""
import importlib.util
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

if 'LUMA_EXPORT_DISCOVERY_CHILD' not in os.environ:
    with tempfile.TemporaryDirectory(prefix='luma-export-discovery-') as directory:
        root = Path(directory)
        (root / 'data/applications').mkdir(parents=True)
        environment = dict(os.environ, LUMA_EXPORT_DISCOVERY_CHILD=directory,
                           XDG_DATA_HOME=str(root / 'data'),
                           XDG_DATA_DIRS=':'.join(str(root / scope / 'flatpak/exports/share')
                                                 for scope in ('user', 'system')))
        raise SystemExit(subprocess.run([sys.executable, __file__], env=environment).returncode)

from gi.repository import Gio, GLib
root = Path(os.environ['LUMA_EXPORT_DISCOVERY_CHILD'])
repo = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('application_directory',
    repo / 'src/luma-installer/luma_installer/application_directory.py')
directory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(directory)
search = runpy.run_path(str(repo / 'src/luma-search/luma-search-service'))['SearchService']
monitor = Gio.AppInfoMonitor.get()
changes = []
monitor.connect('changed', lambda *_: changes.append(GLib.get_monotonic_time()))
context = GLib.MainContext.default()

def wait_for(test):
    end = GLib.get_monotonic_time() + 1500000
    while not test() and GLib.get_monotonic_time() < end:
        while context.pending():
            context.iteration(False)
        GLib.usleep(10000)
    assert test(), 'desktop export was not refreshed within 1.5 seconds'

def application_ids():
    return {row[0] for row in directory.application_rows('')}

def search_ids():
    return {row.application_id for row in search._query_apps(1)}

assert application_ids() == set()
assert search_ids() == set()
for scope in ('user', 'system'):
    identity = f'org.projectluma.FlatpakProbe.{scope}.desktop'
    exported = root / scope / 'flatpak/exports/share/applications' / identity
    exported.parent.mkdir(parents=True)
    deployed = root / f'{scope}-deployment.desktop'
    deployed.write_text(f'[Desktop Entry]\nType=Application\nName=FlatpakProbe{scope}\nExec=/bin/true\nIcon=applications-games-symbolic\nCategories=Game;\n')
    before = len(changes)
    exported.symlink_to(deployed)
    wait_for(lambda: len(changes) > before and identity in application_ids() and identity in search_ids())
    assert len(changes) > before, 'installation did not notify live application clients'
    print(f'PASS: {scope} exported launcher appears in Applications and Search without launch', flush=True)
    exported.unlink()
    wait_for(lambda: identity not in application_ids() and identity not in search_ids())
    print(f'PASS: {scope} removed launcher disappears from Applications and Search', flush=True)
