#!/usr/bin/python3
# SPDX-License-Identifier: Apache-2.0
"""Render the sidebar footer fade and verify alpha at the scroll boundary."""
import sys
from pathlib import Path
import time
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Graphene', '1.0')
from gi.repository import Adw, Gdk, Gio, GLib, Graphene, Gtk
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'appkit'))
from luma_appkit import NavigationSidebar, SidebarFoot, install_appkit, install_lumaui
from luma_appkit.lumaui_tokens import SCROLL

def settle():
    end = time.monotonic() + .4
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.005)

def alpha(window, widget, y):
    width, height = widget.get_width(), widget.get_height()
    snapshot = Gtk.Snapshot()
    Gtk.WidgetPaintable.new(widget).snapshot(snapshot, width, height)
    texture = window.get_renderer().render_texture(snapshot.to_node(), Graphene.Rect().init(0, 0, width, height))
    download = Gdk.TextureDownloader.new(texture)
    download.set_format(Gdk.MemoryFormat.R8G8B8A8)
    data, stride = download.download_bytes()
    return data.get_data()[y * stride + (width // 2) * 4 + 3]

app = Adw.Application(application_id='org.projectluma.SidebarFadeTest', flags=Gio.ApplicationFlags.NON_UNIQUE)
assert app.register(None)
install_appkit(); install_lumaui()
sidebar = NavigationSidebar()
sidebar.append_footer(SidebarFoot(search='Search messages'))
for index in range(40):
    drawing = Gtk.DrawingArea(height_request=40, hexpand=True)
    drawing.set_draw_func(lambda widget, cr, width, height: (cr.set_source_rgba(1, 0, 0, 1), cr.paint()))
    sidebar.list.append(Gtk.ListBoxRow(child=drawing))
window = Gtk.ApplicationWindow(application=app, child=sidebar, default_width=292, default_height=400)
window.present(); settle()
scroll = sidebar._scroll
adjustment = scroll.get_vadjustment()
assert adjustment.get_upper() > adjustment.get_page_size()
height = scroll.get_height()
assert alpha(window, scroll, height - 1) < 25, 'Footer boundary must fade to transparent'
assert alpha(window, scroll, height - SCROLL["fade_bottom"] - 2) > 230, 'Content above the fade must remain opaque'
sidebar.set_footer_fade(False); settle()
assert alpha(window, scroll, height - 1) > 230, 'Opt-out must remove the mask'
sidebar.set_footer_fade(True)
adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size()); settle()
final_alpha = [alpha(window, scroll, y) for y in range(height - SCROLL["fade_bottom"], height)]
assert max(final_alpha) > 230, 'The final row must remain readable at the end'
sidebar.set_footer_fade(False); settle()
assert final_alpha == [alpha(window, scroll, y) for y in range(height - SCROLL["fade_bottom"], height)], 'End-of-list content must match the unfaded rendering'
window.close()
print('Sidebar footer fade: transparent boundary, opaque content, opt-out and final-row visibility passed')
