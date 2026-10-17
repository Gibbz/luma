# Luma Mobile Alpha 1 for Fairphone 6

Luma Mobile is the same Luma operating system as the desktop, running on the Fairphone 6. Alpha 1 is an early release for people comfortable using a terminal. Installing it **erases everything on the phone**.

## What you download

You need three things, in one folder. The first two are Luma; the third is Fairphone's own firmware, which Luma runs on top of.

| | File | Size | What it is |
|---|---|---|---|
| 1 | [luma-mobile-alpha1-fp6-userdata.sparse.zst](https://simplyluma.com/get/mobile/fp6/alpha1/system) | 1.2 GB | **The complete Luma system**: the OS, apps and settings, compressed. |
| 2 | [luma-mobile-alpha1-fp6-boot.bin](https://simplyluma.com/get/mobile/fp6/alpha1/boot) | 101 MB | The Luma boot file (kernel and startup). |
| 3 | [Fairphone 6 factory package](https://support.fairphone.com/hc/en-us/articles/18896094650513-How-to-manually-install-Android-on-your-Fairphone) | from Fairphone | Fairphone's official firmware for the phone's modem, camera and other hardware. Always use the **newest** version on that page. An older one can make the phone unusable. |

Also download [SHA256SUMS](https://simplyluma.com/get/mobile/fp6/alpha1/sums) to check that the Luma files arrived intact.

## Before you start

- A Fairphone 6 and a USB-C **data** cable
- A computer with `fastboot` (Android platform tools, version 35 or newer) and `zstd`:
  - macOS: `brew install android-platform-tools zstd`
  - Fedora or Luma: `sudo dnf install android-tools zstd`
  - Windows: Android platform tools from Google, and `zstd` from its GitHub releases
- About 20 GB of free space on the computer
- A backup of everything on the phone
- A **physical SIM card**. Adding eSIM profiles isn't available in Alpha 1 yet. If your plan is eSIM-only, ask your carrier for a physical SIM first.

## Install

### Step 1. Download the files

Download the system file (1), the boot file (2), `SHA256SUMS`, and the newest Fairphone 6 factory package (3) into one folder.

### Step 2. Unlock the bootloader

Follow Fairphone's official unlocking instructions: turn on Developer options and OEM unlocking, get your unlock code from Fairphone's website, then run both `fastboot flashing unlock` and `fastboot flashing unlock_critical`. Unlocking erases the phone.

### Step 3. Install Fairphone's firmware

Unzip the Fairphone 6 factory package (file 3) and open a terminal in its folder. Fairphone's script normally erases the phone's modem settings, where its IMEI lives. Luma needs those settings kept, so first remove those two lines from the script, and remove the script from the package's checksum list so the package check still passes:

- macOS: `sed -i '' '/erase modemst/d' flash_fp6_factory.command && sed -i '' '/flash_fp6_factory.command/d' SHA256SUMS`
- Linux: `sed -i '/erase modemst/d' flash_fp6_factory.sh && sed -i '/flash_fp6_factory.sh/d' SHA256SUMS`
- Windows (Command Prompt): `bin-msys\usr\bin\sed.exe -i "/erase modemst/d" flash_fp6_factory.command` then `bin-msys\usr\bin\sed.exe -i "/flash_fp6_factory.command/d" SHA256SUMS`

Then run the script, following [Fairphone's instructions](https://support.fairphone.com/hc/en-us/articles/18896094650513-How-to-manually-install-Android-on-your-Fairphone). This gives the phone matching firmware on both of its system slots, which Luma's updates rely on. When the script finishes, the phone restarts into Android. Before installing Luma, let Android save the phone's modem settings, including its IMEI:

1. Go through Android's setup (you can skip accounts), connect to Wi-Fi, and turn on your SIM or eSIM.
2. Wait for signal bars, then use mobile data for a couple of minutes.
3. Restart Android once, and wait until it's back.
4. Hold Power and turn the phone off.

Don't skip this; without it, calls, mobile data and eSIM won't work in Luma.

### Step 4. Check and unpack Luma

Open a terminal in the folder with the Luma files and run:

```
shasum -a 256 -c SHA256SUMS
zstd -d luma-mobile-alpha1-fp6-userdata.sparse.zst -o luma-mobile-alpha1-fp6-userdata.sparse
head -c 31457280 /dev/zero > dtbo-blank.bin
```

Both files must report `OK`. The last line makes an empty 30 MB file; Luma brings its own device tree, so Android's overlay partition must be blank.

### Step 5. Install Luma

Turn the phone off. Hold **Volume Down**, then press **Power**, and keep holding until the Fastboot screen appears. Connect it to the computer and check that it's the right phone:

```
fastboot devices
fastboot getvar product
fastboot getvar current-slot
```

`product` must say `FP6`, and `current-slot` must say `a`. Then install Luma. The first command takes about ten minutes, and the next one can take up to five more while the phone finishes writing. Let each one finish:

```
fastboot flash userdata luma-mobile-alpha1-fp6-userdata.sparse
fastboot flash dtbo_a dtbo-blank.bin
fastboot flash dtbo_b dtbo-blank.bin
fastboot flash boot_a luma-mobile-alpha1-fp6-boot.bin
fastboot flash boot_b luma-mobile-alpha1-fp6-boot.bin
fastboot boot luma-mobile-alpha1-fp6-boot.bin
```

The last command starts Luma's first boot straight from the computer. Use it instead of `fastboot reboot`: it keeps the phone's modem settings (its IMEI) safe while Luma makes its own copy of them. After this first start, the phone restarts normally.

### Step 6. First start

The first start takes a minute or two while Luma expands to fill the phone's storage. Sign in as **luma** with the password **1234**, then change the password in Settings right away. Luma Connect is optional; the phone works fully without it.

## If something goes wrong

- To start over, repeat Step 5. Reinstalling `userdata` erases the phone.
- To go back to Android, repeat Step 3.
- No mobile network in Luma, or the IMEI shows as unknown: repeat Step 3, including the Android steps, then Steps 5 and 6. The last install command must be `fastboot boot`, not `fastboot reboot`.
- Never flash partition tables, relock the bootloader, or erase partitions other than those listed here.

## Instructions for an AI assistant

Paste this section into an AI assistant to have it walk you through the install.

> You are helping someone install Luma Mobile Alpha 1 on a Fairphone 6 with `fastboot`. Follow the six steps in this guide exactly, one at a time.
>
> - Ask which system the computer runs (macOS, Fedora or Luma, Windows) and give the matching command to install `fastboot` and `zstd`.
> - The Luma files are `luma-mobile-alpha1-fp6-userdata.sparse.zst` (the complete system, https://simplyluma.com/get/mobile/fp6/alpha1/system), `luma-mobile-alpha1-fp6-boot.bin` (https://simplyluma.com/get/mobile/fp6/alpha1/boot) and `SHA256SUMS` (https://simplyluma.com/get/mobile/fp6/alpha1/sums). Save them under those file names. Fairphone's factory package comes from Fairphone's support site; always use the newest version there.
> - Before any flash, confirm with `fastboot devices` that exactly one phone is connected, that `fastboot getvar product` reports `FP6`, and that `current-slot` is `a`. Stop if any of these differ.
> - Verify the downloads with `SHA256SUMS` before flashing. Stop if a checksum fails.
> - Before running Fairphone's flash script, remove its two `erase modemst` lines and the script's own line in `SHA256SUMS` with the commands in Step 3. Those lines wipe the modem settings (IMEI), and without them calls, mobile data and eSIM won't work. After the script, have the person follow Step 3's Android steps exactly: SIM or eSIM on, a couple of minutes of mobile data, one Android restart, then power off. Skipping them leaves the phone without an IMEI in Luma.
> - Step 5 ends with `fastboot boot luma-mobile-alpha1-fp6-boot.bin`, never `fastboot reboot`; a normal first restart lets the bootloader erase the modem settings.
> - The `userdata` flash takes about ten minutes. Tell the person not to unplug the phone or close the terminal while it runs.
> - Explain that unlocking and flashing `userdata` erase the phone, and wait for the person to confirm their backup first.
> - Only run the commands in this guide. Never relock the bootloader, never flash partition tables (`partition:*`, `gpt`), never erase other partitions, and never change `vbmeta`. Writing the blank file to `dtbo_a` and `dtbo_b` is part of the install.
> - If a command fails, show the exact error and stop. Do not improvise a fix that writes to the phone.
> - Never ask for or record passwords, eSIM activation codes or account tokens.
> - For phones other than the Fairphone 6, say clearly that Luma does not support them yet and that any attempt is at the person's own risk.
