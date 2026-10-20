// SPDX-License-Identifier: Apache-2.0
// Packaged Shell test. All settings and layouts belong to a disposable profile.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
const OUT = GLib.getenv('LUMA_TILING_EDITOR_OUT');
const results = [];
const sleep = ms => new Promise(r => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {r(); return GLib.SOURCE_REMOVE;}));
const check = (name, ok, detail = '') => { results.push({name, ok: !!ok, detail}); console.log(`[tiling-editor] ${ok ? 'PASS' : 'FAIL'} ${name} ${detail}`); };
const descend = (a, out = []) => { out.push(a); a.get_children?.().forEach(c => descend(c, out)); return out; };
const over = (fg, bg) => ({red: fg.red * fg.alpha / 255 + bg.red * (1 - fg.alpha / 255),
    green: fg.green * fg.alpha / 255 + bg.green * (1 - fg.alpha / 255),
    blue: fg.blue * fg.alpha / 255 + bg.blue * (1 - fg.alpha / 255), alpha: 255});
const lum = c => [c.red, c.green, c.blue].map(v => v / 255).map(v =>
    v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
    .reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
const contrast = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);
function ground(actor) {
    const chain = [];
    for (let a = actor; a; a = a.get_parent()) if (a.get_theme_node && a.get_stage()) chain.unshift(a);
    return chain.reduce((bg, a) => over(a.get_theme_node().get_background_color(), bg),
        {red: 0, green: 60, blue: 140, alpha: 255});
}
Gio._promisify(Shell.Screenshot.prototype, 'screenshot_stage_to_content');
Gio._promisify(Shell.Screenshot, 'composite_to_stream');
async function shot(name, actor = null) {
    const [content, scale] = await new Shell.Screenshot().screenshot_stage_to_content();
    const stream = Gio.File.new_for_path(`${OUT}/${name}.png`).replace(null, false, Gio.FileCreateFlags.NONE, null);
    const monitor = Main.layoutManager.primaryMonitor;
    const e = actor?.get_transformed_extents();
    const x = e ? Math.max(monitor.x, Math.floor(e.get_x()) - 12) : monitor.x;
    const y = e ? Math.max(monitor.y, Math.floor(e.get_y()) - 12) : monitor.y;
    const width = e ? Math.min(monitor.x + monitor.width - x, Math.ceil(e.get_width()) + 24) : monitor.width;
    const height = e ? Math.min(monitor.y + monitor.height - y, Math.ceil(e.get_height()) + 24) : monitor.height;
    await Shell.Screenshot.composite_to_stream(content.get_texture(), x, y, width,
        height, scale, null, 0, 0, 1, stream);
    stream.close(null);
}
const seat = Clutter.get_default_backend().get_default_seat();
const pointer = seat.create_virtual_device(Clutter.InputDeviceType.POINTER_DEVICE);
const touch = seat.create_virtual_device(Clutter.InputDeviceType.TOUCHSCREEN_DEVICE);
const keyboard = seat.create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
async function clickAt(x, y) {
    pointer.notify_absolute_motion(GLib.get_monotonic_time(), x, y); await sleep(100);
    pointer.notify_button(GLib.get_monotonic_time(), Clutter.BUTTON_PRIMARY, Clutter.ButtonState.PRESSED);
    await sleep(50);
    pointer.notify_button(GLib.get_monotonic_time(), Clutter.BUTTON_PRIMARY, Clutter.ButtonState.RELEASED);
    await sleep(600);
}
async function click(actor) {
    const e = actor.get_transformed_extents();
    const x = e.get_x() + e.get_width() / 2, y = e.get_y() + e.get_height() / 2;
    const picked = global.stage.get_actor_at_pos(Clutter.PickMode.REACTIVE, x, y);
    let hits = false;
    for (let a = picked; a; a = a.get_parent()) if (a === actor) hits = true;
    check(`pointer reaches ${actor.label?.text ?? actor.label ?? actor.style_class}`, hits);
    await clickAt(x, y);
}
async function tap(actor) {
    const e = actor.get_transformed_extents();
    touch.notify_touch_down(GLib.get_monotonic_time(), 0,
        e.get_x() + e.get_width() / 2, e.get_y() + e.get_height() / 2);
    await sleep(70);
    touch.notify_touch_up(GLib.get_monotonic_time(), 0);
    await sleep(600);
}
async function key(symbol, control = false) {
    if (control) keyboard.notify_keyval(GLib.get_monotonic_time(), Clutter.KEY_Control_L, Clutter.KeyState.PRESSED);
    keyboard.notify_keyval(GLib.get_monotonic_time(), symbol, Clutter.KeyState.PRESSED);
    keyboard.notify_keyval(GLib.get_monotonic_time(), symbol, Clutter.KeyState.RELEASED);
    if (control) keyboard.notify_keyval(GLib.get_monotonic_time(), Clutter.KEY_Control_L, Clutter.KeyState.RELEASED);
    await sleep(600);
}
async function closeLegend(indicator) {
    const dialog = indicator._editorDialog;
    if (!dialog) return;
    const root = dialog.dialogLayout ?? dialog._dialog?.dialogLayout ?? dialog;
    const start = descend(root).find(a => a.label === 'Start editing');
    if (!start) throw Error('legend Start editing button unavailable');
    await click(start);
    await sleep(300);
}
async function work() {
    let toggle, indicator;
    for (let n = 0; n < 50; n++) {
        toggle = Main.extensionManager.lookup('tiling-toggle@project-luma.local')?.stateObj?._indicator?.quickSettingsItems[0];
        indicator = Main.extensionManager.lookup('tilingshell@ferrarodomenico.com')?.stateObj?._indicator;
        if (toggle && indicator) break;
        await sleep(300);
    }
    if (!toggle || !indicator) throw Error('packaged extensions unavailable');
    console.log(`[tiling-editor] session=${Main.sessionMode.currentMode} allowSettings=${Main.sessionMode.allowSettings} mode=${JSON.stringify(Main.sessionMode.isLocked)}`);
    for (const module of ['quickSettings', 'popupMenu'])
        GLib.file_set_contents(`${OUT}/${module}-installed.js`, Gio.resources_lookup_data(
            `/org/gnome/shell/ui/${module}.js`, Gio.ResourceLookupFlags.NONE).get_data());
    const settings = toggle._tilingSettings;
    settings.set_boolean('show-indicator', false);
    const initial = settings.get_string('layouts-json');
    const initialLayouts = JSON.parse(initial);
    const quick = Main.panel.statusArea.quickSettings;
    // A large collection stays bounded, and the current layout is visible on open.
    const originalSelection = settings.get_value('selected-layouts');
    const many = Array.from({length: 30}, (_, i) => ({...initialLayouts[i % initialLayouts.length], id: `fixture-${i + 1}`}));
    settings.set_string('layouts-json', JSON.stringify(many));
    const selection = originalSelection.deepUnpack();
    const workspace = global.workspace_manager.get_active_workspace_index();
    while (selection.length <= workspace) selection.push([]);
    selection[workspace] = Main.layoutManager.monitors.map(() => many[29].id);
    settings.set_value('selected-layouts', new GLib.Variant('aas', selection));
    await sleep(700);
    for (const mode of ['light', 'dark', 'frost', 'glass']) {
        new Gio.Settings({schema_id: 'org.project_luma.shell-state'}).set_string('surface-treatment', mode);
        new Gio.Settings({schema_id: 'org.gnome.desktop.interface'}).set_string('color-scheme', mode === 'dark' ? 'prefer-dark' : 'default');
        await sleep(700);
        quick.menu.open(); await sleep(300); toggle.menu.open(); await sleep(500);
        toggle._syncSurface(); await sleep(300);
        check(`${mode}: 30 layouts use a six-card gallery`, toggle._previewButtons.length === 6 && toggle._page === 4);
        check(`${mode}: current layout is visible on opening`, toggle._previewButtons.some(b => b.checked && b._layoutId === many[29].id));
        const bounds = toggle._newLayoutItem.get_transformed_extents();
        check(`${mode}: New action fits on screen with 30 layouts`, bounds.get_y() >= 0 && bounds.get_y() + bounds.get_height() < Main.layoutManager.primaryMonitor.height);
        let worst = Infinity;
        for (const card of toggle._previewButtons) {
            const tile = descend(card).find(a => a.has_style_class_name?.('luma-tiling-preview-tile'));
            const bg = ground(tile.get_parent());
            worst = Math.min(worst, contrast(over(tile.get_theme_node().get_border_color(0), bg), bg));
        }
        check(`${mode}: native thumbnail strokes hold 3:1 contrast`, worst >= 3, worst.toFixed(2));
        const actionContrast = Math.min(...[toggle._editLayoutsItem, toggle._newLayoutItem, toggle._settingsItem].map(item =>
            contrast(over(item.label.get_theme_node().get_foreground_color(), ground(item.label)), ground(item.label))));
        check(`${mode}: action text holds 4.5:1 native contrast`, actionContrast >= 4.5, actionContrast.toFixed(2));
        const iconContrast = Math.min(...[toggle._editLayoutsItem, toggle._newLayoutItem, toggle._settingsItem].flatMap(item =>
            item.get_children().filter(a => a instanceof St.Icon).map(a => contrast(over(a.get_theme_node().get_foreground_color(), ground(a)), ground(a)))));
        check(`${mode}: action glyphs hold 3:1 native contrast`, iconContrast >= 3, iconContrast.toFixed(2));
        check(`${mode}: gallery adds no nested background`, toggle._layoutsBox.get_theme_node().get_background_color().alpha === 0);
        const title = descend(toggle._layoutsBox).find(a => a.has_style_class_name?.('luma-tiling-display-name'));
        check(`${mode}: display heading uses Luma typography`, title.get_theme_node().get_font().get_family() === 'Figtree');
        check(`${mode}: disabled page arrow is visibly muted`, !toggle._pageNext.reactive && toggle._pageNext.opacity < 100);
        await shot(`picker-many-${mode}`);
        await shot(`detail-many-${mode}`, toggle.menu.box);
        toggle.menu.close(); quick.menu.close();
    }
    quick.menu.open(); await sleep(200); toggle.menu.open(); await sleep(400);
    await click(toggle._pagePrevious);
    check('Previous layouts preserves usable keyboard focus', toggle._page === 3 && global.stage.key_focus === toggle._pagePrevious);
    await click(toggle._pageNext);
    check('Last gallery page keeps focus on enabled navigation', toggle._page === 4 && global.stage.key_focus === toggle._pagePrevious);
    toggle._search.grab_key_focus();
    await key(Clutter.KEY_3); await key(Clutter.KEY_0);
    check('Typing finds layout 30 without leaving Quick Options', toggle._previewButtons.length === 1 && toggle._previewButtons[0]._layoutId === many[29].id && quick.menu.isOpen);
    await shot('picker-search');
    const clear = toggle._clearSearch.get_transformed_extents();
    await clickAt(clear.get_x() + clear.get_width() / 2, clear.get_y() + clear.get_height() / 2);
    check('Clear search restores the gallery and retains entry focus', !toggle._query && toggle._previewButtons.length === 6 && toggle._search.clutter_text.has_key_focus());
    toggle._search.set_text('nothing matches this'); await sleep(300);
    check('No search results keeps New available', toggle._previewButtons.length === 0 && toggle._newLayoutItem.reactive);
    toggle._search.set_text(''); await sleep(300);
    const oldMonitor = toggle._monitorIndex;
    await click(toggle._displayNext);
    check('Display navigation preserves each display selection', toggle._monitorIndex === (oldMonitor + 1) % Main.layoutManager.monitors.length && toggle._previewButtons.some(b => b.checked));
    // Select via real pointer input and check the supported native D-Bus route.
    toggle._page = 0; toggle._renderLayouts(); await sleep(400);
    const targetMonitor = toggle._monitorIndex;
    await click(toggle._previewButtons[0]); await sleep(600);
    check('Layout choice applies only to the chosen display', settings.get_value('selected-layouts').deepUnpack()[workspace][targetMonitor] === many[0].id &&
        settings.get_value('selected-layouts').deepUnpack()[workspace][oldMonitor] === many[29].id);
    // Tiler normalizes malformed/empty collections back to defaults when
    // enabled. Exercise the chooser's defensive/empty states with it disabled.
    await Main.extensionManager.disableExtension('tilingshell@ferrarodomenico.com'); await sleep(500);
    toggle = Main.extensionManager.lookup('tiling-toggle@project-luma.local').stateObj._indicator.quickSettingsItems[0];
    const hundred = Array.from({length: 100}, (_, i) => ({...many[i % many.length], id: `hundred-${i}`}));
    hundred[0].name = 'A deliberately long saved layout name that must not widen the Quick Options menu';
    settings.set_string('layouts-json', JSON.stringify(hundred)); await sleep(300);
    toggle._page = 99; toggle._renderLayouts();
    check('100 layouts clamp to a bounded last page', toggle._page === 16 && toggle._previewButtons.length === 4);
    toggle._page = 0; toggle._renderLayouts();
    quick.menu.open(); await sleep(200); toggle.menu.open(); await sleep(500);
    check('Long layout names do not widen Quick Options', toggle.menu.box.width <= 400);
    settings.set_string('layouts-json', JSON.stringify([null, {id: 'broken', tiles: [null]}, many[0]])); await sleep(300);
    check('A malformed saved layout does not hide valid layouts', toggle._getLayouts().length === 1 && toggle._previewButtons.length === 1);
    settings.set_string('layouts-json', '[]'); await sleep(300);
    check('Empty collection leaves creation available', toggle._previewButtons.length === 0 && toggle._newLayoutItem.reactive && !toggle._editLayoutsItem.reactive);
    settings.set_string('layouts-json', initial);
    settings.set_value('selected-layouts', originalSelection);
    toggle.menu.close(); quick.menu.close(); await sleep(500);
    await Main.extensionManager.enableExtension('tilingshell@ferrarodomenico.com'); await sleep(700);
    indicator = Main.extensionManager.lookup('tilingshell@ferrarodomenico.com').stateObj._indicator;
    toggle = Main.extensionManager.lookup('tiling-toggle@project-luma.local').stateObj._indicator.quickSettingsItems[0];
    for (const mode of ['light', 'dark', 'frost', 'glass']) {
        new Gio.Settings({schema_id: 'org.project_luma.shell-state'}).set_string('surface-treatment', mode);
        new Gio.Settings({schema_id: 'org.gnome.desktop.interface'}).set_string('color-scheme', mode === 'dark' ? 'prefer-dark' : 'default');
        await sleep(800);
        quick.menu.open(); await sleep(350); toggle.menu.open(); await sleep(800);
        const previews = descend(toggle._layoutsBox).filter(a => a.has_style_class_name?.('luma-tiling-preview'));
        const bottom = Math.max(...previews.map(a => {const e = a.get_transformed_extents(); return e.get_y() + e.get_height();}));
        for (const a of [toggle._editLayoutsItem, toggle._newLayoutItem]) {
            const e = a.get_transformed_extents();
            check(`${mode}: ${a.label.text} clears the monitor grid`, e.get_y() >= bottom && e.get_height() >= 24,
                `class=${a.style_class} preferred=${a.get_preferred_height(-1)} visible=${a.visible} mapped=${a.mapped} action y=${e.get_y()} height=${e.get_height()} thumbnails bottom=${bottom}`);
        }
        // On a short display the full three-monitor grid scrolls. Keyboard
        // focus uses the page's production ensure-visible handler before the
        // native pointer click, exercising the reachable target after scroll.
        toggle._newLayoutItem.grab_key_focus(); await sleep(500);
        await shot(`picker-${mode}`);
        await click(toggle._newLayoutItem); await sleep(700);
        check(`${mode}: Quick Options closes for editing`, !quick.menu.isOpen);
        // New layout initially shows upstream guidance; close that modal to edit.
        await closeLegend(indicator);
        await sleep(700);
        const editor = indicator._layoutEditor, bar = indicator._editorActions;
        if (!editor || !bar) throw Error('New layout did not open the editor with actions');
        check(`${mode}: toolbar mapped with the panel indicator hidden`, bar.mapped && !indicator.visible);
        const area = Main.layoutManager.getWorkAreaForMonitor(Main.layoutManager.primaryIndex);
        const e = bar.get_transformed_extents();
        check(`${mode}: actions fit at the upper right of the work area`,
            e.get_x() > area.x + area.width / 2 && e.get_x() + e.get_width() <= area.x + area.width &&
            e.get_y() >= area.y && e.get_y() + e.get_height() < area.y + area.height / 2);
        check(`${mode}: edit geometry has no window-gap insets`,
            [editor._innerGaps, editor._outerGaps].every(g => g.top === 0 && g.left === 0 && g.right === 0 && g.bottom === 0));
        const monitor = Main.layoutManager.primaryMonitor;
        check(`${mode}: canvas covers the entire monitor`, editor.x === monitor.x && editor.y === monitor.y &&
            editor.width === monitor.width && editor.height === monitor.height);
        const tiles = descend(editor).filter(a => a.has_style_class_name?.('editable-tile-preview'));
        check(`${mode}: no second blue fill on edit zones`, tiles.length > 0 && tiles.every(a =>
            a.get_theme_node().get_background_color().alpha === 0));
        // Leave the zones idle so the screenshot shows the canvas, rather than
        // the transient hover highlight and split guide beneath the pointer.
        pointer.notify_absolute_motion(GLib.get_monotonic_time(), e.get_x() + 4, e.get_y() + 4);
        await sleep(300);
        await shot(`editor-${mode}`);
        if (mode === 'glass') await tap(bar.get_children()[0]);
        else await click(bar.get_children()[0]);
        check(`${mode}: Close removes the toolbar and preserves saved layouts`,
            indicator._editorActions === null && indicator._layoutEditor === null && settings.get_string('layouts-json') === initial);
    }
    // Native zone split and Save, then discard a modification of that saved zone.
    indicator.newLayoutOnClick(false); await sleep(500);
    let editor = indicator._layoutEditor;
    await clickAt(editor.x + editor.width * 0.15, editor.y + editor.height * 0.6);
    check('native click splits a zone', editor.layout.tiles.length === 3);
    const bar = indicator._editorActions;
    await click(bar.get_children()[1]);
    const saved = JSON.parse(settings.get_string('layouts-json'));
    const added = saved.find(l => !initialLayouts.some(old => old.id === l.id));
    check('Save persists exactly one new three-zone layout', saved.length === initialLayouts.length + 1 && added?.tiles.length === 3);
    // Open the real picker and select the newly saved layout for editing.
    quick.menu.open(); await sleep(300); toggle.menu.open(); await sleep(500);
    toggle._editLayoutsItem.grab_key_focus(); await sleep(500);
    await click(toggle._editLayoutsItem); await sleep(600);
    const dialog = indicator._editorDialog;
    if (!dialog) throw Error('Edit layouts action did not open the selection dialog');
    const layouts = dialog._layoutsBoxLayout.get_children();
    await click(layouts[saved.findIndex(l => l.id === added.id)].get_children()[0]);
    await closeLegend(indicator); await sleep(600);
    editor = indicator._layoutEditor;
    if (!editor) throw Error('Selecting a saved layout did not start editing');
    const beforeClose = settings.get_string('layouts-json');
    await clickAt(editor.x + editor.width * 0.5, editor.y + editor.height * 0.6);
    check('saved layout draft can be split', editor.layout.tiles.length > 3);
    await click(indicator._editorActions.get_children()[0]);
    check('Close discards a saved-layout edit', settings.get_string('layouts-json') === beforeClose);
    indicator.newLayoutOnClick(false); await sleep(400);
    indicator._editorActions.get_children()[1].grab_key_focus();
    await key(Clutter.KEY_Escape);
    check('keyboard Escape closes without saving', indicator._layoutEditor === null && settings.get_string('layouts-json') === beforeClose);
    indicator.newLayoutOnClick(false); await sleep(400);
    indicator._editorActions.get_children()[1].grab_key_focus();
    await key(Clutter.KEY_s, true);
    const afterShortcut = settings.get_string('layouts-json');
    check('keyboard Ctrl+S saves the draft', indicator._layoutEditor === null && JSON.parse(afterShortcut).length === saved.length + 1);
    // Teardown while editing exercises the actual chrome/signal lifetime.
    indicator.newLayoutOnClick(false); await sleep(400);
    // Recreate the extension to check actual persisted settings and owned chrome.
    await Main.extensionManager.disableExtension('tilingshell@ferrarodomenico.com'); await sleep(500);
    check('extension teardown removes all editing actions', !descend(Main.layoutManager.uiGroup).some(a =>
        a.has_style_class_name?.('luma-tiling-editor-actions')));
    await Main.extensionManager.enableExtension('tilingshell@ferrarodomenico.com'); await sleep(900);
    check('new layout survives extension recreation', JSON.parse(settings.get_string('layouts-json')).some(l => l.id === added?.id && l.tiles.length === 3));
}
export function init() {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 6000, () => {
        work().catch(e => check('native scenario completes', false, `${e}\n${e.stack}`)).finally(() => {
            GLib.file_set_contents(`${OUT}/result.json`, JSON.stringify({results, pass: results.length > 0 && results.every(r => r.ok)}, null, 2));
            global.context.terminate();
        });
        return GLib.SOURCE_REMOVE;
    });
}
// Shell's automation runner owns the main loop while init schedules the probe.
export async function run() { await new Promise(() => {}); }
