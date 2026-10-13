#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
if [ "$#" != 3 ] || [[ "$1" != Calendar && "$1" != Tasks ]]; then
    echo "Usage: $0 {Calendar|Tasks} PORTABLE_DIRECTORY OUTPUT_DIRECTORY" >&2
    exit 2
fi
application=$1
portable=$(realpath "$2")
output=$(realpath -m "$3")
app_id=org.projectluma.$application
version=$(python3 -c 'import sys,xml.etree.ElementTree as E;print(E.parse(sys.argv[1]).find("releases/release").get("version"))' "$portable/usr/share/metainfo/$app_id.metainfo.xml")
mkdir "$output"
flatpak build-init "$output/app" "$app_id" org.freedesktop.Platform org.freedesktop.Platform 25.08
mkdir -p "$output/app/files/bin" "$output/app/files/agenda" "$output/app/files/share"
cp -a "$portable/." "$output/app/files/agenda/"
for directory in applications metainfo; do
    cp -a "$portable/usr/share/$directory" "$output/app/files/share/"
done
sed -i "s/^Exec=$application/Exec=$app_id/" "$output/app/files/share/applications/$app_id.desktop"
mkdir -p "$output/app/files/share/icons/hicolor/scalable/apps"
cp "$portable/usr/share/icons/hicolor/scalable/apps/$app_id.svg" "$output/app/files/share/icons/hicolor/scalable/apps/"
printf '#!/bin/sh\ncd /\nexec /app/agenda/%s "$@"\n' "$application" > "$output/app/files/bin/$app_id"
chmod +x "$output/app/files/bin/$app_id"
flatpak build-finish --command="$app_id" --share=ipc --share=network \
    --socket=wayland --socket=fallback-x11 --device=dri \
    --talk-name=org.freedesktop.secrets --talk-name=org.gnome.OnlineAccounts \
    --talk-name=org.gnome.evolution.dataserver.Sources5 \
    --talk-name=org.gnome.evolution.dataserver.Calendar8 \
    --talk-name=org.gnome.evolution.dataserver.AddressBook9 \
    '--talk-name=org.gnome.evolution.dataserver.Subprocess.Backend.*' \
    --talk-name=org.gnome.Settings --talk-name=org.gnome.ControlCenter "$output/app"
flatpak build-export --arch=x86_64 "$output/repo" "$output/app" standalone
flatpak build-bundle "$output/repo" "$output/$application-$version-x86_64.flatpak" \
    "$app_id" standalone --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
