/* SPDX-License-Identifier: LGPL-2.1-or-later */
import assert from "node:assert/strict";
import { test } from "node:test";
import { preserveExistingBootOrder } from "../../src/model/bootloader.js";

const esp = { "mount-point": "/boot/efi", "format-type": "efi", reformat: false };
test("manual reuse keeps the existing default unless explicitly changed", () => {
    assert.equal(preserveExistingBootOrder({ method: "MANUAL", requests: [esp] }), true);
    assert.equal(preserveExistingBootOrder({ method: "MANUAL", requests: [esp], choice: false }), false);
    assert.equal(preserveExistingBootOrder({ method: "MANUAL", requests: [esp], choice: "true" }), false);
});
test("automatic, reformatted and non-EFI plans cannot inherit the manual choice", () => {
    for (const method of ["AUTOMATIC", "CUSTOM", undefined]) {
        assert.equal(preserveExistingBootOrder({ method, requests: [esp], choice: true }), false);
    }
    for (const requests of [[], [{ ...esp, reformat: true }], [{ ...esp, "format-type": "vfat" }], [{ ...esp, "mount-point": "/boot" }]]) {
        assert.equal(preserveExistingBootOrder({ method: "MANUAL", requests, choice: true }), false);
    }
});
test("the real manual D-Bus variant shape obeys the same preservation rules", () => {
    const requests = [Object.fromEntries(Object.entries(esp).map(([key, v]) => [key, { v }]))];
    assert.equal(preserveExistingBootOrder({ method: "MANUAL", requests, choice: true }), true);
    requests[0].reformat.v = true;
    assert.equal(preserveExistingBootOrder({ method: "MANUAL", requests, choice: true }), false);
});
