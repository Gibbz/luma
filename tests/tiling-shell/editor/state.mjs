// SPDX-License-Identifier: Apache-2.0
// Run against the fully patched reviewed extension payload, not a copied model.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
const payload = process.argv[2];
assert(payload, 'pass the patched Tiling Shell payload directory');
let id = 0;
class Actor {
    constructor(params = {}) {
        Object.assign(this, params);
        this.children = []; this.signals = new Map(); this.classes = new Set();
        this.width = 216; this.visible = false; this.destroyed = false;
    }
    connect(name, fn) { const n = ++id; this.signals.set(n, {name, fn}); return n; }
    connect_after(name, fn) { return this.connect(name, fn); }
    disconnect(n) { assert(this.signals.delete(n), `signal ${n} was already disconnected`); }
    connectObject(name, fn, owner) { this.signals.set(++id, {name, fn, owner}); }
    disconnectObject(owner) { for (const [n, s] of this.signals) if (s.owner === owner) this.signals.delete(n); }
    emit(name, ...args) { for (const s of [...this.signals.values()]) if (s.name === name) s.fn(this, ...args); }
    add_child(child) { this.children.push(child); }
    add_style_class_name(name) { this.classes.add(name); }
    remove_style_class_name(name) { this.classes.delete(name); }
    set_position(x, y) { this.x = x; this.y = y; }
    set_size(w, h) { this.width = w; this.height = h; }
    show() { this.visible = true; }
    hide() { this.visible = false; }
    grab_key_focus() {}
    destroy_all_children() { for (const c of this.children) c.destroy(); this.children = []; }
    destroy() { assert(!this.destroyed, 'actor destroyed twice'); this.destroyed = true; this.emit('destroy'); }
}
class Panel extends Actor {
    constructor() { super(); this.menu = {removeAll() {}, close() {}, toggle() { throw Error('editor must not toggle the hidden panel menu'); }}; }
}
const stage = new Actor(), display = new Actor(), manager = new Actor();
manager.primaryIndex = 0; manager.monitors = [{index: 0}];
let area = {x: 1000, y: 32, width: 1200, height: 800};
manager.getWorkAreaForMonitor = () => area;
manager.addTopChrome = actor => actor.show();
manager.addChrome = actor => actor.show();
const appearance = new Actor(); appearance.mode = 'dark'; appearance.get_string = () => appearance.mode;
const state = {layouts: [], adds: 0, edits: 0,
    addLayout(layout) { this.adds++; this.layouts.push(layout); },
    editLayout(layout) { this.edits++; this.layouts = this.layouts.map(l => l.id === layout.id ? layout : l); },
    deleteLayout() {}, swapLayouts() {}};
class Layout { constructor(tiles, id) { this.tiles = tiles; this.id = id; } }
class Tile { constructor(params) { Object.assign(this, params); } }
class Canvas extends Actor { constructor(layout) { super(); this.layout = layout; } }
class Menu { destroy() {} }
const context = vm.createContext({console,
    St: {BoxLayout: Actor, Button: Actor, Icon: Actor, Widget: Actor,
        ThemeContext: {get_for_stage: () => ({scale_factor: 1})}},
    Clutter: {KEY_Escape: 27, KEY_s: 115, KEY_S: 83,
        ModifierType: {CONTROL_MASK: 4}, EVENT_STOP: 1, EVENT_PROPAGATE: 0},
    Gio: {SettingsSchemaSource: {get_default: () => ({lookup: () => ({})})},
        Settings: function() { return appearance; }, SettingsBindFlags: {GET: 1}, icon_new_for_string: s => s},
    Main: {layoutManager: manager, panel: {addToStatusArea() {}}},
    global: {stage, display, windowGroup: {bind_property() {}}},
    registerGObjectClass() {}, _: s => s,
    PanelMenu: {Button: Panel}, Settings: {bind() {}, SHOW_INDICATOR: false},
    GlobalState: {get: () => state}, lumaNewLayoutId: () => `new-${state.adds}`,
    Layout, Tile, LayoutEditor: Canvas, DefaultMenu: Menu, EditingMenu: Menu,
    EditorDialog: class { constructor(params) { this.params = params; context.lastDialog = this; } open() {} destroy() {} },
});
function load(file, name, expression) {
    const source = fs.readFileSync(path.join(payload, file), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace(/export\s*\{[^}]+\};/g, '')
        .replace(/^export default .*;$/gm, '');
    vm.runInContext(`${source}\nglobalThis.${name} = ${expression};`, context, {filename: file});
}
load('indicator/editorActions.js', 'EditorActions', '_EditorActions');
load('indicator/indicator.js', 'TestIndicator', '_Indicator');
const indicator = new context.TestIndicator('/extension', 'tiler'); indicator.enable();
const snapshot = () => JSON.stringify(state.layouts);
const savedBefore = snapshot();
indicator.newLayoutOnClick(false);
let bar = indicator._editorActions;
assert(bar?.visible, 'actions visible even with the panel indicator disabled');
assert.equal(indicator.visible, false, 'panel preference retained');
assert.deepEqual(bar.children.map(c => c.label), ['Close', 'Save']);
assert.equal(bar.x, 1968); assert.equal(bar.y, 48);
assert(bar.classes.has('luma-surface-dark'));
appearance.mode = 'light'; appearance.emit('changed::surface-treatment');
assert(bar.classes.has('luma-surface-light') && !bar.classes.has('luma-surface-dark'));
area = {...area, width: 900}; display.emit('workareas-changed'); assert.equal(bar.x, 1668);
bar.children[0].emit('clicked');
assert.equal(snapshot(), savedBefore, 'Close must not persist a new draft');
assert(bar.destroyed && indicator._editorActions === null);
assert.equal(stage.signals.size, 0, 'keyboard handler removed after Close');
assert.equal(display.signals.size, 0, 'work-area handler removed after Close');
assert.equal(manager.signals.size, 0, 'monitor handler removed after Close');
assert.equal(appearance.signals.size, 0, 'appearance handler removed after Close');
indicator.newLayoutOnClick(false); bar = indicator._editorActions;
indicator._layoutEditor.layout.tiles[0].width = 0.4;
bar.children[1].emit('clicked');
assert.equal(state.adds, 1); assert.equal(state.layouts[0].tiles[0].width, 0.4);
assert(bar.destroyed && indicator._layoutEditor === null);
const persisted = snapshot();
indicator.openLayoutEditor();
context.lastDialog.params.onSelectLayout(0, state.layouts[0]);
indicator._layoutEditor.layout.tiles[0].width = 0.55;
indicator.cancelLayoutOnClick();
assert.equal(snapshot(), persisted, 'editing uses a copy; Close preserves the saved layout');
indicator.openLayoutEditor(); context.lastDialog.params.onSelectLayout(0, state.layouts[0]);
indicator._layoutEditor.layout.tiles[0].width = 0.6;
stage.emit('key-press-event', {get_key_symbol: () => 115, get_state: () => 4});
assert.equal(state.edits, 1); assert.equal(state.layouts[0].tiles[0].width, 0.6);
indicator.newLayoutOnClick(false); bar = indicator._editorActions;
stage.emit('key-press-event', {get_key_symbol: () => 27, get_state: () => 0});
assert(bar.destroyed); assert.equal(state.adds, 1, 'Escape discards');
indicator.newLayoutOnClick(false); bar = indicator._editorActions;
manager.emit('monitors-changed'); assert(bar.destroyed); assert.equal(state.adds, 1, 'hotplug discards');
indicator.newLayoutOnClick(false); bar = indicator._editorActions;
indicator.destroy(); assert(bar.destroyed);
assert.equal(stage.signals.size + display.signals.size + manager.signals.size + appearance.signals.size, 0,
    'extension teardown leaves no toolbar signals');
// Use the actual editor constructor to prove window-gap settings cannot inset
// editing geometry. Tiling/rendering outside the editor is deliberately untouched.
context.Settings.get_inner_gaps = () => { throw Error('window gaps used by editor'); };
context.Settings.get_outer_gaps = context.Settings.get_inner_gaps;
context.buildMargin = value => ({top: value, right: value, bottom: value, left: value});
context.buildRectangle = params => params; context.getWindowsOfMonitor = () => [];
context.GObject = {BindingFlags: {DEFAULT: 0}};
context.HoverLine = class {};
load('components/editor/layoutEditor.js', 'TestCanvas', '_LayoutEditor');
context.TestCanvas.prototype._drawEditor = function() {};
const monitor = {index: 0, x: 1000, y: 0, width: 1280, height: 960};
const canvas = new context.TestCanvas(new Layout([], 'test'), monitor, false);
assert.equal(canvas.x, monitor.x); assert.equal(canvas.y, monitor.y);
assert.equal(canvas.width, monitor.width); assert.equal(canvas.height, monitor.height);
for (const g of [canvas._innerGaps, canvas._outerGaps]) assert.deepEqual(Object.values(g), [0, 0, 0, 0]);
console.log('PASS: create/edit Save and discard, shortcuts, toolbar placement/appearance, hotplug/teardown cleanup, edge-to-edge geometry');
