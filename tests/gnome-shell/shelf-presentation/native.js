// SPDX-License-Identifier: GPL-2.0-or-later
// Actual Shell actors and virtual seat input in an isolated profile.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';
import St from 'gi://St';
import Meta from 'gi://Meta';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
const out = GLib.getenv('LUMA_SHELF_TEST_OUT');
const results = [];
const frames = [];
const sleep = ms => new Promise(resolve => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
    resolve(); return GLib.SOURCE_REMOVE;
}));
const check = (name, ok, detail = '') => {
    results.push({name, ok: !!ok, detail});
    console.log(`[shelf-presentation] ${ok ? 'PASS' : 'FAIL'} ${name} ${detail}`);
};
const descendants = (actor, all = []) => {
    all.push(actor);
    actor.get_children?.().forEach(child => descendants(child, all));
    return all;
};
const rect = actor => {
    const r = actor.get_transformed_extents();
    return [r.get_x(), r.get_y(), r.get_width(), r.get_height()];
};
function sample() {
    const shelf = Main.shelf;
    if (!shelf) return;
    const dock = shelf.islandActorFor('dock');
    const clock = shelf.partActorFor('clock');
    const painted = actor => actor?.mapped && actor.get_paint_opacity() > 0;
    frames.push({dock: painted(dock) ? rect(dock) : null,
        clock: painted(clock) ? rect(clock) : null,
        children: shelf._dash._box.get_children().length});
}
Gio._promisify(Shell.Screenshot.prototype, 'screenshot_stage_to_content');
Gio._promisify(Shell.Screenshot, 'composite_to_stream');
async function shot(name) {
    const [content, scale] = await new Shell.Screenshot().screenshot_stage_to_content();
    const m = Main.layoutManager.primaryMonitor;
    const stream = Gio.File.new_for_path(`${out}/${name}.png`).replace(null, false, Gio.FileCreateFlags.NONE, null);
    await Shell.Screenshot.composite_to_stream(content.get_texture(), m.x, m.y, m.width, m.height,
        scale, null, 0, 0, 1, stream);
    stream.close(null);
}
async function work() {
    const shelf = Main.shelf;
    if (GLib.getenv('LUMA_SHELF_TRACE_LIFT') === '1') {
        const seen = new Set();
        const hook = () => {
            for (const group of shelf._groups) {
                if (seen.has(group)) continue;
                seen.add(group);
                group.connect('notify::scale-x', () => console.log(`[lift-trace] scale ${group.scale_x} dragging ${group.dragging} active ${!!shelf._arrange._drag} ${new Error().stack}`));
            }
        };
        hook();
        const sync = shelf._syncGroups.bind(shelf);
        shelf._syncGroups = (...args) => { const value = sync(...args); hook(); return value; };
        const lift = shelf._arrange.syncDragLift.bind(shelf._arrange);
        shelf._arrange.syncDragLift = () => {
            const value = lift();
            console.log(`[lift-trace] sync active ${!!shelf._arrange._drag} scale ${shelf._arrange._dragGroup()?.scale_x} transition ${!!shelf._arrange._dragGroup()?.get_transition('scale-x')}`);
            return value;
        };
    }
    const animated = GLib.getenv('LUMA_SHELF_REDUCED_MOTION') !== '1';
    global.force_animations = animated;
    new Gio.Settings({schema_id: 'org.gnome.desktop.interface'}).set_boolean('enable-animations', animated);
    Main.overview.hide();
    await sleep(500);
    check('requested animation preference is applied', St.Settings.get().enable_animations === animated);
    for (const id of ['dock', 'clock']) {
        const actor = id === 'dock' ? shelf.islandActorFor(id) : shelf.partActorFor(id);
        const first = frames.find(frame => frame[id] && frame[id][2] > 0)?.[id];
        const final = rect(actor);
        check(`${id} first painted geometry is settled`, first &&
            first.every((v, i) => Math.abs(v - final[i]) < 4), JSON.stringify({first, final}));
    }
    if (GLib.getenv('LUMA_SHELF_STARTUP_ONLY') === '1') {
        await shot('settled');
        return;
    }
    const seat = global.stage.context.get_backend().get_default_seat();
    const pointer = seat.create_virtual_device(Clutter.InputDeviceType.POINTER_DEVICE);
    const touch = seat.create_virtual_device(Clutter.InputDeviceType.TOUCHSCREEN_DEVICE);
    const now = () => GLib.get_monotonic_time();
    const targetApp = Shell.AppSystem.get_default().lookup_app('org.projectluma.ShelfProbe01.desktop');
    const button = descendants(shelf._dash).find(actor => actor._delegate?.app === targetApp && actor.reactive);
    check('real application button exists', !!button);
    async function press(actor, name, touchscreen = false) {
        const [x, y, w, h] = rect(actor);
        if (touchscreen) touch.notify_touch_down(now(), 0, x + w / 2, y + h / 2);
        else {
            pointer.notify_absolute_motion(now(), x + w / 2, y + h / 2);
            await sleep(70);
            pointer.notify_button(now(), Clutter.BUTTON_PRIMARY, Clutter.ButtonState.PRESSED);
        }
        await sleep(100);
        const picked = global.stage.get_actor_at_pos(Clutter.PickMode.REACTIVE, x + w / 2, y + h / 2);
        console.log('Press target '+JSON.stringify({name,rect:[x,y,w,h],picked:picked?.name,classes:picked?.get_style_class_name?.(),canArrange:shelf.canArrange,desktop:shelf._isDesktopSession(),pointer:global.get_pointer(),tray:Main.panel.statusArea.quickSettings.menu.isOpen,quick:Main.panel.statusArea.quickSettings.menu.isOpen}));
        const carriers = [shelf.islandActorFor('dock'), shelf.islandActorFor('quick-options'),
            shelf.partActorFor('clock'), ...shelf._groups, ...shelf._groups.map(group => group.surface)];
        check(`${name} press keeps surfaces at normal scale`, carriers.filter(Boolean).every(a =>
            Math.abs(a.scale_x - 1) < 0.0001 && Math.abs(a.scale_y - 1) < 0.0001));
        await sleep(130);
        check(`${name} deliberate click does not begin arrangement`, !shelf._arrange.active &&
            carriers.filter(Boolean).every(a => Math.abs(a.scale_x - 1) < 0.0001 && Math.abs(a.scale_y - 1) < 0.0001),
            JSON.stringify({active:shelf._arrange.active,scales:carriers.filter(Boolean).map(a=>[a.name,a.scale_x,a.scale_y])}));
        if (touchscreen) touch.notify_touch_up(now(), 0);
        else pointer.notify_button(now(), Clutter.BUTTON_PRIMARY, Clutter.ButtonState.RELEASED);
        await sleep(touchscreen ? 900 : 700);
    }
    await press(button, 'closed application');
    check('ordinary application click launches its window', global.get_window_actors().some(a =>
        Shell.WindowTracker.get_default().get_window_app(a.meta_window) === targetApp));
    await press(button, 'running application');
    await press(shelf.partActorFor('clock'), 'clock');
    check('clock click opens its native menu', Main.panel.statusArea.quickSettings.menu.isOpen);
    Main.panel.statusArea.quickSettings.menu.close();
    await sleep(350);
    await press(shelf.partActorFor('quick-options'), 'Quick Options');
    check('Quick Options click opens its native menu', Main.panel.statusArea.quickSettings.menu.isOpen);
    Main.panel.statusArea.quickSettings.menu.close();
    await sleep(350);
    await press(button, 'touch application', true);
    await press(shelf.partActorFor('clock'), 'touch clock', true);
    check('clock tap opens its native menu', Main.panel.statusArea.quickSettings.menu.isOpen);
    Main.panel.statusArea.quickSettings.menu.close();
    await sleep(350);
    const [dockX, dockY, , dockH] = rect(shelf.islandActorFor('dock'));
    const cx = dockX + 5, cy = dockY, cw = 2, ch = dockH;
    pointer.notify_absolute_motion(now(), cx + cw / 2, cy + ch / 2);
    await sleep(70);
    pointer.notify_button(now(), Clutter.BUTTON_PRIMARY, Clutter.ButtonState.PRESSED);
    await sleep(650);
    check('intentional pointer hold enters arrangement', shelf._arrange.active && !!shelf._arrange._drag);
    const liftDeadline = GLib.get_monotonic_time() + 3000000;
    while (shelf._arrange._dragGroup()?.scale_x < 1.039 && GLib.get_monotonic_time() < liftDeadline)
        await sleep(50);
    check('recognized arrangement lifts its carrier', shelf._arrange._dragGroup()?.scale_x > 1, JSON.stringify({groups:shelf._groups.map(g=>({dragging:g.dragging,scale:g.scale_x,transition:g.get_transition('scale-x')?.progress})),preview:shelf._preview?.drag,active:shelf._arrange.active}));
    pointer.notify_button(now(), Clutter.BUTTON_PRIMARY, Clutter.ButtonState.RELEASED);
    await sleep(100);
    shelf._arrange.end();
    Main.panel.statusArea.quickSettings.menu.close();
    await sleep(400);
    const [tx, ty, , th] = rect(shelf.islandActorFor('dock'));
    touch.notify_touch_down(now(), 0, tx + 6, ty + th / 2);
    await sleep(700);
    check('intentional touch hold enters arrangement', shelf._arrange.active && !!shelf._arrange._drag, JSON.stringify({touch:[tx+6,ty+th/2],active:shelf._arrange.active,pressed:shelf.islandActorFor('dock')._lumaHoldGesture?.pressed}));
    touch.notify_touch_up(now(), 0);
    await sleep(100);
    shelf._arrange.end();
    Main.panel.statusArea.quickSettings.menu.close();
    await sleep(400);
    const settings = shelf._settings;
    const window = global.get_window_actors().find(a =>
        Shell.WindowTracker.get_default().get_window_app(a.meta_window) === targetApp)?.meta_window;
    const monitor = Main.layoutManager.primaryMonitor;
    window.maximize();
    await sleep(600);
    const edgeGap = () => {
        const frame = window.get_frame_rect();
        return monitor.x + monitor.width - frame.x - frame.width;
    };
    check('default maximized border preserves current spacing', edgeGap() === 14, String(edgeGap()));
    settings.set_int('window-border-size', 32);
    await sleep(600);
    check('border size changes actual maximized geometry', edgeGap() === 32, String(edgeGap()));
    settings.set_int('shelf-padding', 20);
    await sleep(600);
    check('chosen border size is independent of Dash padding', edgeGap() === 32, String(edgeGap()));
    settings.set_boolean('window-border-enabled', false);
    await sleep(600);
    check('disabled border reaches the unoccupied screen edge', edgeGap() === 0, String(edgeGap()));
    check('disabling the border preserves its chosen size', settings.get_int('window-border-size') === 32);
    settings.set_boolean('window-border-enabled', true);
    await sleep(600);
    check('enabling the border restores its chosen size', edgeGap() === 32, String(edgeGap()));
    window.make_fullscreen();
    await sleep(600);
    const full = window.get_frame_rect();
    check('true fullscreen continues to fill the monitor', full.x === monitor.x && full.y === monitor.y &&
        full.width === monitor.width && full.height === monitor.height, JSON.stringify(full));
    window.unmake_fullscreen();
    for (let attempt = 0; attempt < 40 && (window.is_fullscreen() || edgeGap() !== 32); attempt++)
        await sleep(100);
    check('leaving fullscreen restores the maximized window', !window.is_fullscreen(),
        JSON.stringify({fullscreen: window.is_fullscreen(), gap: edgeGap()}));
    settings.set_int('window-border-size', 64);
    await sleep(600);
    check('largest border size applies to maximized windows', edgeGap() === 64, JSON.stringify({gap: edgeGap(), fullscreen: window.is_fullscreen()}));
    settings.reset('window-border-size');
    settings.reset('shelf-padding');
    await sleep(600);
    await shot('settled');
    shelf._arrange.begin({select: 'clock'});
    await sleep(200);
    check('explicit arrangement remains available', shelf._arrange.active);
    shelf._arrange.end();
}
export function init() {
    const sampler = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 16, () => {sample(); return GLib.SOURCE_CONTINUE;});
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 5000, () => {
        GLib.source_remove(sampler);
        work().catch(error => check('scenario completes', false, `${error}\n${error.stack}`)).finally(() => {
            GLib.file_set_contents(`${out}/result.json`, JSON.stringify({pass: results.every(r => r.ok), results, frames}, null, 2));
            global.context.terminate();
        });
        return GLib.SOURCE_REMOVE;
    });
}
