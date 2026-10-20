// SPDX-License-Identifier: GPL-2.0-or-later
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Clutter from 'gi://Clutter';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {getNotificationTray} from 'resource:///org/gnome/shell/ui/lumaNotificationBeacon.js';
const out = GLib.getenv('LUMA_SHELF_TEST_OUT');
const results = [];
const sleep = ms => new Promise(resolve => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {resolve(); return GLib.SOURCE_REMOVE;}));
const check = (name, ok, detail = '') => {results.push({name, ok: Boolean(ok), detail}); console.log(`${ok ? 'PASS' : 'FAIL'} ${name} ${detail}`);};
async function work() {
    const player = Gio.Subprocess.new(['python3', '/source/tests/gnome-shell/dash-layout/player.py'], Gio.SubprocessFlags.NONE);
    await sleep(1800);
    const shelf = Main.shelf;
    const state = new Gio.Settings({schema_id: 'org.project_luma.shell-state'});
    const lip = getNotificationTray();
    try {
    for (const edge of ['left', 'right', 'top', 'bottom']) {
        state.set_value('shelf-arrangement', new GLib.Variant('aa{sv}', []));
        state.set_string('shelf-edge', edge);
        await sleep(700);
        check(`${edge} dash placement`, shelf.edgeOfIsland('dock') === edge);
        lip._place();
        await sleep(100);
        const monitor = Main.layoutManager.primaryMonitor;
        const [, y] = lip.get_transformed_position();
        const [, height] = lip.get_transformed_size();
        check(`${edge} notification edge`, edge === 'top'
            ? Math.abs(y + height - monitor.y - monitor.height) <= 1
            : Math.abs(y - monitor.y) <= 1, `${y},${height}`);
        lip.open();
        await sleep(500);
        const [, trayY] = lip.get_transformed_position();
        const [, trayHeight] = lip.get_transformed_size();
        check(`${edge} expanded notification edge`, edge === 'top'
            ? Math.abs(trayY + trayHeight - monitor.y - monitor.height) <= 1
            : Math.abs(trayY - monitor.y) <= 1, `${trayY},${trayHeight}`);
        lip.close(); await sleep(400);
        const media = shelf._media;
        if (media) {
            check(`${edge} active media shown`, media.mapped && !!media.selection.selected);
            media.setVertical(edge === 'left' || edge === 'right');
            check(`${edge} media hides unused text container`, media._copyStack.visible === (edge === 'top' || edge === 'bottom'));
            const island = shelf._mediaIsland.get_transformed_extents();
            for (const [name, control] of [['artwork', media._artTile], ['previous', media._previous], ['pause', media._toggle], ['next', media._next]]) {
                const bounds = control.get_transformed_extents();
                check(`${edge} media ${name} fits`, control.mapped && bounds.get_x() >= island.get_x() - 1 && bounds.get_y() >= island.get_y() - 1 &&
                    bounds.get_x() + bounds.get_width() <= island.get_x() + island.get_width() + 1 &&
                    bounds.get_y() + bounds.get_height() <= island.get_y() + island.get_height() + 1);
            }
        }
        if (edge === 'left' || edge === 'right') {
            const quick = Main.panel.statusArea.quickSettings;
            check(`${edge} clock centered`, quick._statusTimeRow.x_align === Clutter.ActorAlign.CENTER &&
                quick._statusDateShort.x_align === Clutter.ActorAlign.CENTER);
        }
    }
    } finally {player.force_exit();}
}
export function init() {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 5000, () => {
        work().catch(error => check('native dash test completed', false, String(error.stack))).finally(() => {
            GLib.file_set_contents(`${out}/result.json`, JSON.stringify({pass: results.every(r => r.ok), results}, null, 2));
            global.context.terminate();
        });
        return GLib.SOURCE_REMOVE;
    });
}
