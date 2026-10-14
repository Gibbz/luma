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
flatpak build-init "$output/app" org.projectluma.VoiceMemos org.gnome.Platform org.gnome.Platform 50
mkdir -p "$output/app/files/bin" "$output/app/files/memos" "$output/app/files/share"
cp -a "$portable/." "$output/app/files/memos/"
for directory in applications metainfo; do
    cp -a "$portable/usr/share/$directory" "$output/app/files/share/"
done
sed -i 's/^Exec=VoiceMemos/Exec=org.projectluma.VoiceMemos/' "$output/app/files/share/applications/org.projectluma.VoiceMemos.desktop"
mkdir -p "$output/app/files/share/icons/hicolor/scalable/apps"
cp "$portable/usr/share/icons/hicolor/scalable/apps/org.projectluma.VoiceMemos.svg" "$output/app/files/share/icons/hicolor/scalable/apps/"
cat > "$output/app/files/bin/org.projectluma.VoiceMemos" <<'LAUNCHER'
#!/bin/sh
cd /
exec /app/memos/VoiceMemos "$@"
LAUNCHER
chmod +x "$output/app/files/bin/org.projectluma.VoiceMemos"
flatpak build-finish --command=org.projectluma.VoiceMemos --share=ipc \
    --socket=wayland --socket=fallback-x11 --device=dri \
    --socket=pulseaudio '--filesystem=xdg-music/Voice Memos:create' "$output/app"
flatpak build-export --arch=x86_64 "$output/repo" "$output/app" standalone
flatpak build-bundle "$output/repo" "$output/VoiceMemos-0.1.1-x86_64.flatpak" \
    org.projectluma.VoiceMemos standalone --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
