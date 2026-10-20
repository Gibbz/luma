#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Filer Space input and Quick View through a filtered session bus."""
import os
import json
from pathlib import Path
import subprocess
import tempfile
import time

import gi
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gio, GLib


def wait(check, label, seconds=20):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(.1)
    raise AssertionError(label)


def visible():
    try:
        reply = Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync('org.gnome.NautilusPreviewer',
            '/org/gnome/NautilusPreviewer', 'org.freedesktop.DBus.Properties', 'Get',
            GLib.Variant('(ss)', ('org.gnome.NautilusPreviewer2', 'Visible')),
            GLib.VariantType.new('(v)'), Gio.DBusCallFlags.NONE, 1000, None)
        return reply.unpack()[0]
    except GLib.Error:
        return False


with tempfile.TemporaryDirectory(prefix='filer-space-') as temporary:
    root = Path(temporary)
    directory = root / 'Preview'
    directory.mkdir()
    image = directory / 'Preview image.png'
    texture = Gdk.MemoryTexture.new(32, 32, Gdk.MemoryFormat.R8G8B8A8,
        GLib.Bytes.new(bytes([70, 150, 210, 255]) * 1024), 128)
    assert texture.save_to_png(str(image))
    socket = root / 'bus'
    manifest = Path(os.environ['LUMA_FILER_MANIFEST']).read_text()
    assert '--talk-name=org.gnome.NautilusPreviewer' in manifest
    assert '--talk-name=org.projectluma.QuickView' not in manifest
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
        'StartServiceByName', GLib.Variant('(su)', ('org.gnome.NautilusPreviewer', 0)),
        None, Gio.DBusCallFlags.NONE, 60000, None)
    assert not visible(), 'Starting the service must not open a preview'
    environment = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=f'unix:path={socket}')
    policy = ['--filter', '--own=org.gnome.Nautilus', '--talk=org.freedesktop.portal.*']
    for argument in json.loads(manifest)['finish-args']:
        if argument.startswith('--talk-name='):
            policy.append(argument.replace('--talk-name=', '--talk=', 1))
        elif argument.startswith('--own-name='):
            policy.append(argument.replace('--own-name=', '--own=', 1))
    old_socket = root / 'old-bus'
    old_policy = [argument.replace('--talk=org.gnome.NautilusPreviewer', '--talk=org.projectluma.QuickView')
                  for argument in policy]
    old_proxy = subprocess.Popen(['xdg-dbus-proxy', os.environ['DBUS_SESSION_BUS_ADDRESS'], str(old_socket), *old_policy])
    try:
        wait(old_socket.exists, 'Old filtered bus did not start')
        old_connection = Gio.DBusConnection.new_for_address_sync(f'unix:path={old_socket}',
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        try:
            old_connection.call_sync('org.gnome.NautilusPreviewer', '/org/gnome/NautilusPreviewer',
                'org.freedesktop.DBus.Properties', 'Get',
                GLib.Variant('(ss)', ('org.gnome.NautilusPreviewer2', 'Visible')),
                GLib.VariantType.new('(v)'), Gio.DBusCallFlags.NONE, 3000, None)
        except GLib.Error:
            pass
        else:
            raise AssertionError('The old permission unexpectedly reached Quick View')
        finally:
            old_connection.close_sync(None)
    finally:
        old_proxy.terminate(); old_proxy.wait(timeout=5)
    proxy = subprocess.Popen(['xdg-dbus-proxy', os.environ['DBUS_SESSION_BUS_ADDRESS'], str(socket), *policy])
    log = open(os.environ.get('LUMA_PREVIEW_LOG', str(root / 'filer.log')), 'w')
    filer = None
    try:
        wait(socket.exists, 'Filtered bus did not start')
        filer = subprocess.Popen([os.environ.get('LUMA_FILER_BINARY', 'nautilus'), '--select', str(image)],
            env=environment, stdout=log, stderr=log)
        def filer_window():
            assert filer.poll() is None, 'Filer exited before mapping; inspect its log'
            result = subprocess.run(['xdotool', 'search', '--onlyvisible', '--class', 'nautilus'],
                capture_output=True, text=True)
            return result.stdout.splitlines()[0] if result.returncode == 0 and result.stdout.strip() else None
        try:
            window = wait(filer_window, 'Filer did not map', seconds=45)
        except AssertionError:
            subprocess.run(['xdotool', 'search', '--name', '.*', 'getwindowname'], check=False)
            raise
        time.sleep(2)
        subprocess.run(['xdotool', 'windowfocus', '--sync', window], check=True)
        subprocess.run(['xdotool', 'key', 'space'], check=True)
        wait(visible, 'Space did not open Quick View through the permitted service', seconds=45)
        def preview_window():
            result = subprocess.run(['xdotool', 'search', '--onlyvisible', '--name', 'Preview image'],
                capture_output=True, text=True)
            return result.stdout.splitlines()[0] if result.returncode == 0 and result.stdout.strip() else None
        preview = wait(preview_window, 'Quick View did not render an image window')
        subprocess.run(['xdotool', 'windowfocus', '--sync', preview], check=True)
        subprocess.run(['xdotool', 'key', 'Escape'], check=True)
        wait(lambda: not visible(), 'Escape did not close Quick View')
        print('Filer Space opened the actual Quick View image window through the manifest bus permission; Escape closed it')
    finally:
        if filer:
            filer.terminate()
            try:
                filer.wait(timeout=5)
            except subprocess.TimeoutExpired:
                filer.kill(); filer.wait()
        proxy.terminate(); proxy.wait(timeout=5); log.close()
