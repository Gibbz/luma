# Tokay display geometry

This scoped data patch targets gmobile 0.7.3, commit
`d1b0e693807c2c2de8ab34b43060625c6d89d636` from
https://gitlab.gnome.org/World/Phosh/gmobile.

The Google Pixel 9 (`google,tokay`) record uses the saved stock
CP41.260814.003.B1 display diagnostics: 1080 × 2424 pixels, corner radii
132 pixels and a circular cutout centered at (539.5, 86.5), radius 42.
The 65 × 146 mm dimensions agree with the pinned native Tokay panel driver.
Android's parser-only `@left` directive is omitted; SVG commands are expanded
and use uppercase `Z` for the gmobile parser. No Android code is executed.

The patch adds device data to the shared library rather than a phone-only
application or an identifier override. It has passed a native host build,
all seven gmobile component test suites, compiled-resource lookup using the
real Tokay compatible, and standalone parsing by the phone's installed
library. The device data is applied through a GLib resource overlay before the desktop starts.

At scale 3 the pinned Phosh layout policy selects the left clock. Higher
scales need additional layout review: scale 4 cannot fully avoid the cutout
with the present icon widths. An ARM64 cross-build and all seven component suites under QEMU also pass.
On the corrected native RAM boot, the installed library also resolved this
record through a GLib resource overlay using the genuine Tokay compatible.
The live output scale was 3. The owner confirmed that the top-bar clock moved
left, clear of the cutout, and touch still worked after restarting the session.
The installed library was unchanged; this remains a volatile device-data test.
RPM packaging and integration into a persistent image are pending.
