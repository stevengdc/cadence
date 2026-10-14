# Development state

Updated 2026-10-14. Labels: **R** = confirmed in current repository;
**H** = verified by tools earlier in this conversation, not rechecked today;
**U** = unverified / outstanding. No live services were inspected in this
documentation session.

## Implemented

- **R** Personal accounts, ratings, deferral, daily discovery/tops/previews,
  playlists, acquisition/search/retry, quality checks, manual review, loudness,
  recoverable library/remaster operations and explicit redistribution.
- **R** EN/PT UI, installer administrator/container-group prompts, resumable
  per-account welcome guide, metadata radio -> Emby playlists, configurable
  verified backups. Provider setup still uses `configure.py`.
- **R/H** Blank-screen translator shadowing fixed; repeated manual approval loop
  fixed. “Piece of Your Heart” and “O Tempo Vai Esperar” completed, MP3 320 and
  available in Emby at the historical check on 2026-10-12.
- **R/H** Library datagrid checkboxes, per-page/all-filtered selection and bulk
  playlist creation/addition; simplified downloads filters with detailed states
  under Other; sortable/searchable style column.
- **R/H** Automatic missing-style enrichment. Native timer and portable worker
  default: every 15 minutes. Historical fill: 186 tracks; two lacked confirmed
  styles. These counts are not current inventory.
- **H** AudioMuse installed separately and linked to Emby on 2026-10-13. Two-track
  test succeeded, similarity indexes created, full-library task accepted. Daily
  analysis at 04:00 configured. **U:** full task completion and present health.

## Validation history (not a current full-suite result)

- Earlier clean distribution: README records 99 backend tests and fresh Compose
  sign-in; this predates the current changes.
- Review/import correction: 115 backend tests passed in a Linux staging directory.
- Genres: three focused tests passed separately; do not claim a combined 118-test
  suite run. Frontend builds and synthetic browser bulk-selection/filter checks
  passed during earlier implementation.
- Offline failures: Emby logs showed requests for old item identifiers after
  migration. Complete current downloads of “When I'm Gone” and “With or Without
  You” returned HTTP 200 and matched server file hashes. **U:** successful retry
  on the user's phone after provider sync and queue recreation.
- Emby music real-time monitoring was enabled; complete library scan every
  12 hours. Cadence also requests refresh after publication. **H**, not today's
  config audit.

## Unfinished / known issues

- Native deployment and distributable repo are not yet consolidated. Many local
  functional changes remain uncommitted/untracked relative to HEAD `ff64ce1`;
  they must be preserved. No push/PR for these changes has been confirmed.
- `radio.py` still returns `method: metadata`; no AudioMuse client/adapter exists
  in the repository. Installing AudioMuse did not change that behavior.
- External/off-host backup remains pending. Existing Cadence archives exclude
  Emby/slskd state and migration originals; AudioMuse recovery coverage is also
  not confirmed. Backup options are not proof of a successful recoverable copy.
- FLAC migration final aggregate is unknown. Last earlier aggregate was 181/194
  complete before the subsequent review recovery; do not reuse as current status.
- Potential duplicates: “In the End” and “In the End (Album Version)” are distinct
  files with similar duration; not confirmed same recording, neither removed.
  Suggestion-only duplicate pairs also existed. Historical exact-file/path checks
  found no identical file duplicates; not a permanent uniqueness guarantee.
- iPhone support remains an evaluation: Embeat suggested but untested. Substreamer
  requires Subsonic/OpenSubsonic; direct Emby URLs are incompatible. Navidrome is
  not installed/selected. Do not equate HTTPS success with API compatibility.
- Code observation to validate when working on radio: `genres.clean` joins values
  with ` / `, while `radio.select` tokenizes commas/semicolons; multi-style matching
  may need normalization. No behavioral change made for this observation.
- Remaining roadmap: playback history, personalized sonic radio/energy controls,
  off-library discoveries via approval, optional capped API assistant, complete
  localization, guided integrations, upgrade and restore validation.

## Next priorities

1. Confirm latest user direction: iPhone evaluation versus sonic radio integration.
   Verify actual AudioMuse full-analysis results before consuming embeddings.
2. Consolidate native code/config and repository, preserve all local work, audit
   current migration/review queue and establish recoverable off-host backup.
3. Integrate optional AudioMuse similarity into Cadence radio with metadata
   fallback; validate user exclusions, variety and Emby playlist playback.
4. Validate iPhone login, playlists, offline and CarPlay. Only add a second server
   after choosing it and designing account/playlist/history synchronization.
5. Improve learning/discovery, then optional API assistant and release recovery.

Order reflects dependencies; a new explicit user task can reprioritize it.
