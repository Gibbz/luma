# Notes standalone dependencies

Notes uses selected libraries from the Luma Platform. Included components retain
their notices in `usr/share/licenses`: Python, PyGObject, cairo, GTK, libadwaita,
LumaUI, LumaSemantics, AppKit, GLib, libsecret, fonts, icons and their native
dependencies, including GStreamer libraries linked by GTK. Consult each
component's license for its terms. Audio decoder plugins, Mutagen and OS
account services are not included.

Standalone GdkPixbuf 2.44.8 uses builtin PNG, JPEG and GIF loaders, with Glycin
disabled. Source: [GNOME GdkPixbuf](https://download.gnome.org/sources/gdk-pixbuf/2.44/gdk-pixbuf-2.44.8.tar.xz).
SHA256: `919f529512961a12e81cd4b4b466a48c3933469e7f9a310c6513cd4fb252ba3c`.
The loader build recipe and options are shared with Tide in
`scripts/standalone/build-tide-loaders.sh`.

The unmodified [librsvg SVG loader](https://raw.githubusercontent.com/GNOME/librsvg/9dd24204cc92fbdf1e7566968807e8812a27f292/gdk-pixbuf-loader/io-svg.c)
has SHA256 `fa6a8904dbd2efbe63ea7e28d44d8bd8b5c8a237e18da0dca421534ad298d350`.

The AppImage runtime SHA256 is
`156f4bdbde9c52d01814600013e0a273f0118dc2de98975f3c8c63427ec79074`.
Native libraries are replaceable in the extracted portable directory's
`usr/lib64`. Build recipes remain in the same source repository as Notes.
