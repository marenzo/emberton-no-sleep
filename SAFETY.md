# Safety and risk notice

**Experimental firmware modification. Not a consumer-ready product or a safety-certified modification. Do not use this tool unless you can accept permanent loss of the speaker and its settings.**

## What has and has not been tested

The original investigation installed one exact patch on one Emberton III, hardware 01.04.00, running application 9.1.7. Playback, application readback and short USB/battery timer observations succeeded. Those results do not establish reliability across other devices or conditions.

The public CLI is a refactor of the investigation scripts and has only been tested offline. Long idle operation without a BLE observer, the fully charged transition, sustained operation, manual power-off, battery and thermal protection behavior, live stock restoration, and recovery after an interrupted update have not been qualified.

## Hardware and data risks

- Bugs, interruption, power loss or unexpected device state can permanently disable the speaker, corrupt firmware or settings, and require hardware repair or replacement. There is no demonstrated unbrick procedure or guaranteed rollback.
- The backup contains the application and boot/partition region, not the entire flash. Do not treat it as a complete recovery image. Keep an independent copy before updating.
- The patch deliberately changes inactivity behavior. Longer powered operation may increase energy use, heat or battery wear. Charging/thermal protections were not intentionally modified, but their continued safe operation has not been established by this work. Hash checks and emulation are not safety certification.
- Follow the manufacturer's charging and ventilation instructions. Do not experiment on damaged or swollen batteries. Stop use if unexpected heat, smell, swelling or charging behavior occurs. Do not treat this experiment as qualified for unattended, continuously powered operation.
- Use only hardware you own or are authorized to modify. Keep USB power stable throughout staging, commit and reboot. Do not run other update tools concurrently or interrupt an update to retry it.
- If the tool rejects a version, hash, hardware revision, state or reply, investigate the mismatch. Removing checks does not make another build compatible.

## Older firmware security

This project targets **9.1.7**, not the latest security baseline. Marshall lists an Airoha security patch in 9.2.1 and Fast Pair/app-pairing security changes in 9.2.6. This patch does not include those later fixes, does not backport them, and does not assess their vulnerabilities or exploitability.

Using the supported older build may retain security issues addressed by newer vendor releases. Do not downgrade a speaker or postpone vendor security updates solely to use this project. A vendor update may remove the patch; compatibility with newer releases has not been established.

Source, checked 2026-09-28: [Marshall Emberton III firmware release notes](https://www.marshall.com/nl/en/support/speakers/support-for-emberton-iii/latest-firmware-version).

## Warranty, support and responsibility

Modification may affect manufacturer warranty coverage or eligibility for service. Applicable terms and statutory consumer rights vary; this project does not determine or waive them. The maintainers provide no guarantee of repair, recovery, compatibility, support response, or suitability for any use.

The software is provided under the [Unlicense](LICENSE), including its warranty disclaimer and limitation of liability. These warnings explain known risks; they are not a separate indemnity agreement or a promise of immunity from legal claims. Nothing here purports to exclude obligations or liability that applicable law does not allow to be excluded.

Using `--yes` deliberately authorizes this program to stage, commit and reboot. It is an operational safeguard, not a legal waiver or proof that a user read this notice.

For legal scope, third-party rights and branding, see [NOTICE.md](NOTICE.md). For handling faults and sensitive reports, see [SECURITY.md](SECURITY.md).
