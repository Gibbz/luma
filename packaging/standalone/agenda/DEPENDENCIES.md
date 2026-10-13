# Calendar and Tasks standalone dependencies

The bundles contain selected Luma Platform libraries: GTK, libadwaita, LumaUI,
LumaSemantics, AppKit, Python, PyGObject, cairo, GLib, libsecret and Evolution
Data Server client libraries, with their native dependencies. EDS server
processes and desktop Online Accounts remain host services. Included notices
are retained under `usr/share/licenses`; consult each component's license.

The Freedesktop Platform 25.08 runtime is shared. Its source is maintained by
the Freedesktop SDK project. The application release includes a native file
inventory and corresponding dependency source inputs.

GTK and libadwaita use the upstream source RPMs, Luma patches and build recipes
pinned in `config/desktop/inputs.env`, `scripts/packages/build-gtk4.sh` and
`scripts/packages/build-libadwaita.sh`. The source receipt distinguishes these
custom builds from their upstream RPM inputs.

Standalone GdkPixbuf 2.44.8 provides builtin PNG, JPEG and GIF loaders with
Glycin disabled. Its upstream archive SHA256 is
`919f529512961a12e81cd4b4b466a48c3933469e7f9a310c6513cd4fb252ba3c`.
The unmodified librsvg `io-svg.c` loader SHA256 is
`fa6a8904dbd2efbe63ea7e28d44d8bd8b5c8a237e18da0dca421534ad298d350`.
The source URLs and build options are documented in
`packaging/standalone/notes/DEPENDENCIES.md` and
`scripts/standalone/build-tide-loaders.sh`.

Native libraries can be replaced in the portable directory's `usr/lib64`.
The application, shared UI and packaging source remain in the Luma repository.
