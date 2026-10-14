# Current handoff — 2026-10-14

## Objective and outcome

Prepare compact, repository-local Codex continuity documentation without changing
application logic. Reviewed existing instructions, READMEs, contribution/security
rules, source entrypoints/modules, dependencies, Compose/installer, CI and Git
state. Created `AGENTS.md` and the four documents in `docs/ai-context/`.

Follow-up: the user requested publication to GitHub. Publication scope is these
five documentation files only. `origin/main` was fetched and matched local HEAD
before staging; pre-existing functional changes remain outside this publication.

The Git root is `cadence/` inside a ChatGPT project mirror. The parent AGENTS.md
is protected and was preserved; synced `sources/` and attachments were untouched.
Technical docs follow CONTRIBUTING.md's English convention.

## Files and validation

- New: `AGENTS.md`, `docs/ai-context/PROJECT.md`, `DECISIONS.md`, `PROGRESS.md`,
  `SESSION.md`. No functional files intentionally changed in this session.
- Checks: all relative Markdown links resolve; source/command references were
  reviewed against the working tree and CI. Before/after SHA-256 comparison
  confirmed 61 pre-existing source/config/documentation files unchanged. The
  parent AGENTS.md was also preserved. New documentation has no trailing spaces.
- Whole-tree `git diff --check` reports pre-existing trailing whitespace at
  `ui/src/main.jsx:144`; left untouched because functional files are out of scope.
  Git also reports existing CRLF/LF normalization notices. Neither is a new
  documentation failure; do not infer application test results from these checks.
- No backend suite, frontend rebuild, live deployment or remote audit was required
  for this documentation-only change. Historical tests are listed in PROGRESS.

## Resume context

Before this documentation task, the latest discussion concerned good iPhone music
clients. Embeat was proposed for testing with existing Emby; Navidrome + Subsonic
clients was an alternative. No iPhone test or architecture switch was authorized
as a selected implementation. AudioMuse was separately installed and its initial
test passed, but final full-library analysis remains unverified; Cadence radio
still selects by metadata. Details and other pending work: PROGRESS.md.

## Constraints / remaining work

- Existing functional changes span backend, UI, installer and deployment files;
  their commit/push has not been confirmed. Do not reset or treat them as this session's
  changes. Compare the working tree with HEAD before packaging or committing.
- Live runtime history is dated evidence, not today's state. Native/systemd and
  Compose parity, final audio migration, off-host recovery and sonic integration
  remain unresolved. No functional work was attempted to close those gaps here.
- Parent mirror references can be replaced by project synchronization; keep the
  Git repository and these new docs in version control for durable continuity.

## Recommended next action

For a new functional task, read AGENTS + this handoff + PROGRESS, inspect Git
status, and identify the user's chosen objective. If continuing sonic work,
perform a read-only AudioMuse health/full-task/index audit before implementing
an optional API adapter. If continuing iPhone work, validate the chosen client
against Emby before changing server architecture. Check DECISIONS first.

Replace this handoff at the next transition with objective, actual changes,
validation, unresolved issues and one concrete next action; avoid a transcript.
