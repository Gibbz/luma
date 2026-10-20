# Luma Tiling Quick Toggle

This Luma-owned GNOME Shell extension provides one narrow integration point: a
standard Quick Settings menu named **Tiling**. Its primary tile calls GNOME
Shell's live extension service to enable or disable
`tilingshell@ferrarodomenico.com` and its automatic window placement immediately.
The switch follows both the enabled and disabled extension lists, and returns
to its actual state when the Shell refuses a change. The submenu reads Tiling Shell's
compiled extension-local schema, renders its saved tile geometry, and uses the
tiler's Shell D-Bus object to select a layout or open its existing edit/new
layout interfaces. A direct **Tiling settings** action remains available.
GNOME Shell owns the persisted enabled-extension list, preserving every
unrelated extension.

Tiling Shell remains a separate and explicitly credited upstream package with
its narrow downstream deltas recorded in Luma's component ledger. This bridge
does not copy, rename, or replace its implementation. Tiling Shell's separate
top-panel indicator is off by default because the same controls are available
in Quick Settings.

The layout picker is drawn by `stylesheet.css` in the appearance mode Quick
Options is showing (its `luma-surface-*` class), from the Shell's ink ledger:
neutral outlines for every layout and the shared state slate for the chosen
one (ADR-043). `verify-ink.py` measures each pair in all four modes from the
package's `%check`.

The chooser remains inside Quick Options. It shows one display at a time and
at most six named layout previews, with balanced rows, previous/next pages and
a range count. Opening it reveals the current layout; the Current link returns
to that layout after browsing or searching. Collections of twelve or more show
Find a layout, matching names, layout numbers and zone counts. Display navigation
preserves a search, and choosing a layout affects only that display on the current
workspace. Long names are ellipsized visually and remain available to assistive
technology. Invalid entries are skipped, and an empty collection keeps New layout
available. Disabled arrows are dimmed and skipped by keyboard focus.

There is one Shell-owned sheet surface, a transparent gallery, and one recessed
search field. Type and field geometry follow config/shared/design-tokens.json;
menu controls follow the Quick Options sheet and context-menu contracts. Hover
and keyboard focus share the same wash. Only the selected layout gets the slate
state and ring. Runtime material classes follow the actual Shell foreground so
older frost/glass palettes retain readable controls. Package contrast checks and
native measurements cover all four appearance modes.

Entering the editor closes Quick Options. The tiler supplies floating Save and
Close buttons throughout zone editing. No separate layout-manager window is added.
