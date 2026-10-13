#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package a qualified Notes portable directory as an x86_64 AppImage."""
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
shutil.copy2(REPO / 'packaging/standalone/notes/appimage-runtime.LICENSE', notice / 'LICENSE')
(appdir / 'AppRun').write_text('''#!/bin/sh
set -eu
notes_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$notes_dir/Notes" "$@"
''')
(appdir / 'AppRun').chmod(0o755)
shutil.copy2(appdir / 'usr/share/applications/org.projectluma.Notes.desktop', appdir)
shutil.copy2(appdir / 'usr/share/icons/hicolor/scalable/apps/org.projectluma.Notes.svg', appdir)
payload = args.output / 'payload.squashfs'
subprocess.run(['mksquashfs', str(appdir), str(payload), '-noappend', '-no-xattrs', '-all-root', '-comp', 'zstd',
                '-Xcompression-level', '15', '-processors', '2'], check=True)
version = next(line.split()[1] for line in (REPO / 'packaging/rpm/prairie-core-apps.spec').read_text().splitlines() if line.startswith('Version:'))
image = args.output / f'Notes-{version}-x86_64.AppImage'
with image.open('wb') as target:
    for source in (args.runtime, payload):
        with source.open('rb') as stream:
            shutil.copyfileobj(stream, target)
image.chmod(0o755)
print(f'{image.stat().st_size} bytes: {image.name}')
