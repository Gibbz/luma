#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Root inside a disposable fixture with the candidate packages installed only.
set -euo pipefail
[[ ${LUMA_NATIVE_SHELL_DISPOSABLE:-0} == 1 && $(id -u) == 0 ]]
[[ $(id -u luma-media-test) == 1000 ]]
test_primary=${LUMA_TILING_TEST_PRIMARY:-1920x1080}
[[ $test_primary =~ ^[0-9]+x[0-9]+$ ]]
root=$(cd "$(dirname "$0")" && pwd)
work=${DEV_ARTIFACT_DIR:?}/tiling-editor-native
mkdir -p "$work"/{config/glib-2.0/settings,data,runtime}
chmod 700 "$work/runtime"
rpm -q gnome-shell mutter gnome-shell-extension-tiling-shell gnome-shell-extension-luma-tiling-toggle > "$work/packages.txt"
. "$root/../../../config/desktop/inputs.env"
rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n' gnome-shell-extension-tiling-shell | grep -Fx "$TILING_SHELL_NEVRA"
rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n' gnome-shell-extension-luma-tiling-toggle | grep -Fx "$LUMA_TILING_TOGGLE_NEVRA"
cat > "$work/config/glib-2.0/settings/keyfile" <<'K'
[org/project-luma/shell-state]
surface-treatment='light'

[org/gnome/shell]
enabled-extensions=['tilingshell@ferrarodomenico.com', 'tiling-toggle@project-luma.local']
disable-user-extensions=false
welcome-dialog-last-shown-version='999'
K
cp "$root/native.js" "$work/probe.js"
mkdir -p /run/dbus
if ! dbus-send --system --print-reply --dest=org.freedesktop.DBus / org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1; then
 rm -f /run/dbus/pid /run/dbus/system_bus_socket
 dbus-daemon --system --fork
fi
chown -R 1000:1000 "$work"
runuser -u luma-media-test -- env XDG_RUNTIME_DIR="$work/runtime" XDG_CONFIG_HOME="$work/config" \
 XDG_DATA_HOME="$work/data" GSETTINGS_BACKEND=keyfile LIBGL_ALWAYS_SOFTWARE=1 \
 LUMA_MUTTER_ALLOW_SOFTWARE_BLUR=1 LUMA_TILING_EDITOR_OUT="$work" \
 dbus-run-session -- timeout 150 gnome-shell --headless --no-x11 \
 --virtual-monitor "$test_primary" --virtual-monitor 1600x900 --virtual-monitor 1280x800 \
 --automation-script="$work/probe.js" > "$work/shell.log" 2>&1
python3 - "$work/result.json" <<'PY'
import json, sys
r=json.load(open(sys.argv[1]))
for c in r['results']:
 print(('PASS' if c['ok'] else 'FAIL')+': '+c['name']+' '+c.get('detail',''))
assert r['pass'], 'native editor regression failed'
PY
