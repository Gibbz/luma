// SPDX-License-Identifier: GPL-2.0-or-later
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
const out = GLib.getenv('LUMA_BORDER_SHELL_OUT');
const results = [];
const sleep = ms => new Promise(resolve => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
    resolve(); return GLib.SOURCE_REMOVE;
}));
const check = (name, ok, detail = '') => {
    results.push({name, ok: !!ok, detail});
    console.log(`[border-settings] ${ok ? 'PASS' : 'FAIL'} ${name} ${detail}`);
};
Gio._promisify(Shell.Screenshot.prototype, 'screenshot_stage_to_content');
Gio._promisify(Shell.Screenshot, 'composite_to_stream');
async function work() {
    const child = Gio.Subprocess.new(['gnome-control-center', 'windows'], Gio.SubprocessFlags.NONE);
    try {
        let actor;
        for (let attempt = 0; attempt < 100; attempt++) {
            actor = global.get_window_actors().find(window => {
                const app = Shell.WindowTracker.get_default().get_window_app(window.meta_window);
                return app?.get_id() === 'org.gnome.Settings.desktop';
            });
            if (actor?.mapped) break;
            await sleep(100);
        }
        check('installed Settings opens in the native Shell', !!actor?.mapped);
        if (!actor?.mapped) return;
        const window = actor.meta_window;
        window.maximize();
        await sleep(1500);
        const state = new Gio.Settings({schema_id: 'org.project_luma.shell-state'});
        const monitor = Main.layoutManager.primaryMonitor;
        const gap = () => {
            const frame = window.get_frame_rect();
            return monitor.x + monitor.width - frame.x - frame.width;
        };
        check('installed Settings maximizes with the default border', gap() === 14, String(gap()));
        state.set_int('window-border-size', 32);
        for (let attempt = 0; attempt < 40 && gap() !== 32; attempt++) await sleep(100);
        check('installed Settings follows a changed border size', gap() === 32, String(gap()));
        state.set_boolean('window-border-enabled', false);
        for (let attempt = 0; attempt < 40 && gap() !== 0; attempt++) await sleep(100);
        check('installed Settings reaches the edge with border disabled', gap() === 0, String(gap()));
        state.set_boolean('window-border-enabled', true);
        state.set_int('window-border-size', 14);
        await sleep(1500);
        const frame = window.get_frame_rect();
        const [content, scale] = await new Shell.Screenshot().screenshot_stage_to_content();
        const stream = Gio.File.new_for_path(`${out}/settings-window.png`).replace(null, false, Gio.FileCreateFlags.NONE, null);
        await Shell.Screenshot.composite_to_stream(content.get_texture(), frame.x, frame.y, frame.width, frame.height,
            scale, null, 0, 0, 1, stream);
        stream.close(null);
        check('installed Settings window renders at a usable size', frame.width > 600 && frame.height > 400);
    } finally {
        child.force_exit();
    }
}
export function init() {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 5000, () => {
        work().catch(error => check('scenario completes', false, `${error}\n${error.stack}`)).finally(() => {
            GLib.file_set_contents(`${out}/result.json`, JSON.stringify({pass: results.every(r => r.ok), results}, null, 2));
            global.context.terminate();
        });
        return GLib.SOURCE_REMOVE;
    });
}
