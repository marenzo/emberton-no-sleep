# Preparing a public release

Release as an **experimental source-code project**, not a qualified firmware product. The public CLI has not yet performed a live update. Do not remove that statement until matching evidence exists. Disclaimers do not establish legal clearance or safety certification.

## Source and artifact review

1. Review `SAFETY.md`, `NOTICE.md`, `SECURITY.md`, the README and compatibility hashes for accuracy. Check vendor release notes again; older firmware security risks must remain prominent.
2. Run `python -m unittest discover -s tests -v` and `python -O -m unittest discover -s tests`.
3. Stage the intended source changes, then run `python tools/check_release.py --index`. This checks the staged tree and reachable commit history against `release-files.txt`, checks text/size/type restrictions, and looks for common local-path, address, UUID and private-key markers. It is a limited leak check, not a general secret scanner or legal review.
4. Review the complete staged diff, commit, then run `python tools/check_release.py`. It also requires a clean tracked working tree. Ignored local material can remain but must not be uploaded.
5. Export only the audited Git tree: `git archive --format=zip --output=work/emberton-no-sleep-source.zip HEAD`. Create `work/` if needed. Never zip the entire local folder: it may contain ignored firmware and private investigation data. Git archives omit history; pushing a Git repository exposes its reachable commit history and author metadata, which also need review.
6. For Python distributions, build from the exported Git tree in a clean directory. Inspect both wheel and source archive. `MANIFEST.in` prunes private/output paths, and package data uses explicit package selection. Exclusion rules do not replace inspection. Do not upload binaries or generated firmware as release assets.
7. Verify that only project code/docs/tests, the Unlicense, safety/legal notices and packaging metadata are shipped. Include the notices in project-maintained releases so recipients can understand the risks. This is release guidance, not an attribution or notice-retention condition imposed on downstream users by the Unlicense. The wheel includes the notices in its license metadata area.

The automated allowlist is deliberately narrow. Review new files before adding their exact paths to `release-files.txt`; do not add firmware or private captures to make a check pass. If sensitive material ever entered Git history, excluding it in a later commit is insufficient. Resolve the history exposure before publication, and rotate exposed credentials where applicable.

## Hosting and communication

- No remote repository or public release is created by these instructions or the check script.
- Before publishing a repository on GitHub, configure private vulnerability reporting or a working private contact, and update `SECURITY.md` if necessary. Also review which author name/email will become public.
- Use a source-only release description stating the one-device evidence, exact compatibility, untested public CLI, unproven recovery/stock restoration, and old-firmware security tradeoff. Link the notices; do not claim the device is safe to leave continuously powered or that the modification is legal everywhere.
- Do not offer vendor firmware downloads or unsupported downgrades. Do not present the package hash as a manufacturer signature or approval.
- If legal clearance or a commercial support commitment is needed, obtain appropriate professional review. Nothing in this checklist provides it.
