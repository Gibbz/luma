#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-or-later
import sys
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
app = Gtk.Application(application_id=sys.argv[1])
def activate(application):
    window = Gtk.ApplicationWindow(application=application, title='Shelf test')
    window.set_default_size(400, 300)
    window.present()
app.connect('activate', activate)
app.run([sys.argv[0]])
