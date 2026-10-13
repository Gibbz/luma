# Standalone Calendar and Tasks for Linux

Calendar and Tasks package their existing responsive applications with selected
LumaUI, AppKit, GTK, Python and Evolution Data Server client dependencies. They
use the shared Freedesktop Platform 25.08 runtime and do not require Luma Platform.

## Desktop services and accounts

Evolution Data Server must be installed and running on the host. It stores the
calendars, task lists, offline caches and account configuration. The standalone
apps access the same calendars and lists as other desktop EDS clients. This is
shared desktop data, rather than an isolated copy inside each Flatpak.

On GNOME, use Online Accounts in desktop settings to connect supported providers,
such as Google or Nextcloud. Calendar's Add calendar control and Tasks' Accounts
command open that panel through its D-Bus application interface. Other CalDAV
accounts can be configured in Evolution. Provider credentials are managed by
those desktop services and their keyring. These bundles do not install Luma
Connect or provide a separate Luma Hub browser sign-in.

Calendar keeps timed events in named time zones and all-day events as dates.
Tasks uses standard VTODO records. Existing desktop CalDAV sources continue to
sync through EDS; local calendars and lists remain available offline.

## Install

Download the application bundle and install it with:

```sh
flatpak install --user ./Calendar-0.1.1-x86_64.flatpak
flatpak run org.projectluma.Calendar//standalone

flatpak install --user ./Tasks-0.1.2-x86_64.flatpak
flatpak run org.projectluma.Tasks//standalone
```

The shared runtime downloads from Flathub when needed. Install a later bundle
to update an application; these bundles do not add an application update remote.
They request display, network, desktop account/keyring and EDS D-Bus access.
They do not request the host filesystem or the Luma account device token.

## Build

The build host needs PyGObject, readelf, schema compilation and Flatpak tools.
Use the qualified Luma Platform and standalone GdkPixbuf/SVG inputs documented
in `packaging/standalone/agenda/DEPENDENCIES.md`.

```sh
python3 scripts/standalone/build-agenda.py --application Calendar \
  --runtime-files PLATFORM_FILES --pixbuf-prefix LOADERS_OUTPUT/install/usr \
  --output Calendar
bash scripts/standalone/build-agenda-flatpak.sh Calendar Calendar calendar-flatpak
```

Use `Tasks` instead of `Calendar` for the second application. Native client
libraries are selected by their actual dependencies; local Python imports are
followed so unrelated core application code is omitted. The release source
receipt records packaged source and native file hashes. Signing is performed
separately by the publisher's release infrastructure.
