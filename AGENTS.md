# Cadence development instructions

Cadence is an MIT-licensed, self-hosted music companion in early alpha: personal
taste, discovery, approval, acquisition, library management and Emby playlists.
Keep integrations optional. Immich, films/series, Proxmox/CT creation, host
provisioning and network-account configuration are outside the core project.

## Start and resume

- This directory is the Git/project root. If opened through the parent ChatGPT
  mirror, its instructions also apply: `sources/` is read-only; never modify,
  rename, move or delete synced reference files. Preserve the parent AGENTS.md.
- At session start read this file, `docs/ai-context/SESSION.md` and
  `docs/ai-context/PROGRESS.md`. Read PROJECT.md only for unfamiliar components;
  read the relevant DECISIONS.md entries before significant changes.
- Inspect `git status --short`. Existing uncommitted work may belong to earlier
  sessions; do not reset, overwrite, clean or commit it indiscriminately.
- Read only files needed for the task. Use targeted searches and symbol reads;
  do not reload every context document or repeat a documented investigation
  unless checking changed code, deployment state or an unresolved assumption.
- Distinguish **repository-confirmed**, **historically verified**, **decided**
  and **unverified**. Historical checks do not establish current runtime health.

## Code and architecture

- Python 3.12 on Linux, standard-library HTTP server and SQLite; not Flask or
  an ORM. `backend/app.py` owns API dispatch and shared state paths.
- React 19, Chakra UI 3, Emotion, lucide-react, Vite 7; npm lockfile in `ui/`.
  Python dependencies: BeautifulSoup and Mutagen; audio processing uses FFmpeg
  and ffprobe. See PROJECT.md for module relationships and commands.
- Docker Compose distributes Cadence, its worker, Emby and slskd. The existing
  native/systemd installation is a distinct deployment, not a clean Compose
  reference. Never assume code or configuration parity.
- Follow each file's existing compact style; avoid whole-file reformatting.
  Python modules/functions use snake_case; React components use PascalCase,
  hooks and handlers camelCase. Prefer the existing module boundaries.
- Follow CONTRIBUTING.md: English code, commit messages and technical docs;
  user-facing strings in both `ui/src/locales/en.json` and `pt.json`.
  In `main.jsx` the translator is `translate`; do not shadow it with a track
  variable (the former `t` collision caused a blank page).
- Use parameterized SQL and the existing `init()` schema conventions. Inspect
  existing migrations and preserve user data before changing schemas.

## Change boundaries and safety

- Change only what the requested task needs. Do not refactor, update dependencies
  or change infrastructure incidentally. Add files in the owning component;
  remove files only after checking references and preserving required data.
- Never edit generated `ui/dist/`, installed dependencies, production databases
  or media as a substitute for a source change. Rebuild assets from `ui/src/`.
- Never commit secrets, connection files, databases, music, provider responses,
  private logs or deployment archives. Respect `.gitignore` and SECURITY.md.
  Do not copy personal hostnames/IPs/accounts into distributable defaults/docs.
- Keep personal ratings, deferrals and playlist ownership isolated by account.
  “Not today” defers; it is not a dislike. Downloads and redistribution require
  the existing approvals; a manual identity approval cannot waive audio quality.
- Preserve approved sources on import failure; retry import without requesting
  approval again. Maintain path confinement, signatures, locks, atomic publishing
  and recovery behavior in library/remaster/review/backup operations.
- Back up affected state before production changes. Compare deployed files with
  repository files before replacing them. Restore service ownership/readability
  and verify service health and the served asset after deployment. Never treat
  a local build as deployment proof. This documentation does not authorize deploys.

## Validation and handoff

- Commands and Linux requirements are in PROJECT.md; CI is
  `.github/workflows/validate.yml`. Run focused checks for changed behavior;
  run backend tests and frontend build before submitting functional changes.
- Use synthetic fixtures and temporary state. Do not run scans, migrations or
  tests against the live library. Windows is suitable for UI builds; backend
  modules use `fcntl` and tests require Linux plus FFmpeg/ffprobe.
- Documentation-only work needs link/path/consistency checks, not application
  changes or a full functional test run. Record exactly what was validated.
- After significant work update only the relevant context documents: PROJECT
  for architecture/commands, DECISIONS for accepted tradeoffs, PROGRESS for state.
  Keep SESSION updated at handoffs, changes of objective and before ending.
- SESSION is a short current handoff, not an accumulating transcript. Link to
  details rather than duplicating them; keep older milestones in PROGRESS.
- Never mark work complete without evidence. Record check/date/environment,
  failures, unknowns and one concrete next action. Installation, analysis,
  application integration and client validation are separate milestones.

## Context index

- [PROJECT](docs/ai-context/PROJECT.md): architecture, source map and commands.
- [DECISIONS](docs/ai-context/DECISIONS.md): constraints and accepted decisions.
- [PROGRESS](docs/ai-context/PROGRESS.md): completed, pending and uncertain work.
- [SESSION](docs/ai-context/SESSION.md): latest objective, validation and next step.
- README.md / README.pt.md: user installation and behavior; CONTRIBUTING.md and
  SECURITY.md remain applicable. If docs disagree, inspect the specific source
  and record the discrepancy rather than silently assuming either is current.
