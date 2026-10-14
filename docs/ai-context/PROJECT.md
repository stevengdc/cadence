# Project map

Verified from this working tree on 2026-10-14. Runtime history is in PROGRESS;
it is not a fresh deployment audit. All repository paths below are root-relative.

## Purpose and stack

Cadence learns each account's taste from Love/Like/Dislike and deferred choices,
proposes daily music, manages acquisition approvals and downloaded files, and
creates playlists served by Emby. Symfonium is the current Android player.
Recommendations in Cadence currently use rules and metadata, not audio embeddings.

| Layer | Implementation |
| --- | --- |
| API/state | Python 3.12; `http.server.ThreadingHTTPServer`; SQLite `profile.sqlite` |
| UI | React 19 / Chakra UI 3 / Emotion / lucide-react / Vite 7 |
| Python packages | `requirements.txt`: beautifulsoup4 4.14.3, mutagen 1.47.0 |
| Audio | FFmpeg/ffprobe; quality validation, MP3 conversion, loudness/ReplayGain |
| Providers | Emby API; slskd/Soulseek API; Deezer catalog/previews; chart scraping |
| Distribution | Docker multi-stage Node 22 -> Python 3.12; Compose v2; Linux |
| External experiment | AudioMuse-AI, deployed separately; not in core Compose |

## Source and dependency map

- `backend/app.py`: HTTP routes, state initialization, import/scan, previews.
  `ROOT` uses `MC_STATE` (default `/var/lib/media-center`); `MEDIA` uses
  `MC_MEDIA` (default `/data/media/music`). Module CLI calls initialize state.
- `accounts.py`: authentication, administrator/member roles, account context,
  personal ratings/settings/deferrals and playlist ownership.
- `catalog_previews.py`, `discovery.py`, `daily.py`: identity matching, catalog
  relations, tops and proposals. `accounts` overlays personal decisions.
- `playlists.py`: Emby connection, playable item resolution, playlist CRUD and
  reconciliation of pending additions. `radio.py` uses accounts + playlists to
  publish a finite metadata-selected radio. `onboarding.py` stores guide steps.
- `acquisition.py`: approved queue, independent search, retry, validation,
  publication and indexing. `review.py` handles human identity confirmation;
  `remaster.py` handles recoverable FLAC -> MP3 320 replacements;
  `loudness.py` measures/prepares/tags audio.
- `library.py`: inventory/cache, file confinement, playlist membership and
  recoverable removal/trash. `redistribution.py`: signature-bound file sharing.
- `genres.py`: fills empty styles from Emby, then verified Deezer album identity;
  throttles failed/unavailable lookups and preserves existing values.
- `operations.py`: tasks, activity, services and schedule defaults.
  `worker.py`: independent scheduled subprocesses; search invokes acquisition
  with `--search-only`. `backup.py` invokes `backups.py` for verified archives.
- `bootstrap.py` / `configure.py`: persistent installation setup and private
  provider connections. Browser onboarding does not replace configure.py.
- `ui/src/main.jsx`: application sections, library grid/bulk playlists and
  downloads. `setup.jsx`, `backups.jsx` own those forms. `i18n.js` loads EN/PT.
- `backend/test_*.py`: unittest tests using temporary fixtures and mocked
  providers. `ui/` has a build script but no automated browser-test script.
- `compose.yml`, `Dockerfile`, `install.sh`: portable deployment;
  `.github/workflows/validate.yml`: backend tests and frontend build.

Flow: catalog/tops -> personal decisions -> approved acquisition -> quality and
identity checks -> verified library publication -> Emby indexing/playlists ->
mobile playback. Radio consumes existing library data; it does not approve new
downloads. SQLite owns Cadence state; Emby owns actual playlist entries.

## Commands

From repository root, in a Linux environment with Python 3.12 and FFmpeg/ffprobe:

```sh
python -m pip install -r requirements.txt
cd backend
python -m unittest discover -q
# Example focused checks:
python -m unittest test_review test_genres -q
```

From `ui/` with Node 22:

```sh
npm ci
npm run build
```

Portable installation/management, from root (these mutate local deployment):

```sh
sh install.sh
docker compose ps
docker compose logs --tail=100 cadence worker
docker compose run --rm cadence python configure.py
docker compose up -d --build
```

Server entrypoint: `python app.py --serve` from `backend/`; port 8787, `/health`.
Use isolated `MC_STATE`/`MC_MEDIA` and correct built web assets for manual runs;
prefer Compose for a complete environment. `app.py --scan`, `--import-csv` and
`--samples` mutate state/media; they are not read-only diagnostics.

## Deployment boundary

Compose persists `data/` and `.secrets/`, ignored by Git. Emby sees music read-only
at `/media/music`; Cadence sees `/data/media/music`. Web ports bind to loopback
by default; TLS/network access are environment responsibilities.

Historical live installation: native Cadence under `/opt/media-center`, systemd
`media-center.service` plus workers/timers, private state under
`/var/lib/media-center`; Emby/slskd in Docker. AudioMuse uses its own private
Compose/state. Access via the operator's configured SSH environment, never
embedded credentials. Local and live files differ (e.g. acquisition timezone
handling); reconcile deliberately before deployment. No host provisioning.

Existing README validation numbers describe earlier snapshots. README's statement
that AudioMuse is not implemented remains true for Cadence's code integration,
but does not describe the separately installed runtime experiment.
