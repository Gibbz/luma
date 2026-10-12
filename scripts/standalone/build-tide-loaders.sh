#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Run inside the qualified Luma SDK; the output is a DESTDIR prefix.
set -euo pipefail
if [ "$#" != 2 ]; then
    echo "Usage: $0 INPUT_DIRECTORY OUTPUT_DIRECTORY" >&2
    exit 2
fi
inputs=$(realpath "$1")
output=$(realpath -m "$2")
mkdir "$output"
python3 - "$inputs" <<'PY'
import hashlib,sys
from pathlib import Path
root=Path(sys.argv[1])
for filename,digest in (
    ('gdk-pixbuf-2.44.8.tar.xz','919f529512961a12e81cd4b4b466a48c3933469e7f9a310c6513cd4fb252ba3c'),
    ('io-svg.c','fa6a8904dbd2efbe63ea7e28d44d8bd8b5c8a237e18da0dca421534ad298d350')):
    assert hashlib.sha256((root/filename).read_bytes()).hexdigest()==digest,filename
PY
mkdir "$output/source"
tar -xf "$inputs/gdk-pixbuf-2.44.8.tar.xz" --strip-components=1 -C "$output/source"
meson setup "$output/build" "$output/source" --prefix=/usr --libdir=lib64 --wrap-mode=nofallback \
    -Dglycin=disabled -Dpng=enabled -Djpeg=enabled -Dgif=enabled -Dtiff=disabled \
    -Dothers=disabled -Dbuiltin_loaders=png,jpeg,gif -Drelocatable=true \
    -Dintrospection=disabled -Dtests=false -Dinstalled_tests=false -Dman=false -Dthumbnailer=disabled
meson compile -C "$output/build" -j2
DESTDIR="$output/install" meson install -C "$output/build"
prefix="$output/install/usr"
mkdir -p "$prefix/lib64/gdk-pixbuf-2.0/2.10.0/loaders"
cc -shared -fPIC -O2 -DGDK_PIXBUF_ENABLE_BACKEND -I"$prefix/include/gdk-pixbuf-2.0" \
    $(pkg-config --cflags librsvg-2.0 gdk-pixbuf-2.0) "$inputs/io-svg.c" \
    -o "$prefix/lib64/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-svg.so" \
    -L"$prefix/lib64" $(pkg-config --libs librsvg-2.0 gdk-pixbuf-2.0)
