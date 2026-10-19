# Tokay kernel source snapshots

Apply `0001-known-good-rfs2-source.patch` to exact linux-zumapro commit `c03f06b6fb9b2c8ebf608635a33ae25db1c59b19`. It includes tracked and added source files from the physically booted rfs2 development tree. Existing upstream notices and licenses remain in each file. The aggregate is a source integration patch, not a claim that all changes are new original Luma work. Its reference camera work derives from the Tegu tree at `87e6171eeabdff89b9114a1256a7a838e50a40e5`; Tegu wiring is not proof of Tokay wiring.

Use `config/mobile/tokay-physical/kernel-rfs2.config` and an appropriate pinned ARM64 build toolchain. The private absolute `CONFIG_INITRAMFS_SOURCE` path is deliberately cleared in this public config; supply your own reviewed initramfs. Private lab SSH/bootstrap and unit calibration must never be embedded in a public artifact. The lab used clang/LLD 22.1.8 and GCC 16.2.1. Build modules for the exact resulting kernel. A source snapshot is not an independently reproduced binary build or hardware qualification.

`0002-offline-runtime-tx-fence.patch` is a subsequent **unbooted** source change. Three admission/notification regressions failed before it; 43 UML driver/session/endpoint tests passed afterward with lockdep, debug spinlocks and atomic-sleep checks. ARM64 module compilation passed but those modules were not installed on the working phone. It does not establish complete modem reset/power/PCI lifecycle correctness. Apply it separately only when deliberately testing that candidate.

The known-good device tree disables CP power, modem PCI/PHY and associated paths. Do not enable the modem while native protected NV lifecycle remains incomplete. Camera sensor/ISP graph integration is likewise unfinished.
