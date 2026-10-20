// SPDX-License-Identifier: GPL-2.0-or-later
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as AppDisplay from 'resource:///org/gnome/shell/ui/appDisplay.js';
const out = GLib.getenv('LUMA_INSTALLED_APPS_OUT');
const results = [];
const sleep = ms => new Promise(resolve => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
    resolve(); return GLib.SOURCE_REMOVE;
}));
const check = (name, ok, detail = '') => {
    results.push({name, ok: !!ok, detail});
    console.log(`[installed-apps] ${ok ? 'PASS' : 'FAIL'} ${name} ${detail}`);
};
async function waitFor(test, limit = 10000) {
    const start = GLib.get_monotonic_time();
    while (!test() && (GLib.get_monotonic_time() - start) / 1000 < limit)
        await sleep(50);
    return (GLib.get_monotonic_time() - start) / 1000;
}
async function work() {
    const system = Shell.AppSystem.get_default();
    const search = new AppDisplay.AppSearchProvider();
    Main.lumaSearch.open();
    await sleep(700);
    const view = Main.lumaSearch._dialog._results;
    check('Luma Search is open for live installation', Main.lumaSearch._dialog._entry.mapped);
    for (const scope of ['user', 'system']) {
        const id = `org.projectluma.FlatpakProbe.${scope}.desktop`;
        const query = `FlatpakProbe${scope}`;
        check(`${scope} application starts absent`, !system.lookup_app(id));
        Main.lumaSearch._dialog._entry.set_text(query);
        await sleep(500);
        check(`${scope} initial search has no installed result`, !view._results.applications?.includes(id));
        const directory = `${out}/${scope}/flatpak/exports/share/applications`;
        GLib.mkdir_with_parents(directory, 0o755);
        const deployment = `${out}/${scope}-deployment.desktop`;
        GLib.file_set_contents(deployment, `[Desktop Entry]\nType=Application\nName=${query}\nExec=/bin/true\nIcon=applications-games-symbolic\nCategories=Game;\nX-Flatpak=org.projectluma.FlatpakProbe.${scope}\n`);
        Gio.File.new_for_path(`${directory}/${id}`).make_symbolic_link(deployment, null);
        const elapsed = await waitFor(() => !!system.lookup_app(id));
        check(`${scope} exported app is discovered without launch`, !!system.lookup_app(id), `${elapsed.toFixed(0)} ms`);
        check(`${scope} installation appears promptly`, elapsed < 1500, `${elapsed.toFixed(0)} ms`);
        await waitFor(() => view._results.applications?.includes(id), 3000);
        check(`${scope} open search updates without retyping`, view._results.applications?.includes(id));
        const found = await search.getInitialResultSet([query], null);
        check(`${scope} application appears in search`, found.includes(id), JSON.stringify(found));
        check(`${scope} checks did not start the app`, system.lookup_app(id)?.state === Shell.AppState.STOPPED);
        Gio.File.new_for_path(`${directory}/${id}`).delete(null);
        await waitFor(() => !system.get_installed().some(info => info.get_id() === id));
        check(`${scope} removal disappears from installed apps`, !system.get_installed().some(info => info.get_id() === id));
        await waitFor(() => !view._results.applications?.includes(id), 1500);
        check(`${scope} open search removes an uninstalled app`, !view._results.applications?.includes(id));
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
