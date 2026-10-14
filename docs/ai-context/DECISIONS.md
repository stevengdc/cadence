# Decisions and constraints

Only accepted choices belong here. Proposals and uncertain runtime state belong
in PROGRESS. Baseline reviewed 2026-10-14 against source and conversation history.

| Decision | Reason / consequence | Evidence |
| --- | --- | --- |
| Music-only, MIT core; optional external services | Keep deployment portable; Immich, host provisioning and films/series excluded | LICENSE, README, user scope |
| Standard-library API + SQLite | Existing alpha architecture; avoid introducing a framework/database migration incidentally | `app.py`, `accounts.py` |
| One shared file library, personal taste/playlist ownership | Multiple accounts must not overwrite each other's choices | `accounts.overlay_tracks`, `playlists.check_playlist` |
| “Not today” means defer | Preserve uncertainty without recording a rejection | `accounts.defer`, `radio.select` |
| Acquisition and redistribution require approval | Preserve explicit control; identity approval never bypasses quality checks | `acquisition.eligible`, `review.control`, `redistribution.py` |
| Failed approved import retains approval | Repeated confirmation was caused by an import failure, not a missing choice | `acquisition.tick/control`, `test_review.py` |
| FLAC metadata repair uses lossless encoding and decoded sample hashes | Stream-copy staging lost discard padding in the affected files; compressed-byte comparisons were insufficient | `review.publish`; historical real-file checks, 2026-10-12 |
| Recoverable library replacement/removal | Preserve originals, verify signatures and playlists before retiring files | `remaster.publish/finish`, `library.remove/restore` |
| Radio first publishes an Emby playlist | Works with current server/client path; direct player radio hook is unvalidated | `radio.create`; not a continuous stream |
| Existing styles take precedence | Fill missing values from Emby/verified catalog; empty scanned tags must not erase known style | `genres.refresh`, `app.scan` |
| Backups use bounded destinations and verified full archives | Avoid arbitrary host paths; unavailable external mounts fail; retention follows verification | `backups.py`, README backup section |
| Native installation and portable Compose must converge deliberately | Current code/config differ; a blind replacement can lose deployment behavior | Historical deployed-file comparison; consolidation still pending |
| AudioMuse runs as a separate optional service | Test sonic analysis locally without making an external AI API mandatory | Historical installation, 2026-10-13; no Cadence adapter yet |

## AudioMuse experiment

Historically verified: CPU lacks AVX2; official `latest-noavx2` image was used,
then pinned by digest in the private deployment. Worker CPU/memory limits were
set. Lyrics/transcription were disabled after the first test to prioritize audio
features. Daily analysis was configured for 04:00 Europe/Lisbon. Revalidate after
updates; this experimental compatibility image is not in Cadence's Compose.
AudioMuse has its own license; do not copy its implementation into the MIT core
without reviewing licensing. Keep any integration API-based and optional.

## Open choices, not decisions

- iPhone: first evaluate an Emby music client (Embeat was suggested). Navidrome
  serving the same files is an alternative, not an approved migration or installed
  component. Neither app quality nor account/playlist/history parity is validated.
- Optional language assistant: provider/model selection and spending limits are
  proposed; no OpenAI API integration or model training is implemented.
- Audio similarity, history ingestion and continuous radio behavior need design
  after validating AudioMuse output; installed analysis is not integrated radio.
