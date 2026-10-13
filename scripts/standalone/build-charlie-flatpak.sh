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
flatpak build-init "$output/app" org.projectluma.Charlie org.gnome.Platform org.gnome.Platform 50
mkdir -p "$output/app/files/bin" "$output/app/files/charlie" "$output/app/files/share"
cp -a "$portable/." "$output/app/files/charlie/"
for directory in applications metainfo; do
    cp -a "$portable/usr/share/$directory" "$output/app/files/share/"
done
sed -i 's/^Exec=Charlie /Exec=org.projectluma.Charlie /' "$output/app/files/share/applications/org.projectluma.Charlie.desktop"
mkdir -p "$output/app/files/share/icons/hicolor/scalable/apps"
cp "$portable/usr/share/icons/hicolor/scalable/apps/org.projectluma.Charlie.svg" "$output/app/files/share/icons/hicolor/scalable/apps/"
cat > "$output/app/files/bin/org.projectluma.Charlie" <<'LAUNCHER'
#!/bin/sh
cd /
exec /app/charlie/Charlie "$@"
LAUNCHER
chmod +x "$output/app/files/bin/org.projectluma.Charlie"
flatpak build-finish --command=org.projectluma.Charlie --share=ipc --share=network \
    --socket=wayland --socket=fallback-x11 --device=dri \
    --talk-name=org.freedesktop.secrets "$output/app"
flatpak build-export --arch=x86_64 "$output/repo" "$output/app" standalone
flatpak build-bundle "$output/repo" "$output/Charlie-0.2.14-x86_64.flatpak" \
    org.projectluma.Charlie standalone --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
