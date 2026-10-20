#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Launch the installed Settings candidate inside the native Shell fixture.
set -euo pipefail
[[ ${LUMA_NATIVE_SHELL_DISPOSABLE:-0} == 1 && $(id -u) == 0 ]]
root=$(cd "$(dirname "$0")" && pwd)
work=${DEV_ARTIFACT_DIR:?}/border-settings-shell
mkdir -p "$work"/{config/glib-2.0/settings,data/applications,runtime}
printf "[org/gnome/shell]\nenabled-extensions=[]\ndisable-user-extensions=true\nwelcome-dialog-last-shown-version='999'\nfavorite-apps=[]\n" > "$work/config/glib-2.0/settings/keyfile"
chmod 700 "$work/runtime"
cp "$root/native-shell.js" "$work/probe.js"
mkdir -p /run/dbus
if ! dbus-send --system --print-reply --dest=org.freedesktop.DBus / org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1; then
    rm -f /run/dbus/pid /run/dbus/system_bus_socket
    dbus-daemon --system --fork
fi
rpm -q gnome-shell mutter gnome-control-center luma-shell-state > "$work/packages.txt"
chown -R 1000:1000 "$work"
runuser -u luma-media-test -- env XDG_RUNTIME_DIR="$work/runtime" XDG_CONFIG_HOME="$work/config" \
    XDG_DATA_HOME="$work/data" GSETTINGS_BACKEND=keyfile LIBGL_ALWAYS_SOFTWARE=1 \
    LUMA_MUTTER_ALLOW_SOFTWARE_BLUR=1 LUMA_BORDER_SHELL_OUT="$work" \
    dbus-run-session -- timeout 80 gnome-shell --headless --no-x11 \
    --virtual-monitor 1920x1080 --automation-script="$work/probe.js" > "$work/shell.log" 2>&1
python3 - "$work/result.json" <<'PY'
import json, sys
result = json.load(open(sys.argv[1]))
for item in result['results']:
    print(('PASS' if item['ok'] else 'FAIL') + ': ' + item['name'] + ' ' + item['detail'])
assert result['pass'], 'installed Settings checks failed'
PY
