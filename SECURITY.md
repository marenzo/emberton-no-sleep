# Security and fault reporting

## Scope

No release has a security-support or response-time guarantee. Version 0.1.0 is experimental and targets only the exact application/boot hashes listed in `docs/technical.md`. It does not maintain or secure the vendor's older firmware. See the newer-firmware security warning in `SAFETY.md`.

If an update fails, retain the local log and backup. Do not repeatedly flash, remove validation checks, or assume an acknowledged commit means the installed image is verified. If charging or temperature is abnormal, stop using the device and follow the manufacturer's safety guidance.

## Private reports

For a vulnerability, unintended writes, exposed credentials, or another sensitive problem, use the published repository's **Security → Report a vulnerability** option when enabled. If that option is absent, open a public issue asking only for a private reporting channel. Do not include the vulnerability details or sensitive files in that request. No private endpoint or email address is promised until one is configured.

Maintainers must enable and test private vulnerability reporting, or publish a functioning private contact, before advertising a private reporting channel. GitHub documentation: [private vulnerability reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately).

## Safe bug reports

Useful public details: tool commit/version, OS/Python/Bleak versions, speaker model and hardware/firmware versions, last completed step, and a minimal redacted error message. State whether results came from hardware or a simulator.

Do not attach firmware dumps, generated update packages, raw Bluetooth captures, pairing data, keys, serial numbers, Bluetooth addresses/UUIDs, or full local paths. Logs and backup manifests may contain identifiers or firmware bytes in error replies; inspect and redact them before sharing. Avoid uploading the whole working directory or `private/`/`work/` folders.

The runtime code communicates locally over BLE and writes local output. There is no intentional telemetry or upload code. Package installation may contact package indexes, and dependency behavior is governed by those projects. This statement is not an independent security audit.
