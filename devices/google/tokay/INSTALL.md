# Tokay development boot boundaries

There is no qualified persistent installation procedure. Do not apply Fairphone partition instructions or manifests to this Pixel. The working method is an unlocked Pixel bootloader loading a device-specific development boot image using `fastboot boot`. The required private bootstrap root and owner-supplied firmware/calibration are intentionally not in this public repository. No public binary image is being distributed by this branch.

Before a controlled RAM boot, verify the exact device, boot image hash, firmware provenance, stable USB data connection, powered host, recoverable stock slots and complete matching module/rootfs payloads. Observe kernel identity and actual end-to-end behavior after boot. A device node, service startup or frame-completion interrupt alone is not a working subsystem.

An eligible locked Pixel can be unlocked through Android Developer options/OEM unlocking and the official bootloader unlock procedure, which erases user data. The lab phone was already unlocked; this port did not run unlock or wipe commands. Preserve original calibration/identity data before development. Keep the exact factory image and independently verified hashes. Never repartition, relock, write vbmeta, or overwrite persist/EFS/modem storage as a bring-up shortcut. Factory recovery may erase personal data and requires a separately reviewed restore plan.

Firmware must come from the exact factory package pinned in `source-pins.json`; never mix same-named firmware from other builds. Per-unit calibration must belong to the target phone. No Android userspace is required for core Luma operation. Android factory diagnostics are separate from the native runtime.

Full suspend, camera capture, cellular registration/calls/data, power/thermal qualification and persistent installation/update/rollback remain blockers. This branch must not be advertised as release-ready.
