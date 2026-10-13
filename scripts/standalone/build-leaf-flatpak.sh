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
flatpak build-init "$output/app" org.projectluma.Leaf org.gnome.Platform org.gnome.Platform 50
mkdir -p "$output/app/files/bin" "$output/app/files/leaf" "$output/app/files/share"
cp -a "$portable/." "$output/app/files/leaf/"
for directory in applications metainfo; do
    cp -a "$portable/usr/share/$directory" "$output/app/files/share/"
done
sed -i 's/^Exec=Leaf /Exec=org.projectluma.Leaf /' "$output/app/files/share/applications/org.projectluma.Leaf.desktop"
mkdir -p "$output/app/files/share/icons/hicolor/scalable/apps"
cp "$portable/usr/share/icons/hicolor/scalable/apps/org.projectluma.Leaf.svg" "$output/app/files/share/icons/hicolor/scalable/apps/"
cat > "$output/app/files/bin/org.projectluma.Leaf" <<'LAUNCHER'
#!/bin/sh
cd /
exec /app/leaf/Leaf "$@"
LAUNCHER
chmod +x "$output/app/files/bin/org.projectluma.Leaf"
flatpak build-finish --command=org.projectluma.Leaf --share=ipc --share=network \
    --socket=wayland --socket=fallback-x11 --device=dri \
    --socket=pulseaudio --filesystem=xdg-run/speech-dispatcher \
    --filesystem=~/Books:ro --talk-name=org.freedesktop.secrets \
    --own-name=org.mpris.MediaPlayer2.leaf.Standalone \
    --talk-name=org.freedesktop.portal.Flatpak "$output/app"
flatpak build-export --arch=x86_64 "$output/repo" "$output/app" standalone
flatpak build-bundle "$output/repo" "$output/Leaf-0.1.0-x86_64.flatpak" \
    org.projectluma.Leaf standalone --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
