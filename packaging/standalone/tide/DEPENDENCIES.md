# Tide standalone dependencies

Tide uses selected libraries from the Luma Platform rather than distributing the
complete platform. Its application source remains `src/luma-tide` in
[SimplyLuma/luma](https://github.com/SimplyLuma/luma).

Included components retain their notices in `usr/share/licenses`: Python,
PyGObject, cairo, GTK, libadwaita, LumaUI, LumaSemantics, AppKit, GLib,
GStreamer and selected audio plugins, FFmpeg, libsecret, font and icon assets,
and their native dependencies. Mutagen is GPL-2.0-or-later. Consult each
component's license for its terms.

Standalone GdkPixbuf 2.44.8 is built from
[GNOME's source](https://download.gnome.org/sources/gdk-pixbuf/2.44/gdk-pixbuf-2.44.8.tar.xz)
with builtin PNG, JPEG and GIF loaders and Glycin disabled. SHA256:
`919f529512961a12e81cd4b4b466a48c3933469e7f9a310c6513cd4fb252ba3c`.
Build options: `--prefix=/usr --libdir=lib64 --wrap-mode=nofallback
-Dglycin=disabled -Dpng=enabled -Djpeg=enabled -Dgif=enabled -Dtiff=disabled
-Dothers=disabled -Dbuiltin_loaders=png,jpeg,gif -Drelocatable=true
-Dintrospection=disabled -Dtests=false -Dinstalled_tests=false -Dman=false
-Dthumbnailer=disabled`. The SVG loader is built from unmodified upstream
[librsvg io-svg.c](https://raw.githubusercontent.com/GNOME/librsvg/9dd24204cc92fbdf1e7566968807e8812a27f292/gdk-pixbuf-loader/io-svg.c),
SHA256 `fa6a8904dbd2efbe63ea7e28d44d8bd8b5c8a237e18da0dca421534ad298d350`.

Mutagen 1.48.1 wheel SHA256:
`4f077fe87d3fc7fba259aa63d8c026b18382ca6a42ef37c61e16f1b1b5b82fe7`.
[Corresponding source](https://files.pythonhosted.org/packages/df/70/1675da133ea92227da41bf5b24e1c66be597ff736a1533ade41da986852f/mutagen-1.48.1.tar.gz)
SHA256: `8f95637ab9f6f305cec6bd1294e197debe207998e3e068596563c74f86b0a173`.

Native libraries are replaceable in the extracted portable directory's
`usr/lib64`; the launcher selects them without changing the host's library
search path. Build and packaging recipes are in `scripts/standalone`.
