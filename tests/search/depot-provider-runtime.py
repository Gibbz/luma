#!/usr/bin/python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise catalogue results over the native SearchProvider2 D-Bus interface."""
import os, sys, time, json, tempfile
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
temporary = tempfile.TemporaryDirectory(prefix='depot-provider-')
data = Path(temporary.name)
os.environ['XDG_DATA_HOME'] = str(data / 'share')
applications = data / 'share/applications'
applications.mkdir(parents=True)
record = data / 'launch.json'
launcher = data / 'launcher.py'
launcher.write_text('import json,sys\nfrom pathlib import Path\nPath(' + repr(str(record)) + ').write_text(json.dumps(sys.argv[1:]))\n')
(applications / 'org.projectluma.Depot.desktop').write_text('[Desktop Entry]\nType=Application\nName=Depot\nExec=/usr/bin/python3 ' + str(launcher) + ' %U\n')
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src/luma-search'), str(ROOT / 'src/luma-installer')]
os.environ['LUMA_DEPOT_DATA_DIRECTORY'] = str(ROOT / 'src/luma-installer/data')
from luma_search import depot

connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
with ThreadPoolExecutor(max_workers=2) as pool:
    provider = depot.Provider(pool, lambda: None)
    provider.register(connection)

    def call(method, parameters):
        result = []
        def ready(connection, response):
            try: result.append(connection.call_finish(response).unpack())
            except Exception as error: result.append(error)
        connection.call(connection.get_unique_name(), depot.PATH, depot.INTERFACE,
                        method, parameters, None, Gio.DBusCallFlags.NONE, 3000, None, ready)
        deadline = time.monotonic() + 4
        while not result and time.monotonic() < deadline:
            GLib.MainContext.default().iteration(True)
        assert result, method
        if isinstance(result[0], Exception): raise result[0]
        return result[0]

    ids, = call('GetInitialResultSet', GLib.Variant('(as)', (['blender'],)))
    assert ids, 'shipped catalogue did not return Blender'
    metas, = call('GetResultMetas', GLib.Variant('(as)', (ids,)))
    assert any(item['name'] == 'Blender' for item in metas), metas
    assert all(item['lumaKindLabel'] == 'Depot' for item in metas)
    narrowed, = call('GetSubsearchResultSet', GLib.Variant('(asas)', (ids, ['blender'])))
    assert narrowed == ids
    empty, = call('GetInitialResultSet', GLib.Variant('(as)', (['no-such-app-928573'],)))
    assert not empty
    call('ActivateResult', GLib.Variant('(sasu)', (ids[0], ['blender'], 0)))
    deadline = time.monotonic() + 3
    while not record.exists() and time.monotonic() < deadline:
        time.sleep(.01)
    assert record.exists(), 'Depot activation did not launch the desktop entry'
    assert json.loads(record.read_text()) == ['luma-depot://app/' + quote(ids[0], safe='')]
    record.unlink()
    call('LaunchSearch', GLib.Variant('(asu)', (['blender'], 0)))
    deadline = time.monotonic() + 3
    while not record.exists() and time.monotonic() < deadline:
        time.sleep(.01)
    assert record.exists() and json.loads(record.read_text()) == []
    try:
        call('ActivateResult', GLib.Variant('(sasu)', ('invalid-catalogue-id', [], 0)))
    except GLib.Error:
        pass
    else:
        raise AssertionError('Unknown catalogue item was launched')
temporary.cleanup()
print('PASS Depot SearchProvider2 returns catalogue metadata and handles subsearch/no matches and launches exact app details')
