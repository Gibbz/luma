# Native Exynos modem / RFS work

Apply `series` in order to exact exynos-modem commit `eba1e23aea1be111aa30796cc84dc4678bae2b46`. Preserve patch provenance and upstream licensing. This is native Linux daemon work, with no Android userspace core dependency.

Latest synthetic evidence: 123 host Rust tests, 123 ARM64/QEMU tests and 123 isolated Pixel CPU tests passed. An actual UML kernel-endpoint/daemon syscall simulator passed 20 checks; the earlier daemon failed the newly added explicit NV OPEN case. These are synthetic protocol/CPU tests, not physical CP or cellular qualification.

Critical correction: factory NV file IDs are 1 normal, 2 user, 3 protected. Historical code and fixtures interchanged 2/3. Do not reuse historical generated real-unit NV state without explicit provenance/migration review. Protected writes remain blocked. The latest patch implements verified NV OPEN preparation and a matching peer acknowledgement gate; full protection/unprotection/backup and carrier OPEN/CLOSE confirmation lifecycles are still incomplete. Do not infer safe physical modem operation from passing synthetic tests or enable a live CP to exercise incomplete protected NV state handling.

No real NV seeds, calibration, identifiers, firmware, backups or raw vendor disassemblies are included. Factory protocol observations are documented by the targeted source changes and regression cases. Final hardware validation requires owner-supplied unit data and carefully controlled recovery.
