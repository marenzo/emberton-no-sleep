# Contributing

Keep changes small and explain their hardware scope, evidence, failure behavior and limitations. Run `python -m unittest discover -s tests -v` and the release checks in `docs/releasing.md`. Ordinary development and CI must remain offline and must not flash a device.

Contribute only material you have the right to share. By submitting original contributions for inclusion, you agree to release them under the project's [Unlicense](LICENSE), including its public-domain dedication. No author credit is required for that original material. Contribute only if you have authority to make that dedication. Preserve relevant third-party notices and identify the origin/license of any copied or adapted code. Do not copy code from a reference project merely because it is publicly accessible.

Do not submit vendor images, firmware packages, device identifiers, pairing data, secrets, or raw private logs in commits, pull requests or issue attachments. Avoid lowering compatibility checks or adding unbounded write commands. A new supported hash/build needs its own analysis and evidence; matching a marketing name or version string is insufficient.

Distinguish tests of the original investigation from tests of the public CLI. Do not describe successful emulation as hardware validation, restoration as proven recovery, or this tool as approved by the manufacturer.

Report vulnerabilities privately as described in `SECURITY.md`. Feature requests and non-sensitive, redacted bug reports may use public issues.
