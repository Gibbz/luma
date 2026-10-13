# SPDX-License-Identifier: Apache-2.0
"""Open the desktop's online account settings through its application API."""

def open_settings(on_error):
    from gi.repository import Gio, GLib

    def connected(_source, result):
        try:
            connection = Gio.bus_get_finish(result)
        except GLib.Error:
            on_error("Account settings could not connect to the desktop.")
            return

        def activated(connection, result):
            try:
                connection.call_finish(result)
            except GLib.Error:
                on_error("Open Online Accounts in your desktop settings, or configure CalDAV in Evolution.")

        arguments = GLib.Variant('(sava{sv})', (
            'launch-panel', [GLib.Variant('(sav)', ('online-accounts', []))], {}))
        connection.call('org.gnome.Settings', '/org/gnome/Settings',
                        'org.freedesktop.Application', 'ActivateAction', arguments,
                        None, Gio.DBusCallFlags.NONE, 5000, None, activated)

    Gio.bus_get(Gio.BusType.SESSION, None, connected)
    return True
