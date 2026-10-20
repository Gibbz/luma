# Luma on the Unihertz Titan 2 Elite

Luma runs on the Titan 2 Elite from a microSD card. The phone keeps Android on
its internal storage and on boot slot b; Luma's kernel goes into boot slot a.
There is no ready-made Luma image for this phone yet: you build the kernel and
packages from this repository, and the system from the Fairphone 6 Alpha 1
image. This guide is for people comfortable with a Linux terminal.

This is the **Titan 2 Elite** with the MediaTek MT6878. Other Titan models use
different chips and will not start this kernel.

## What Luma never touches

Luma writes only `boot_a`, and the boot-slot record in `misc`. Never flash,
erase or format any other partition. In particular, these hold the phone's own
radio calibration and identity (its IMEI) and cannot be recreated:

`nvram`, `nvdata`, `nvcfg`, `protect1`, `protect2`, `proinfo`

The bootloader also checks `dtbo_a`, `vbmeta_a` and `vendor_boot_a` and stops
if they are not Unihertz's own, so they stay as shipped. Luma reads the
`vendor` and `nvdata` partitions (read-only) on first boot to copy the Wi-Fi,
Bluetooth and speaker firmware.

## What you need

- A Titan 2 Elite and a USB-C data cable
- A microSD card of 16 GB or more
- A Linux computer with `adb`, `fastboot`, `zstd`, `simg2img` and `sfdisk`;
  Fedora 44 or Luma for the build (`git`, `clang`, `lld`, `llvm`, `make`,
  `flex`, `bison`, `bc`, `pahole`, `lz4`, `python3`, `curl`, `rpm`, `cpio`,
  `podman`)
- From the [Fairphone 6 Alpha 1 release](../../fairphone/fp6/INSTALL.md):
  `luma-mobile-alpha1-fp6-userdata.sparse.zst` and `SHA256SUMS`
- Fedora 44's `linux-firmware` and `linux-firmware-whence` packages,
  version 20260309 or newer (the Mali GPU firmware)

## Step 1. Unlock the bootloader

Unlocking erases the phone. In Android, open Settings → About phone and tap
Build number seven times, then turn on Developer options → OEM unlocking and
USB debugging. Connect the phone and run:

```
adb reboot bootloader
fastboot flashing unlock
```

The phone asks for confirmation for only a few seconds: press **Volume Up**.
Then run `fastboot reboot` and let Android start once.

## Step 2. Build

In a checkout of this repository:

```
scripts/packages/build-titan2e-kernel.sh
scripts/packages/build-titan2e-connsys-modules.sh
scripts/packages/build-luma-titan2e-platform.sh
scripts/packages/build-mesa.sh
scripts/packages/build-luma-greeter.sh
```

The first one fetches the pinned kernel source, applies the patches and writes
`build/packages/titan2e-kernel/boot_a.img`, the modules RPM and
`kernel.release`. Check that `kernel.release` reads
`7.2.0-luma-titan2e-m2-g3a50c30a53fd`. Download the two `linux-firmware`
packages into the same checkout:

```
dnf download --releasever 44 linux-firmware linux-firmware-whence
```

## Step 3. Prepare the microSD card

Check and unpack the Fairphone 6 system image, and attach it:

```
shasum -a 256 -c SHA256SUMS --ignore-missing
zstd -d luma-mobile-alpha1-fp6-userdata.sparse.zst -o userdata.sparse
simg2img userdata.sparse userdata.img
sudo losetup -P -r -f --show userdata.img
lsblk -o NAME,LABEL,SIZE /dev/loopN
```

`losetup` prints the loop device (`/dev/loopN`). The Luma system is the
partition labelled `pmOS_root`. Find the card's device with `lsblk` before and
after inserting it (here `/dev/sdX`); everything on the card is erased. Give it
one partition and copy the system onto it:

```
printf 'label: dos\nstart=2048, type=83\n' | sudo sfdisk /dev/sdX
sudo mkfs.ext4 -L luma_root /dev/sdX1
sudo mkdir -p /mnt/luma-image /mnt/luma-card
sudo mount -o ro /dev/loopNpM /mnt/luma-image
sudo mount /dev/sdX1 /mnt/luma-card
sudo cp -a /mnt/luma-image/. /mnt/luma-card/
```

`/dev/loopNpM` is the `pmOS_root` partition. Now add the Titan parts. The
Wi-Fi and Bluetooth modules and the session launcher go straight into the
system; the packages go to a folder you install them from on the phone:

```
deploy=$(ls -d /mnt/luma-card/ostree/deploy/luma/deploy/*.0)
krel=$(cat build/packages/titan2e-kernel/kernel.release)
sudo mkdir -p "$deploy/usr/lib/modules/$krel/extra"
sudo cp -a build/titan2e-connsys/usr/lib/modules/$krel/extra/titan2e-connsys "$deploy/usr/lib/modules/$krel/extra/"
sudo install -m 0755 scripts/mobile/luma-phosh-session "$deploy/usr/libexec/luma-phosh-session"
sudo mkdir -p /mnt/luma-card/ostree/deploy/luma/var/tmp/titan2e
sudo cp build/packages/titan2e-kernel/RPMS/aarch64/*.rpm \
  build/packages/luma-titan2e-platform/RPMS/noarch/*.rpm \
  build/packages/mesa/aarch64/RPMS/aarch64/*.rpm \
  build/packages/luma-greeter/aarch64/luma-greeter-*.rpm \
  linux-firmware-*.rpm \
  /mnt/luma-card/ostree/deploy/luma/var/tmp/titan2e/
sudo umount /mnt/luma-card /mnt/luma-image
sudo losetup -d /dev/loopN
```

Put the card in the phone.

## Step 4. Install the Luma kernel

Connect the phone with Android running and USB debugging on:

```
adb reboot bootloader
fastboot devices
fastboot flash boot_a build/packages/titan2e-kernel/boot_a.img
fastboot set_active a
fastboot reboot
```

## Step 5. First start

Luma starts in about a minute. Sign in as **luma** with the password **1234**
and change the password in Settings. The keyboard works from the start; touch,
Wi-Fi, sound and the GPU follow once the Titan packages are installed. Open
Terminal and run:

```
cd /var/tmp/titan2e
sudo rpm -Fvh mesa-*.rpm
sudo rpm -Uvh linux-firmware-*.rpm titan2e-kernel-modules-*.rpm luma-titan2e-platform-*.rpm luma-greeter-*.rpm
sudo systemctl reboot
```

After this restart Luma marks slot a as booted successfully, and the phone
keeps starting Luma. On the first start with the platform package, Luma copies
the Wi-Fi, Bluetooth and speaker firmware from the phone's own partitions.

## Switching between Luma and Android

To start Android, run this in Luma's Terminal. It tells the bootloader to use
slot b next and restarts the phone:

```
sudo luma-titan2e-boot-android
```

To come back to Luma, start Android with USB debugging on and run:

```
adb reboot bootloader
fastboot set_active a
fastboot reboot
```

The phone has no button combination for fastboot, so `adb reboot bootloader`
from Android is the way in. Check that it works on your phone before you rely
on it.

## If something goes wrong

- If Luma does not start before Step 5 is done, the bootloader falls back to
  Android on slot b after a few attempts.
- Without the microSD card, the Luma kernel restarts the phone after 30
  seconds and tries again. Put the card back to start Luma, then switch to
  Android as above.
- Never flash or erase any partition other than `boot_a`, never relock the
  bootloader, and never change `vbmeta`, `dtbo` or `vendor_boot`.
