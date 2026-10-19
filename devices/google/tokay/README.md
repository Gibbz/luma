# Google Pixel 9 (tokay)

Native Linux device support for the Google Tensor G4 Pixel 9. Device definitions live under `devices/google/tokay`, configuration and native service sources under `config/mobile/tokay-physical`, packaging helpers under `scripts/mobile`, and upstream changes under `patches`.

## Source and boot inputs

Use [source-pins.json](source-pins.json) for immutable kernel, modem and factory inputs. Apply the [kernel source patch](../../../patches/linux-zumapro/tokay/README.md), select `config/mobile/tokay-physical/kernel-rfs2.config`, and build for ARM64 with matching modules. The config deliberately clears the private initramfs path: set it to your locally packaged reviewed initramfs before building.

`config/mobile/tokay-physical/ram-init.in` is the native RAM-root bootstrap source. Use `scripts/mobile/render-tokay-ram-init.py` with a private local digest manifest to render it, then package it with the pinned static ARM64 BusyBox using the existing Pixel initramfs tooling. The static BusyBox input used in device tests was Fedora `busybox-1.37.0-7.fc44.aarch64`, SHA256 `5149092cf1238d65959b76df72d981f9825d09760f7ace9f56f570ea4c73d4b8`. The input manifest must supply the expected complete stock boot partition digest and the digest for every bootstrap payload. Do not substitute filename similarity for provenance.

The rootfs must contain native Fedora ARM64 Luma/Phosh/greetd/PipeWire services, matching GLES userspace and owner-supplied exact-factory firmware. The scoped overlay contains native radio, audio and desktop integration; package it using the payload names in `ram-inputs.example.json`. Build module manifests from the exact resulting kernel rather than retaining hashes from another build. The existing shared handheld composition paths provide the userspace baseline; a rootfs archive is not a universal phone installer. Firmware extraction and per-unit speaker calibration remain local inputs. No proprietary binaries or device-specific private data are distributed in this branch.

Serve the reviewed payload directory on the isolated USB network at `192.168.77.2:8000`; the phone uses `192.168.77.1`. Boot through an unlocked bootloader using `fastboot boot` only, after checking exact image identity and recovery readiness. Bootstrap downloads and verifies the payloads, marks internal storage read-only and starts Luma from tmpfs. See [INSTALL.md](INSTALL.md).

## Hardware validation

| Subsystem | Verified behavior / qualification boundary |
| --- | --- |
| Display/GLES | Native Phosh visible on fresh boots; hardware GLES corrected severe UI lag. Render frame rate has not been instrumented. |
| Touch | Gestures, keypad and short display blank/wake confirmed on the device. |
| Camera cutout | Scoped gmobile geometry selects left clock at scale 3. |
| USB | Native gadget networking/SSH. Cable and enumeration behavior need consideration in recovery. |
| Wi-Fi | Association, bidirectional hash fixtures and certificate-verified interface-bound HTTPS. |
| Bluetooth | Standard pairing and decoded stereo A2DP to a Linux peer. Headset/HFP not qualified. |
| Audio | Separate earpiece/bottom output and protected native speaker path; quiet acoustic microphone roundtrip. Call routing and all microphones not qualified. |
| Charging | Native charger/gauge/TCPM. Policy 500 mA input, about 467 mA charge, 4.20 V target; full cycle/thermal envelope not qualified. |
| Camera | Sensor identity reads; capture path not qualified. |
| Cellular | Modem disabled in the tested tree; no calls, SMS or mobile data. |
| Suspend | Short screen blank/wake works; system suspend currently hangs in UFS handling. |
| Storage/updates | Tested from RAM with internal storage read-only. Persistent installation/update/rollback not qualified. |

The native modem patch series has synthetic protocol/CPU and syscall-level test evidence described in its [README](../../../patches/exynos-modem/tokay/README.md). That evidence must not be substituted for physical modem or network qualification.
