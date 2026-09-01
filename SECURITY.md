# Security & Privacy Policy

## Personal data is never committed

This project analyses **Spotify GDPR / "Extended streaming history" exports**. Those
exports are personal data. Depending on the export package they contain:

- `ip_addr` on every listening event (third-party PII when the export is a friend's)
- email address, display name, date of birth
- postal address (`UserAddress.json`)
- payment records (`Payments.json`)
- inferred-attributes / marketing data (`Marquee.json`, `Identity.json`)

**None of it belongs in git.** Raw exports live only in `data/raw/<user>/` (and the
legacy `data/other users/`, `data/Spotify Account Data/`), all of which are
`.gitignore`d. See `data/README.md` for how to obtain and place an export.

The loader drops `ip_addr` on read; it is never persisted to the database or the
feature store.

## History was rewritten (2026-09-01)

Earlier commits tracked 9 friends' raw `*.zip` exports (introduced in `7d16c08`),
the owner's `data/Spotify Account Data/`, the multi-year `data/streaming_*.json`
files, and large enriched JSON blobs. All of these were **purged from the entire
git history** with `git filter-repo`, and two real IP-address strings that appeared
in design docs were redacted.

**If you cloned or forked this repo before 2026-09-01, delete your copy and
re-clone.** Old commit SHAs are no longer valid.

## Reporting

Found personal data anywhere in this repository or its history? Please email
**tanmaybhuskute8@gmail.com** (or open a minimal issue that does *not* repeat the
data) so it can be purged again.

## Hosted demo

The public demo runs on the maintainer's own listening history plus synthetic
placeholder users. No third party's data is served.
