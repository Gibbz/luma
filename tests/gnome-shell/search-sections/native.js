// SPDX-License-Identifier: GPL-2.0-or-later
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
const out = GLib.getenv('LUMA_SHELF_TEST_OUT');
const results = [];
const sleep = ms => new Promise(resolve => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {resolve(); return GLib.SOURCE_REMOVE;}));
const check = (name, ok, detail = '') => {results.push({name, ok: Boolean(ok), detail}); console.log(`${ok ? 'PASS' : 'FAIL'} ${name} ${detail}`);};
class Provider {
    constructor(id, kind, name) {this.id = id; this.lumaKind = kind; this.name = name; this.isRemoteProvider = false; this.maxResults = 30; this.activated = 0;}
    async getInitialResultSet(terms) {return terms.join(' ').startsWith('probe') ? Array.from({length: 30}, (_, i) => `${this.id}-${i}`) : [];}
    async getSubsearchResultSet(previous, terms) {return this.getInitialResultSet(terms);}
    filterResults(ids, max) {return ids.slice(0, max);}
    async getResultMetas(ids) {return ids.map(id => ({id, name: `Probe ${this.name} ${id.split('-').at(-1)}`, description: this.name,
        createIcon: size => new St.Icon({icon_name: 'applications-system-symbolic', icon_size: size})}));}
    activateResult() {this.activated++;}
}
async function work() {
    const search = Main.lumaSearch, dialog = search._dialog;
    const providers = [new Provider('probe-app', 'app', 'app'), new Provider('probe-setting', 'setting', 'settings'),
        new Provider('probe-file', 'file', 'file'), new Provider('org.projectluma.Depot.desktop', 'app', 'available app')];
    for (const provider of providers) dialog._results.addProvider(provider);
    search.open(); await sleep(500); dialog._entry.text = 'probe'; await sleep(700);
    const children = dialog._results._merged.get_children();
    const headings = children.filter(row => row._lumaSection && row.visible).map(row => row.text);
    check('results have Apps Settings Files Depot sections', JSON.stringify(headings.slice(0, 4)) === JSON.stringify(['Apps', 'Settings', 'Files', 'Depot']), JSON.stringify(headings));
    const rows = children.filter(row => row._lumaRank && row.visible);
    check('section limits retain all categories', ['Apps', 'Settings', 'Files', 'Depot'].every(section => rows.some(row => row._lumaSectionName === section)));
    check('default result is an actionable application row', dialog._results._defaultResult?._lumaRank?.kind === 'app');
    check('headings do not take keyboard focus', children.filter(row => row._lumaSection).every(row => !row.can_focus));
    const selected = dialog._results._defaultResult;
    selected?.activate();
    check('default result activates its owning provider', providers.some(provider => provider.activated === 1));
    search.open(); await sleep(350); dialog._entry.text = 'no-match-for-providers'; await sleep(500);
    check('empty categories are removed', !dialog._results._merged.get_children().some(row => row._lumaSection && row.visible));
    search.close();
}
export function init() {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 5000, () => {
        work().catch(error => check('native search test completed', false, String(error.stack))).finally(() => {
            GLib.file_set_contents(`${out}/result.json`, JSON.stringify({pass: results.every(r => r.ok), results}, null, 2));
            global.context.terminate();
        });
        return GLib.SOURCE_REMOVE;
    });
}
