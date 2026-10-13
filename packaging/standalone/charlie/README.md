# Standalone Charlie for Linux

Charlie uses the mail client source in `src/external/charlie`. The x86_64 Flatpak
includes its selected LumaUI, GTK and Python dependencies and uses GNOME
Platform 50 for the HTML message renderer.

```sh
flatpak install --user ./Charlie-0.2.14-x86_64.flatpak
flatpak run org.projectluma.Charlie//standalone
```

The shared runtime downloads from Flathub when needed. Install a later release
bundle to update the application.

Accounts and mail data remain in the application's private Flatpak directory.
Saved account credentials use the desktop Secret Service keyring. The
standalone package runs its own mail engine and does not require Luma's mail
host service. It retains the client's existing account providers.

HTML messages disable sender scripts and block remote images until requested.
The application uses network access for mail and the file portal for selected
attachments. It does not receive unrestricted access to the home directory.

To build with a qualified Luma Platform and GdkPixbuf/SVG loader prefix:

```sh
python3 scripts/standalone/build-charlie.py \
  --runtime-files PLATFORM_FILES --pixbuf-prefix LOADERS_OUTPUT/install/usr \
  --output Charlie
bash scripts/standalone/build-charlie-flatpak.sh Charlie flatpak
```

Install GNOME Platform 50 in the selected Flatpak installation first. Release
signing is performed separately by the publisher's signing infrastructure.
