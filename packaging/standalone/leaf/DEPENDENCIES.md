# Leaf standalone dependencies

The application includes selected Python, PyGObject, cairo, GTK, libadwaita,
LumaUI, LumaSemantics, AppKit, GLib, libsecret, fonts and icons from the qualified
Luma Platform. Component notices remain in `usr/share/licenses`. The shared
GNOME Platform 50 supplies WebKit, JavaScriptCore and their process sandbox.
Their sources follow the GNOME/Flathub runtime's source publication.

The Python standard library retains sourceless `.pyc` modules from its qualified
input. Fedora packages some codecs that way; removing all bytecode omits CP437,
which the ZIP reader needs for EPUB filename decoding.

GdkPixbuf 2.44.8 uses builtin PNG, JPEG and GIF loaders and the unmodified librsvg
SVG loader, shared with Tide. Input hashes and the build recipe are documented
in `packaging/standalone/tide/DEPENDENCIES.md` and
`scripts/standalone/build-tide-loaders.sh`.

Speech Dispatcher 0.12.1 Python client:

- Fedora `python3-speechd-0.12.1-6.fc44.x86_64.rpm`, SHA256
  `62f0ec981c5ab8f8fe39c56985bebff36e1118e3eb67ba49aad7b7097a8cb124`.
- Corresponding `speech-dispatcher-0.12.1-6.fc44.src.rpm`, SHA256
  `a48d9b9b9dbf13db44116ebceb4bedf84216367d08ae7db0731b6954a27f2f39`.

The optional private fallback includes Speech Dispatcher 0.12.1, eSpeak NG
1.52.0, Dotconf 1.4.1 and Pcaudiolib 1.1. Package versions and SHA256 hashes are
recorded in the release source receipt. It includes eSpeak's dictionaries and
uses the desktop's PulseAudio socket. Other synthesis engines, neural voice
models and OS account services are not bundled.

These inputs are available from Fedora Koji. The speech components retain
their GPL notices; corresponding source RPMs accompany the release together
with the other included dependencies. Application and packaging source remain
in the Luma repository at the release tag.
