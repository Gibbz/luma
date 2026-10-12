#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
if [ "$#" != 2 ]; then
    echo "Usage: $0 PORTABLE_DIRECTORY OUTPUT_DIRECTORY" >&2
    exit 2
fi
portable=$(realpath "$1")
output=$(realpath -m "$2")
mkdir "$output"
flatpak build-init "$output/app" org.projectluma.Tide org.freedesktop.Platform org.freedesktop.Platform 25.08
mkdir -p "$output/app/files/bin" "$output/app/files/tide" "$output/app/files/share"
cp -a "$portable/." "$output/app/files/tide/"
for directory in applications metainfo; do
    cp -a "$portable/usr/share/$directory" "$output/app/files/share/"
done
mkdir -p "$output/app/files/share/icons/hicolor/scalable/apps"
cp "$portable/usr/share/icons/hicolor/scalable/apps/org.projectluma.Tide.svg" "$output/app/files/share/icons/hicolor/scalable/apps/"
cat > "$output/app/files/bin/org.projectluma.Tide" <<'LAUNCHER'
#!/bin/sh
exec /app/tide/Tide "$@"
LAUNCHER
chmod +x "$output/app/files/bin/org.projectluma.Tide"
flatpak build-finish --command=org.projectluma.Tide --share=ipc --share=network \
    --socket=wayland --socket=fallback-x11 --socket=pulseaudio --device=dri \
    --filesystem=xdg-music:ro --talk-name=org.freedesktop.secrets \
    --own-name=org.mpris.MediaPlayer2.Tide "$output/app"
flatpak build-export --arch=x86_64 "$output/repo" "$output/app" standalone
flatpak build-bundle "$output/repo" "$output/Tide-0.1.0-x86_64.flatpak" \
    org.projectluma.Tide standalone --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
