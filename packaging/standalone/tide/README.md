# Standalone Tide for Linux

These recipes package the current `src/luma-tide` application for x86_64 Linux.
The application keeps its normal `org.projectluma.Tide` identity. Source,
changes and issue reports remain in the Luma monorepo.

The portable directory contains a selected native dependency closure, LumaUI,
AppKit, fonts, icons, the Python interpreter, Mutagen, audio decoders and
libsecret. It does not require the complete Luma Platform. The AppImage contains
this directory. The Flatpak uses the shared `org.freedesktop.Platform/25.08`
runtime and the `standalone` application branch.

## Build

Use a qualified Luma Platform and matching SDK. Download the pinned GdkPixbuf
archive, SVG loader source and Mutagen wheel listed in `DEPENDENCIES.md` into
an input directory. Inside the SDK, run:

```sh
bash scripts/standalone/build-tide-loaders.sh INPUTS LOADERS_OUTPUT
```

On a build host with `readelf`, `glib-compile-schemas`, Flatpak and squashfs
tools, assemble the directory and downloads:

```sh
python3 scripts/standalone/build-tide.py \
  --runtime-files PLATFORM_FILES \
  --pixbuf-prefix LOADERS_OUTPUT/install/usr \
  --mutagen-wheel INPUTS/mutagen-1.48.1-py3-none-any.whl \
  --output Tide
python3 scripts/standalone/build-tide-appimage.py \
  --portable-dir Tide --runtime runtime-x86_64 --output appimage
bash scripts/standalone/build-tide-flatpak.sh Tide flatpak
```

The AppImage runtime SHA256 is
`156f4bdbde9c52d01814600013e0a273f0118dc2de98975f3c8c63427ec79074`.
Flatpak packaging requires the Freedesktop runtime installed in the selected
Flatpak installation. Release bundles are signed separately through the
publisher's signing infrastructure.

## Install

With Flatpak installed:

```sh
flatpak install --user ./Tide-0.1.0-x86_64.flatpak
flatpak run org.projectluma.Tide//standalone
```

Flatpak may download the shared Freedesktop runtime from Flathub if it is not
already installed. The bundle does not configure an application update remote;
install a later release bundle to update it.

Alternatively, mark `Tide-0.1.0-x86_64.AppImage` executable and open it. Systems
without FUSE can run it with `--appimage-extract-and-run`. The AppImage works
without a separate application runtime. Saved server sign-ins require the
desktop's Secret Service keyring, such as GNOME Keyring or compatible KWallet.

Tide supports local music and Navidrome/Subsonic sources. HTTPS is recommended;
plain HTTP connections require explicit consent in Tide. Flatpak grants access
to Music; use the folder picker to grant access to another location.
