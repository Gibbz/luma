# Standalone Notes for Linux

The x86_64 Flatpak and AppImage package Notes from `src/prairie-core/prairie_apps`
in [SimplyLuma/luma](https://github.com/SimplyLuma/luma). Both include selected
GTK, LumaUI, AppKit, Python and Secret Service dependencies. They do not require
the complete Luma Platform or the Luma desktop's account service.

## Install

```sh
flatpak install --user ./Notes-0.1.0-x86_64.flatpak
flatpak run org.projectluma.Notes//standalone
```

Flatpak downloads the shared Freedesktop 25.08 runtime from Flathub if needed.
The release bundle does not configure an application update remote; install
a later release bundle to update it. The sandbox has network and display access
and can use the desktop keyring. File selection uses desktop portals.

Alternatively, make `Notes-0.1.0-x86_64.AppImage` executable and open it.
Without FUSE, use `--appimage-extract-and-run`. The AppImage includes its native
runtime. A desktop Secret Service keyring is required to save an account sign-in.
Credentials are never saved to an unencrypted token file.

## Accounts and sync

Open **Luma account…** from Notes' action menu, open the Hub in your browser,
sign in and enter its one-time connection code. Notes receives a device
credential restricted to Notes, rather than your password or a general account
credential. Sign-out revokes this device and removes its keyring entry.

Each account has its own local cloud library. Existing notes on this computer
are kept separately and are not automatically uploaded when you connect.
The action menu switches between the two libraries. Local copies remain
available offline. Sync preserves conflicting versions as separate pages and
verifies downloaded attachment hashes before applying a page.

Rich document sync requires a Hub supporting Notes metadata version 2, file
attachments, layout version 2 and Notes-scoped device credentials. Older cloud
plain-text pages can be imported. Pages with attachment references but no
position metadata require migration by a compatible client; Notes pauses
instead of guessing their document structure.

## Build

Use a qualified Luma Platform and the standalone GdkPixbuf/SVG loaders described
in `DEPENDENCIES.md`. On a host with `readelf`, schema compilation, Flatpak and
squashfs tools:

```sh
python3 scripts/standalone/build-notes.py \
  --runtime-files PLATFORM_FILES --pixbuf-prefix LOADERS_OUTPUT/install/usr \
  --output Notes
python3 scripts/standalone/build-notes-appimage.py \
  --portable-dir Notes --runtime runtime-x86_64 --output appimage
bash scripts/standalone/build-notes-flatpak.sh Notes flatpak
```

Install Freedesktop 25.08 in the selected Flatpak installation before packaging.
Publication bundles are signed separately through the publisher's signing
infrastructure. The application uses `org.projectluma.Notes.Standalone` on the
session bus so it can run alongside the native OS Notes application.
