# Tiling picker and zone editor regression

`state.mjs PATCHED_PAYLOAD` runs the shipped editor/state implementations with
small Shell actor/service adapters. It checks new and existing layout Save and
discard, Escape and Ctrl+S, toolbar geometry/appearance, monitor-change handling,
and teardown signal cleanup. It also instantiates the editor constructor and
rejects any use of window-gap settings for its canvas. This check runs in the
Tiling Shell RPM's `%check`; it does not qualify native actor allocation or paint.

`run-native.sh` requires root **inside a disposable fixture** with the candidate
Tiling Shell 25 and Luma toggle 14 packages, matching Luma Shell/Mutter, and the
`luma-media-test` fixture user. Set `LUMA_NATIVE_SHELL_DISPOSABLE=1` and
`DEV_ARTIFACT_DIR` to an owned output directory. It runs production packages
without source overlays, using an isolated settings profile and three virtual
monitors. It exercises pointer picking and input, picker row allocation, New
and Edit, zone splitting, persistence, discard and extension recreation. Screenshots
and a result JSON cover Light, Dark, Frost and Glass. A failed assertion fails
the command. This is software UI evidence; physical device acceptance is separate.

The existing `tests/gnome-shell/tiling-picker/tiling-picker.js` also checks that
the grid reserves its full height and Edit/New action rows clear the last monitor.
Keep screenshot and long log outputs outside Git. No test builds installation
media or publishes updates.

The picker scenario covers 30 and 100 saved layouts, current-layout paging,
keyboard search and pointer clear, display navigation and selection isolation,
long names, empty/invalid collections with the tiler disabled (the enabled tiler
restores its defaults), visible disabled arrows, transparent gallery geometry,
Figtree heading type and native thumbnail stroke contrast. Native screenshots
include cropped detail surfaces in all four modes. Set
`LUMA_TILING_TEST_PRIMARY=1280x720` inside the disposable runner and make
secondary monitors smaller (1024x600 and 800x600) to repeat on a short primary.
Mutter may otherwise choose a larger secondary as primary. The default primary
is 1920x1080. Check captured PNG dimensions rather than assuming the first
virtual monitor is primary. Native action text/glyph contrast is measured too.
