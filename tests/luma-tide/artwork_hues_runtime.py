#!/usr/bin/python3
# SPDX-License-Identifier: Apache-2.0
"""Check saturated, neutral and transparent artwork background inputs."""
import gi
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib
from luma_tide.ui_parts import artwork_hues


def cover(pixel):
    return Gdk.MemoryTexture.new(24, 24, Gdk.MemoryFormat.R8G8B8A8,
                                 GLib.Bytes.new(bytes(pixel) * 24 * 24), 24 * 4)

red = artwork_hues(cover((255, 0, 0, 255)))
blue = artwork_hues(cover((0, 0, 255, 255)))
assert len(red) == len(blue) == 1
assert red[0] < 15 and 240 <= blue[0] < 255, (red, blue)
assert artwork_hues(cover((128, 128, 128, 255))) == ()
assert artwork_hues(cover((255, 0, 0, 0))) == ()
print('PASS artwork tint follows saturated covers and ignores neutral/transparent pixels')

from lumaui_runtime import settle, test_application
from luma_tide.model import MediaMetadata
from luma_tide.ui import TideWindow

for width in (1180, 390):
    with test_application(f'org.projectluma.TideArtwork{width}') as (app, root):
        source = app.store.add_source('Music', 'local-folder', root, local=True)
        for colour, pixels in [('Red', (255, 0, 0, 255)), ('Blue', (0, 0, 255, 255))]:
            picture = root / f'{colour}.png'
            assert cover(pixels).save_to_png(str(picture))
            app.store.upsert_copy(source.id, MediaMetadata(
                uri=(root / f'{colour}.flac').as_uri(), content_digest=colour.lower() * 16,
                title=colour, artist='Artwork', album=colour, artwork_uri=picture.as_uri()))
        window = TideWindow(app)
        window.set_default_size(width, 874)
        window.present()
        settle(lambda: len(window.library.albums) == 2)
        albums = {album.title: album for album in window.library.albums}
        for title, expected in [('Red', red), ('Blue', blue), ('Red', red)]:
            window.open_album(albums[title].id)
            settle(lambda: window.light.glow.hues == expected and
                   window.light.picture.paintable is not None, what=f'{width}px {title} artwork light')
        window.destroy()
print('PASS desktop and phone album backgrounds follow loaded and cached artwork')
