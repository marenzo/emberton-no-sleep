# emberton-no-sleep

Experimental firmware patch that keeps a **Marshall Emberton III awake while USB-powered** and leaves its battery idle timer intact. Audio can continue from another Bluetooth device; this tool uses BLE for backup and updates. It does **not** add remote power-on.

**Compatibility:** Emberton III, hardware 01.04.00, application 9.1.7, with the exact application and boot hashes in [technical details](docs/technical.md). Other builds are rejected.

**Evidence:** The original scripts patched one speaker. A full application readback matched, Bluetooth audio playback worked, the battery timer advanced, and USB power reset the timer. This repo's refactored CLI has passed offline tests but **has not performed a live update**. Long idle operation, full-charge behavior, live stock restoration, and recovery after a failed update remain untested.

> [!WARNING]
> Firmware updates can permanently disable the speaker or erase settings. The backup is not a complete flash image, and no unbrick method has been demonstrated. Continuous unattended operation is unqualified. Read [SAFETY.md](SAFETY.md) and [NOTICE.md](NOTICE.md) before use.
>
> This patch targets older firmware without the security fixes Marshall lists in [9.2.1 and 9.2.6](https://www.marshall.com/nl/en/support/speakers/support-for-emberton-iii/latest-firmware-version). Do not downgrade or delay vendor updates to use it.

## Quick start

Tested on macOS with Python 3.14 and Bleak 3.0.2. The code supports Python 3.11+; other platforms have not been qualified. Give your terminal Bluetooth access if macOS asks. Turn on the speaker and make its BLE advertisement discoverable.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m emberton_no_sleep scan
```

Use the ID shown by `scan` as `DEVICE_ID` (a UUID on macOS). Keep the speaker awake during backup; it can take about 20 minutes. Store a separate copy of the verified backup.

```sh
python -m emberton_no_sleep backup --device DEVICE_ID --out work/backup
python -m emberton_no_sleep build --stock work/backup/application.bin --out work/build
```

`backup` and `build` do not change the firmware. The backup covers the application and boot/partition region, **not the entire flash**. The generated firmware files stay in the ignored `work/` directory.

Install only with stable USB power and at least 30% battery. `--yes` authorizes staging, commit, and reboot. The tool checks the model, version, hashes, current image, power, staged data, and final application readback; it rejects mismatches.

```sh
python -m emberton_no_sleep install --device DEVICE_ID \
  --stock work/backup/application.bin --yes
```

If final verification fails, **do not blindly retry**. Keep the log and run the read-only check:

```sh
python -m emberton_no_sleep verify --device DEVICE_ID \
  --stock work/backup/application.bin --expect patched
```

Stock restoration requires a working BLE updater and has **not been tested on hardware**:

```sh
python -m emberton_no_sleep restore --device DEVICE_ID \
  --stock work/backup/application.bin --yes
```

## Project information

Run offline tests with `python -m unittest discover -s tests -v`. See [technical details](docs/technical.md), the [security policy](SECURITY.md), and the [release guide](docs/releasing.md). The original project code and documentation are under the [Unlicense](LICENSE); vendor firmware and third-party material are not included. Do not publish dumps, generated packages, device identifiers, or private logs.

This project was fully autonomously implemented by Codex. No single line of code was written by a human.
