// SPDX-License-Identifier: GPL-2.0-or-later
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';
import Meta from 'gi://Meta';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
const out = GLib.getenv('LUMA_SHELF_TEST_OUT');
const results = [];
const sleep = ms => new Promise(resolve => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {resolve(); return GLib.SOURCE_REMOVE;}));
const check = (name, ok, detail = '') => {results.push({name, ok: !!ok, detail}); console.log(`${ok ? 'PASS' : 'FAIL'} ${name} ${detail}`);};
const frame = window => {const r = window.get_frame_rect(); return {x: r.x, y: r.y, width: r.width, height: r.height};};
async function work() {
    const extension = Main.extensionManager.lookup('tilingshell@ferrarodomenico.com')?.stateObj;
    check('Tiling Shell enabled', extension?._tilingManagers?.length > 0);
    if (!extension?._tilingManagers?.length) return;
    const state = new Gio.Settings({schema_id: 'org.project_luma.shell-state'});
    const settings = extension.getSettings();
    check('coordinated resize off by default', !settings.get_boolean('resize-complementing-windows'));
    const children = ['One', 'Two'].map(name => Gio.Subprocess.new(['python3', '/source/tests/gnome-shell/shelf-presentation/app.py', `org.projectluma.Spacing${name}`], Gio.SubprocessFlags.NONE));
    try {
        let windows = [];
        for (let attempt = 0; attempt < 80; attempt++) {
            windows = global.get_window_actors().filter(actor => actor.mapped && actor.meta_window.get_title() === 'Shelf test').map(actor => actor.meta_window);
            if (windows.length === 2) break;
            await sleep(100);
        }
        check('two native windows opened', windows.length === 2);
        if (windows.length !== 2) return;
        const [left, right] = windows;
        left.maximize(); await sleep(700);
        for (const [enabled, size] of [[true, 14], [true, 32], [false, 0]]) {
            state.set_int('window-border-size', size || 14);
            state.set_boolean('window-border-enabled', enabled);
            await sleep(700);
            const r = frame(left), monitor = Main.layoutManager.primaryMonitor;
            check(`maximized border ${enabled ? size : 'off'} with tiler active`,
                r.x === monitor.x + size && r.y === monitor.y + size && monitor.x + monitor.width - r.x - r.width === size,
                JSON.stringify(r));
            const [, dockTop] = Main.shelf._dockIsland.get_transformed_position();
            check(`desktop and dash clearance match ${enabled ? size : 'off'}`,
                Math.abs(dockTop - r.y - r.height - size) <= 1, `${dockTop - r.y - r.height}`);
        }
        left.unmaximize(); await sleep(500);
        const manager = extension._tilingManagers[left.get_monitor()];
        manager.onTileFromWindowMenu({x: 0, y: 0, width: .5, height: 1, groups: []}, left);
        manager.onTileFromWindowMenu({x: .5, y: 0, width: .5, height: 1, groups: []}, right);
        await sleep(900);
        for (let gap = 0; gap <= 24; gap++) {
            settings.set_uint('inner-gaps', gap);
            await sleep(80);
            const a = frame(left), b = frame(right);
            check(`live gap ${gap}`, b.x - a.x - a.width === gap, `${b.x - a.x - a.width}`);
        }
        await sleep(700);
        const neighbor = frame(right), initial = frame(left);
        const bindings = new Gio.Settings({schema_id: "org.gnome.desktop.wm.keybindings"});
        bindings.set_strv("begin-resize", ["<Alt>F8"]);
        const grabs = [];
        const grabSignal = global.display.connect("grab-op-begin", (_display, window, op) => {grabs.push(op); console.log(`resize grab ${op} ${window.get_title()}`);});
        left.activate(global.get_current_time()); await sleep(500);
        check("target window focused and resizable", global.display.focus_window === left && left.allows_resize());
        const keyboard = Clutter.get_default_backend().get_default_seat().create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
        const key = symbol => {
            keyboard.notify_keyval(GLib.get_monotonic_time(), symbol, Clutter.KeyState.PRESSED);
            keyboard.notify_keyval(GLib.get_monotonic_time(), symbol, Clutter.KeyState.RELEASED);
        };
        const backend = global.stage.get_context().get_backend();
        left.begin_grab_op(Meta.GrabOp.KEYBOARD_RESIZING_UNKNOWN,
            backend.get_pointer_sprite(global.stage), global.get_current_time(), null);
        await sleep(200);
        for (let step = 0; step < 8; step++) {key(Clutter.KEY_Right); await sleep(60);}
        key(Clutter.KEY_Return); await sleep(700);
        global.display.disconnect(grabSignal);
        check('native resize grab started', grabs.length > 0, JSON.stringify(grabs));
        check('resizing releases the active tile', !left.assignedTile && frame(left).width > initial.width, JSON.stringify(frame(left)));
        check('resizing leaves its neighbor unchanged', JSON.stringify(frame(right)) === JSON.stringify(neighbor), JSON.stringify(frame(right)));
    } finally {children.forEach(child => child.force_exit());}
}
export function init() {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 5000, () => {
        work().catch(error => check('native spacing scenario completed', false, String(error.stack))).finally(() => {
            GLib.file_set_contents(`${out}/result.json`, JSON.stringify({pass: results.every(r => r.ok), results}, null, 2));
            global.context.terminate();
        }); return GLib.SOURCE_REMOVE;
    });
}
