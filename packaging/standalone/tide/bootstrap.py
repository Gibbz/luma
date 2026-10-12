# SPDX-License-Identifier: Apache-2.0
"""Configure dependencies without changing the host process environment."""
import os
from pathlib import Path
import sys

base = Path(__file__).resolve().parent
env = os.environ.copy()
env.update({
    'TIDE_STANDALONE_INITIALIZE': '1',
    'GI_TYPELIB_PATH': str(base / 'usr/lib64/girepository-1.0'),
    'GSETTINGS_SCHEMA_DIR': str(base / 'usr/share/glib-2.0/schemas'),
    'FONTCONFIG_FILE': str(base / 'fonts.conf'),
    'GIO_EXTRA_MODULES': str(base / 'usr/lib64/gio/modules'),
    'GST_PLUGIN_SYSTEM_PATH_1_0': str(base / 'usr/lib64/gstreamer-1.0'),
    'GST_PLUGIN_PATH_1_0': '',
    'GST_REGISTRY_FORK': 'no',
    'XDG_DATA_DIRS': str(base / 'usr/share') + ':' + env.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share'),
})
# OpenSSL builds use different default CA paths across Linux distributions.
if not env.get('SSL_CERT_FILE'):
    for path in ('/etc/ssl/certs/ca-certificates.crt', '/etc/pki/tls/certs/ca-bundle.crt', '/etc/ssl/cert.pem'):
        if Path(path).is_file():
            env['SSL_CERT_FILE'] = path
            break
# The sole dynamic image loader is SVG. PNG/JPEG/GIF are builtin, avoiding a
# separate subprocess and preserving artwork decoding inside Flatpak.
template = (base / 'pixbuf-loaders.cache').read_text()
cache_dir = Path(env.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'luma-tide/portable'
cache_dir.mkdir(parents=True, exist_ok=True)
import hashlib
dependencies = hashlib.sha256((base / 'native-dependencies.json').read_bytes()).hexdigest()[:16]
env['GST_REGISTRY_1_0'] = str(cache_dir / ('gstreamer-' + dependencies + '.bin'))
cache_file = cache_dir / ('pixbuf-' + hashlib.sha256(str(base).encode()).hexdigest()[:16] + '.cache')
cache_text = template.replace('@TIDE_ROOT@', str(base))
if not cache_file.exists() or cache_file.read_text() != cache_text:
    temporary = cache_file.with_suffix('.tmp-' + str(os.getpid()))
    temporary.write_text(cache_text)
    temporary.replace(cache_file)
env['GDK_PIXBUF_MODULE_FILE'] = str(cache_file)
os.execve(str(base / 'usr/lib64/ld-linux-x86-64.so.2'),
          [str(base / 'usr/lib64/ld-linux-x86-64.so.2'), '--inhibit-cache',
           '--library-path', str(base / 'usr/lib64'), str(base / 'usr/bin/python3.14'), *sys.argv[1:]], env)
