#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reconstruct the reviewed native OSTree source from pinned local archives."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile


def prepare(cache, output):
    repo = Path(__file__).resolve().parents[2]
    config = json.loads((repo / 'config/mobile/fp6-ostree-source.json').read_text())
    if output.exists():
        raise SystemExit('Refusing an existing source output directory')
    # Admit every exact archive before writing a source tree.
    for row in config['archives']:
        archive = cache / (row['name'] + '.tar.gz')
        if hashlib.sha256(archive.read_bytes()).hexdigest() != row['sha256']:
            raise SystemExit('Pinned source checksum mismatch: ' + row['name'])
    output.mkdir(parents=True)
    for row in config['archives']:
        dest = output / row['destination']
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(cache / (row['name'] + '.tar.gz')) as archive:
            members = archive.getmembers()
            prefix = members[0].name.split('/')[0] + '/'
            selected = []
            for member in members:
                if member.name.rstrip('/') == prefix.rstrip('/'):
                    continue
                if not member.name.startswith(prefix):
                    raise SystemExit('Unexpected archive prefix')
                member.name = member.name[len(prefix):]
                selected.append(member)
            archive.extractall(dest, members=selected, filter='data')
    patches = repo / 'patches/ostree'
    for patch in sorted(patches.glob('*.patch')):
        with patch.open('rb') as stream:
            subprocess.run(['patch', '--batch', '--forward', '-p1'], cwd=output,
                           stdin=stream, check=True)
    for name in ('luma-aboot-overlay-native-control.c', 'luma-test-aboot-overlay-native.py'):
        shutil.copy2(patches / name, output / 'tests' / name)
    rows = []
    for path in sorted(output.rglob('*')):
        rel = str(path.relative_to(output))
        if path.is_symlink():
            rows.append([rel, 'link', str(path.readlink())])
        elif path.is_file():
            rows.append([rel, 'file', hashlib.sha256(path.read_bytes()).hexdigest()])
    actual = hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()
    if len(rows) != config['source_entries'] or actual != config['source_tree_sha256']:
        raise SystemExit('Prepared source differs from the qualified source tree')
    print(json.dumps({'source_tree_sha256': actual, 'entries': len(rows),
                      'version': config['version'], 'output': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.cache.resolve(), args.output.resolve())
