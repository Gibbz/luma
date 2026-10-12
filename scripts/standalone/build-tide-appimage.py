#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package a qualified Tide portable directory as an x86_64 AppImage."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

RUNTIME_SHA256 = '156f4bdbde9c52d01814600013e0a273f0118dc2de98975f3c8c63427ec79074'
REPO = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--portable-dir', required=True, type=Path)
parser.add_argument('--runtime', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
assert hashlib.sha256(args.runtime.read_bytes()).hexdigest() == RUNTIME_SHA256, 'Unexpected AppImage runtime'
args.output.mkdir(parents=True, exist_ok=False)
appdir = args.output / 'AppDir'
shutil.copytree(args.portable_dir, appdir, symlinks=True)
notice = appdir / 'usr/share/licenses/appimage-runtime'
notice.mkdir(parents=True, exist_ok=True)
shutil.copy2(REPO / 'packaging/standalone/tide/appimage-runtime.LICENSE', notice / 'LICENSE')
(appdir / 'AppRun').write_text('''#!/bin/sh
set -eu
tide_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$tide_dir/Tide" "$@"
''')
(appdir / 'AppRun').chmod(0o755)
shutil.copy2(appdir / 'usr/share/applications/org.projectluma.Tide.desktop', appdir)
shutil.copy2(appdir / 'usr/share/icons/hicolor/scalable/apps/org.projectluma.Tide.svg', appdir)
payload = args.output / 'payload.squashfs'
subprocess.run(['mksquashfs', str(appdir), str(payload), '-noappend', '-no-xattrs', '-all-root', '-comp', 'zstd',
                '-Xcompression-level', '15', '-processors', '2'], check=True)
version = (REPO / 'src/luma-tide/luma_tide/__init__.py').read_text().split('__version__ = ')[1].splitlines()[0].strip('"\'')
image = args.output / f'Tide-{version}-x86_64.AppImage'
with image.open('wb') as target:
    for source in (args.runtime, payload):
        with source.open('rb') as stream:
            shutil.copyfileobj(stream, target)
image.chmod(0o755)
print(f'{image.stat().st_size} bytes: {image.name}')
