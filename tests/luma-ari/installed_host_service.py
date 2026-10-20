# SPDX-License-Identifier: Apache-2.0
"""Installed session check: native and signed Ari clients reach the host service.

Run as an ordinary graphical-session user after installing the native package
and signed system Ari Flatpak. No D-Bus/session isolation or Flatpak permission
overrides: those would hide failures in the installed systemd service.
"""
import json
import os
from pathlib import Path
import subprocess

from gi.repository import Gio, GLib

BUS = "org.projectluma.Ari1"
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
assert os.getuid() != 0, "Run in the installed ordinary user's session"


def models():
    reply = bus.call_sync(BUS, "/org/projectluma/Ari1", BUS, "Models", None,
                          GLib.VariantType.new("(s)"),
                          Gio.DBusCallFlags.NONE, 30000, None)
    catalogue = json.loads(reply.unpack()[0])
    assert catalogue["models"], "The native service returned an empty catalogue"


def pid(name):
    return bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus",
                         "org.freedesktop.DBus", "GetConnectionUnixProcessID",
                         GLib.Variant("(s)", (name,)),
                         GLib.VariantType.new("(u)"),
                         Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]


models()  # Activate the actual installed systemd service through D-Bus.
daemon = Path(f"/proc/{pid(BUS)}")
broker = Path(f"/proc/{pid('org.freedesktop.DBus')}")
assert daemon.stat().st_uid == os.getuid()
assert os.readlink(daemon / "ns/user") == os.readlink(broker / "ns/user"), (
    "The service cannot inspect signed callers from a sibling user namespace")
status = dict(line.split(":", 1) for line in (daemon / "status").read_text().splitlines()
              if ":" in line)
assert status["NoNewPrivs"].strip() == "1"
assert int(status["CapEff"].strip(), 16) == 0
print("PASS: native catalogue; service shares session user namespace without privileges", flush=True)

# Use the mounted, signed system deployment and its real D-Bus proxy.
probe = '''import json
from gi.repository import Gio, GLib
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
reply = bus.call_sync("org.projectluma.Ari1", "/org/projectluma/Ari1",
    "org.projectluma.Ari1", "Models", None, GLib.VariantType.new("(s)"),
    Gio.DBusCallFlags.NONE, 30000, None)
assert json.loads(reply.unpack()[0])["models"]
print("PASS: signed installed Ari catalogue through the normal Flatpak proxy")
'''
subprocess.run(["flatpak", "run", "--system", "--command=python3",
                "org.projectluma.Ari", "-"], input=probe, text=True,
               check=True, timeout=60)
