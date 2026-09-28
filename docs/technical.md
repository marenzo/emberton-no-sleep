# Patch and validation

## Compatibility

| Item | Required value |
| --- | --- |
| Model | EMBERTON III |
| Hardware | 01.04.00 |
| Application | 9.1.7 |
| Application base / size | `0x08133000` / `0x1f9000` |
| Original application SHA256 | `72b7ba32aadf5c48f8ca9946da56f9383c0d4d9649142eb2e8b5559bc68f20ae` |
| Patched application SHA256 | `37ba02a3a249e5dc3928a686d43620413ea3c3668766b17793996d9aec43f47b` |
| Boot/partition acquisition | `0x08000000`, length `0x13000` |
| Boot/partition SHA256 | `7167ff65d3425bdc9716a75ae9ab3d2e20e690a012642a0c78938b1eba57f4cf` |
| Patched package SHA256 | `e946425aee74cc4579522da3a36d0b755a479daa9c02b373ab796e1f1d8b2291` |
| Stock package SHA256 | `12c2e7349d8c9a601ead56d7af4b7cbf7bbc6c01eb1f1ddc76c486fd7f568585` |

Even another speaker reporting 9.1.7 can differ. The hashes, not just the version string, determine compatibility. The boot acquisition includes partition metadata; a differing layout is rejected.

## Timer patch

The callback at `0x081a74c4` uses counter `0x1423a248`, enable byte `0x1423a24c`, and threshold `0x1423a1fa`. Its setup routine selects 600 or 3600 in certain states and disables counting in others. With a connected, paused Bluetooth audio source the observed state selected 3600 and counted once per second. Expiry uses a strict greater-than comparison.

Replace the two literal loads at `0x081a74e8` (`31493248`) with a Thumb BL (`83f18afd`) to a 40-byte helper at `0x0832b000`. The helper saves registers, calls the existing PMU query at `0x081abd24`, and restores registers. When the returned power-source value is zero it reproduces the displaced loads and returns to the original callback. Otherwise it clears the counter, retains the enable flag, and branches to the callback epilogue at `0x081a754a`.

The helper space was erased application padding in the supported image. Its use has been demonstrated on one device, not established as a vendor-reserved extension area. The observed power-source sequence was USB=1, battery=0, USB=1. Full-charge behavior remains untested.

## Update protocol

BLE writes to `43484152-2dab-3241-6972-6f6861424c45`; notifications come from `43484152-2dab-3141-6972-6f6861424c45`. RACE frames contain head, type, little-endian length and command. Reply fragments are reassembled; both acknowledgment and completion notification are required for asynchronous operations.

The 12 KB raw FOTA package has a 4 KB header with TLVs for basic information, movers, hashes and version. Its leading SHA256 covers bytes 256 through the end. The two payload sectors are ordered helper first (`0x0832b000`), hook second (`0x081a7000`). Unchanged bytes in both sectors are preserved.

The staging query reports offset `0x004a1000` and usable size `0x353000`. The initialized write guard includes the reserved metadata sector and reports size `0x354000`. Direct erase/program commands are limited to `[0x004a1000, 0x004a4000)`; the bootloader performs the application replacements after commit. This overwrites application sectors; it is not a dual-bank swap or proven power-failure recovery scheme.

Sequence: start `1c08`, validate write guard, start transaction `1c0a`, state `0201`, state `0210`, staging erase `0404`, 48 single-page writes `0402`, full staging readback `0403`, integrity `1c01`, state `0211`, power/state recheck, commit `1c02`. State payloads are little-endian. The device echoes state writes. Programming uses CRC polynomial 0x31 with initial zero and a final bit reversal. No RAM writes are sent; `1680` is used only for fixed diagnostic reads.

## Evidence and limits

The original scripts, before this public refactor, achieved:

- Two identical full reads of the stock application.
- Thirteen instruction-emulation cases for USB/battery timer behavior, including threshold crossing and stack restoration.
- Four boot-update emulation cases: stock and patched packages copied correctly; corrupted payload and invalid destination were rejected before application erase.
- A live update with all 48 pages acknowledged, matching staging readback, successful device integrity check and commit.
- Reboot, both modified sectors verified, and a full 2,068,480-byte application readback matching the patched SHA256.
- Bluetooth audio playback confirmed by the owner; enabled battery counter observed at 19, 52 and 84 seconds; reconnecting USB returned it to zero across repeated samples.

The public builder reproduces those application/package hashes. Its CRC matches all 48 captured successful program requests. The public CLI has offline transport/update tests, including refusal to commit after failed integrity, bad readback or loss of USB power. It has not been re-flashed onto hardware as part of repository preparation. The original emulator harnesses/captures are not distributed in this minimal repo.

No hour-long disconnected idle qualification, full-charge transition test, manual-off/thermal/protection qualification, successful hardware stock restoration, or independent recovery interface has been demonstrated. Hash/integrity acceptance here does not establish the absence of secure boot across the whole device.

## References

The implementation was developed by inspecting the device's acquired application and boot code, using the Airoha RACE protocol research as a reference. No third-party flasher is imported or executed.

- [Airoha RACE toolkit](https://github.com/auracast-research/race-toolkit) (packet-format reference; not bundled)
- [ERNW RACE research](https://static.ernw.de/whitepaper/ERNW_White_Paper_74_1.0.pdf)
- [Marshall app protocol research](https://github.com/c0ffee-audio/marshall-protocol) (the generic auto-off characteristics were absent on this device)

These references describe broader product families; their commands are not automatically applicable to this speaker.
