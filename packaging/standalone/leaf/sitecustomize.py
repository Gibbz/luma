# SPDX-License-Identifier: Apache-2.0
"""Initialize portable modules and use the desktop's CA trust file."""
import os

if os.environ.pop('LEAF_STANDALONE_INITIALIZE', None) == '1':
    import gi
    gi.require_version('Gio', '2.0')
    gi.require_version('GdkPixbuf', '2.0')
    from gi.repository import Gio, GdkPixbuf

    # A Fedora-built GnuTLS cannot assume Fedora trust paths or crypto-policy
    # files on another distribution. Keep certificate verification enabled.
    os.environ.setdefault('G_TLS_GNUTLS_PRIORITY', 'NORMAL')
    ca_file = os.environ.get('SSL_CERT_FILE')
    if ca_file:
        database = Gio.TlsFileDatabase.new(ca_file)
        Gio.TlsBackend.get_default().set_default_database(database)
    Gio.SettingsSchemaSource.get_default()
    GdkPixbuf.Pixbuf.get_formats()
    # These paths have now been read by the native repositories. Do not pass
    # bundled module overrides to host applications launched through GIO.
    for name in ('GI_TYPELIB_PATH', 'GIO_EXTRA_MODULES', 'GSETTINGS_SCHEMA_DIR',
                 'GDK_PIXBUF_MODULE_FILE', 'GST_PLUGIN_SYSTEM_PATH_1_0',
                 'GST_PLUGIN_PATH_1_0', 'GST_REGISTRY_1_0', 'GST_REGISTRY_FORK'):
        os.environ.pop(name, None)
