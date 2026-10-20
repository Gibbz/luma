/* SPDX-License-Identifier: LGPL-2.1-or-later */
const value = item => item && typeof item === "object" && "v" in item ? item.v : item;

// Only a manual plan that retains an existing ESP offers this choice. Keep
// automatic plans and newly formatted boot partitions from inheriting it.
export const preserveExistingBootOrder = ({ method, requests = [], choice = true }) =>
    method === "MANUAL" && choice === true && requests.some(request =>
        value(request["mount-point"]) === "/boot/efi" &&
        value(request["format-type"]) === "efi" && !value(request.reformat));
