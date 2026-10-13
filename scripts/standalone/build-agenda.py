#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Assemble Agenda and its selected dependencies into a relocatable Linux directory.

Inputs are a qualified Luma Platform, a GdkPixbuf build with builtin PNG/JPEG/GIF
loaders, and an SVG loader. No application code is forked or patched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--application', choices=('Calendar', 'Tasks'), required=True)
parser.add_argument('--runtime-files', required=True, type=Path)
parser.add_argument('--pixbuf-prefix', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
application = args.application
slug = application.lower()
root = args.runtime_files.resolve()
pixbuf = args.pixbuf_prefix.resolve()
dest = args.output.resolve()
assert (root / 'lib/python3.14/site-packages/luma_appkit').is_dir()
dest.mkdir(parents=True, exist_ok=False)

def copy(source, relative):
    target = dest / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__'))
    else:
        shutil.copy2(source, target)

libraries = {p.name: p for p in (root / 'lib64').rglob('*.so*')}
libraries.update({p.name: p for p in (pixbuf / 'lib64').glob('*.so*')})
seeds = [root / 'bin/python3']
for pattern in ('libgtk-4.so.*', 'libadwaita-1.so.*', 'libluma*.so.*',
                'libgirepository*.so.*', 'libcairo*.so.*', 'librsvg*.so.*',
                'libsecret-1.so.*', 'libecal-2.0.so.*', 'libedataserver-1.2.so.*', 'libical-glib.so.*', 'libebook-1.2.so.*', 'libebook-contacts-1.2.so.*'):
    seeds.extend((root / 'lib64').glob(pattern))
seeds.append(pixbuf / 'lib64/libgdk_pixbuf-2.0.so.0')
seeds.extend((root / 'lib64/python3.14/lib-dynload').glob('*.so'))
for package in ('gi', 'cairo'):
    seeds.extend((root / 'lib64/python3.14/site-packages' / package).rglob('*.so'))
seeds.append(root / 'lib64/gio/modules/libgiognutls.so')
svg_loader = pixbuf / 'lib64/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-svg.so'
assert svg_loader.is_file()
seeds.append(svg_loader)
seen, missing, needed, queue = set(), set(), set(), list(seeds)
while queue:
    source = queue.pop().resolve()
    if source in seen:
        continue
    seen.add(source)
    result = subprocess.run(['readelf', '-d', str(source)],
                            capture_output=True, text=True, check=True)
    needed.update(re.findall(r'Library soname: \[(.*?)\]', result.stdout))
    for name in re.findall(r'Shared library: \[(.*?)\]', result.stdout):
        needed.add(name)
        if name in libraries:
            queue.append(libraries[name])
        else:
            missing.add(name)
if missing:
    raise RuntimeError('Missing native dependencies: ' + ', '.join(sorted(missing)))
for source in sorted(seen):
    prefix = pixbuf if source.is_relative_to(pixbuf) else root
    relative = source.relative_to(prefix)
    if relative.parts[0] == 'lib64' and relative.parts[1] in ('samba', 'pulseaudio', 'evolution-data-server'):
        relative = Path('lib64') / source.name
    copy(source, Path('usr') / relative)
for name, source in libraries.items():
    if name in needed and not (dest / 'usr/lib64' / name).exists():
        (dest / 'usr/lib64' / name).symlink_to(source.resolve().name)
for name in ('libpthread.so.0', 'libdl.so.2', 'libgcc_s.so.1', 'ld-linux-x86-64.so.2'):
    copy(root / 'lib64' / name, Path('usr/lib64') / name)
query = subprocess.run([str(root / 'lib64/ld-linux-x86-64.so.2'), '--inhibit-cache',
                        '--library-path', ':'.join(str(p) for p in (pixbuf / 'lib64', root / 'lib64', root / 'lib64/pulseaudio', root / 'lib64/samba')),
                        str(pixbuf / 'bin/gdk-pixbuf-query-loaders'),
                        str(svg_loader)],
                       capture_output=True, text=True, check=True)
(dest / 'pixbuf-loaders.cache').write_text(query.stdout.replace(str(pixbuf), '@AGENDA_ROOT@/usr'))
copy(root / 'lib64/python3.14', 'usr/lib64/python3.14')
site = dest / 'usr/lib64/python3.14/site-packages'
for path in list(site.iterdir()):
    if path.name not in ('gi', 'cairo') and not path.name.startswith(('PyGObject-', 'pycairo-')):
        shutil.rmtree(path) if path.is_dir() else path.unlink()
copy(root / 'lib/python3.14/site-packages/luma_appkit',
     'usr/lib64/python3.14/site-packages/luma_appkit')
# Follow local Python imports, including lazy imports, rather than ship every core app.
import ast
source_package = REPO / 'src/prairie-core/prairie_apps'
pending, modules = [slug, 'agenda_standalone'], set()
while pending:
    name = pending.pop()
    if name in modules:
        continue
    path = source_package / (name + '.py')
    if not path.is_file():
        continue
    modules.add(name)
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            if node.module:
                pending.append(node.module.split('.')[0]) if node.module.split('.')[0] not in {'calendar', 'tasks'} or node.module == slug else None
            else:
                pending.extend(alias.name for alias in node.names if alias.name not in {'calendar', 'tasks'} or alias.name == slug)
for name in sorted(modules | {'__init__'}):
    copy(source_package / (name + '.py'), 'usr/lib64/python3.14/site-packages/prairie_apps/' + name + '.py')
copy(REPO / 'packaging/standalone/agenda/sitecustomize.py',
     'usr/lib64/python3.14/site-packages/sitecustomize.py')
for path in (root / 'share/luma-appkit').glob('*.css'):
    shutil.copy2(path, site / path.name)
for relative in ('share/glib-2.0/schemas', 'share/icons/Prairie', 'share/icons/Adwaita',
                 'share/icons/hicolor', 'share/fonts/google-figtree-fonts', 'share/licenses'):
    copy(root / relative, Path('usr') / relative)
copy(REPO / f'src/prairie-core/style/{slug}.css', f'usr/share/prairie-core/{slug}.css')
copy(REPO / f'assets/icon-theme/Prairie/scalable/apps/org.projectluma.{application}.svg',
     f'usr/share/icons/hicolor/scalable/apps/org.projectluma.{application}.svg')
desktop = (REPO / f'src/prairie-core/data/org.projectluma.{application}.desktop').read_text().replace(f'Exec=prairie-{slug}', f'Exec={application}')
desktop += f'StartupWMClass=org.projectluma.{application}.Standalone\n'
(dest / 'usr/share/applications').mkdir(parents=True, exist_ok=True)
(dest / f'usr/share/applications/org.projectluma.{application}.desktop').write_text(desktop)
copy(REPO / f'packaging/flatpak/apps/org.projectluma.{application}/org.projectluma.{application}.metainfo.xml',
     f'usr/share/metainfo/org.projectluma.{application}.metainfo.xml')
copy(REPO / 'LICENSES', 'usr/share/licenses/luma-source')
subprocess.run(['glib-compile-schemas', str(dest / 'usr/share/glib-2.0/schemas')], check=True)
(dest / 'usr/share/icons/hicolor/icon-theme.cache').unlink(missing_ok=True)
namespaces = ('Gtk-4.0', 'Gdk-4.0', 'Gsk-4.0', 'Adw-1', 'LumaUI-1', 'LumaSemantics-1',
              'LumaAppearance-1', 'GLib-2.0', 'GObject-2.0', 'Gio-2.0', 'GModule-2.0',
              'GLibUnix-2.0', 'GioUnix-2.0', 'GdkPixbuf-2.0', 'Pango-1.0', 'PangoCairo-1.0',
              'PangoFT2-1.0', 'Graphene-1.0', 'cairo-1.0', 'freetype2-2.0', 'HarfBuzz-0.0',
              'GdkX11-4.0', 'GdkWayland-4.0', 'xlib-2.0', 'Secret-1', 'ECal-2.0', 'EDataServer-1.2', 'ICal-3.0', 'ICalGLib-3.0', 'EBook-1.2', 'EBookContacts-1.2', 'Soup-3.0', 'Goa-1.0')
import gi as build_gi
repository = build_gi.Repository.get_default()
repository.prepend_search_path(str(root / 'lib64/girepository-1.0'))
pending_typelibs, seen_typelibs = list(namespaces), set()
while pending_typelibs:
    name = pending_typelibs.pop()
    if name in seen_typelibs:
        continue
    seen_typelibs.add(name)
    path = root / 'lib64/girepository-1.0' / f'{name}.typelib'
    assert path.is_file(), path
    copy(path, Path('usr') / path.relative_to(root))
    namespace, version = name.rsplit('-', 1)
    repository.require(namespace, version)
    pending_typelibs.extend(repository.get_dependencies(namespace))
(dest / 'fonts.conf').write_text('<fontconfig><include ignore_missing="yes">/etc/fonts/fonts.conf</include><dir prefix="relative">usr/share/fonts</dir><cachedir prefix="xdg">fontconfig</cachedir></fontconfig>')
copy(REPO / 'packaging/standalone/agenda/bootstrap.py', 'bootstrap.py')
for cache in dest.rglob('__pycache__'):
    if cache.is_dir():
        shutil.rmtree(cache)
inventory = []
for path in sorted((dest / 'usr/lib64').rglob('*')):
    if path.is_file() and not path.is_symlink() and '.so' in path.name:
        inventory.append({'path': str(path.relative_to(dest)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
(dest / 'native-dependencies.json').write_text(json.dumps(inventory, indent=2) + '\n')
(dest / 'python').write_text('''#!/bin/sh
set -eu
agenda_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
unset PYTHONHOME PYTHONPATH
exec "$agenda_dir/usr/lib64/ld-linux-x86-64.so.2" --inhibit-cache --library-path "$agenda_dir/usr/lib64" "$agenda_dir/usr/bin/python3.14" "$agenda_dir/bootstrap.py" "$@"
''')
(dest / application).write_text(f'''#!/bin/sh
set -eu
agenda_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$agenda_dir/python" -m prairie_apps.agenda_standalone {application} "$@"
''')
for name in ('python', application):
    (dest / name).chmod(0o755)
print(json.dumps({'native_files': len(seen), 'bytes': sum(p.stat().st_size for p in dest.rglob('*') if p.is_file() and not p.is_symlink())}))
