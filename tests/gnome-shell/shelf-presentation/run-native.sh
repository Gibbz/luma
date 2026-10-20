#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Run inside an owned disposable native Shell container.
set -euo pipefail
[[ ${LUMA_NATIVE_SHELL_DISPOSABLE:-0} == 1 && $(id -u) == 0 ]]
[[ $(id -u luma-media-test) == 1000 ]]
root=$(cd "$(dirname "$0")" && pwd)
work=${DEV_ARTIFACT_DIR:?}/shelf-presentation
mkdir -p "$work"/{config/glib-2.0/settings,data/applications,runtime}
chmod 700 "$work/runtime"
python3 - "$work" "$root" <<'PY'
from pathlib import Path
import sys, os
work, source = map(Path, sys.argv[1:])
ids = [f'org.projectluma.ShelfProbe{i:02}' for i in range(1, int(os.environ.get('LUMA_SHELF_FAVORITES', '8')) + 1)]
for app in ids:
    (work/'data/applications'/f'{app}.desktop').write_text(f'[Desktop Entry]\nType=Application\nName={app}\nExec=python3 {source}/app.py {app}\nIcon=applications-system-symbolic\nTerminal=false\n')
(work/'config/glib-2.0/settings/keyfile').write_text("[org/project-luma/shell-state]\nsurface-treatment='light'\n\n[org/gnome/shell]\nenabled-extensions=[]\ndisable-user-extensions=true\nwelcome-dialog-last-shown-version='999'\nfavorite-apps="+str([app+'.desktop' for app in ids])+"\n")
if os.environ.get('LUMA_SHELF_REDUCED_MOTION') == '1':
    with (work/'config/glib-2.0/settings/keyfile').open('a') as f:
        f.write("\n[org/gnome/desktop/interface]\nenable-animations=false\n")
PY
cp "$root/native.js" "$work/probe.js"
mkdir -p /run/dbus
if ! dbus-send --system --print-reply --dest=org.freedesktop.DBus / org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1; then
    rm -f /run/dbus/pid /run/dbus/system_bus_socket
    dbus-daemon --system --fork
fi
rpm -q gnome-shell mutter luma-shell-state > "$work/packages.txt"
chown -R 1000:1000 "$work"
monitors=(--virtual-monitor 1920x1080)
if [[ ${LUMA_SHELF_SECOND_MONITOR:-0} == 1 ]]; then
    monitors+=(--virtual-monitor 1600x900)
fi
runuser -u luma-media-test -- env XDG_RUNTIME_DIR="$work/runtime" XDG_CONFIG_HOME="$work/config" \
    XDG_DATA_HOME="$work/data" GSETTINGS_BACKEND=keyfile LIBGL_ALWAYS_SOFTWARE=1 \
    LUMA_MUTTER_ALLOW_SOFTWARE_BLUR=1 LUMA_SHELF_TEST_OUT="$work" \
    LUMA_SHELF_TRACE_LIFT="${LUMA_SHELF_TRACE_LIFT:-0}" \
    LUMA_SHELF_STARTUP_ONLY="${LUMA_SHELF_STARTUP_ONLY:-0}" \
    LUMA_SHELF_REDUCED_MOTION="${LUMA_SHELF_REDUCED_MOTION:-0}" \
    dbus-run-session -- timeout 120 gnome-shell --headless --no-x11 \
    "${monitors[@]}" --automation-script="$work/probe.js" > "$work/shell.log" 2>&1
python3 - "$work/result.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
for item in r['results']:
    print(('PASS' if item['ok'] else 'FAIL')+': '+item['name']+' '+item['detail'])
assert r['pass'], 'native shelf presentation checks failed'
PY
