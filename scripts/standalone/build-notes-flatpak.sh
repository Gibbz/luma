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
flatpak build-init "$output/app" org.projectluma.Notes org.freedesktop.Platform org.freedesktop.Platform 25.08
mkdir -p "$output/app/files/bin" "$output/app/files/notes" "$output/app/files/share"
cp -a "$portable/." "$output/app/files/notes/"
for directory in applications metainfo; do
    cp -a "$portable/usr/share/$directory" "$output/app/files/share/"
done
sed -i 's/^Exec=Notes /Exec=org.projectluma.Notes /' "$output/app/files/share/applications/org.projectluma.Notes.desktop"
mkdir -p "$output/app/files/share/icons/hicolor/scalable/apps"
cp "$portable/usr/share/icons/hicolor/scalable/apps/org.projectluma.Notes.svg" "$output/app/files/share/icons/hicolor/scalable/apps/"
cat > "$output/app/files/bin/org.projectluma.Notes" <<'LAUNCHER'
#!/bin/sh
exec /app/notes/Notes "$@"
LAUNCHER
chmod +x "$output/app/files/bin/org.projectluma.Notes"
flatpak build-finish --command=org.projectluma.Notes --share=ipc --share=network \
    --socket=wayland --socket=fallback-x11 --device=dri \
    --talk-name=org.freedesktop.secrets "$output/app"
flatpak build-export --arch=x86_64 "$output/repo" "$output/app" standalone
flatpak build-bundle "$output/repo" "$output/Notes-0.1.0-x86_64.flatpak" \
    org.projectluma.Notes standalone --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
