# Cadence

[English](README.md) · [Português](README.pt.md)

A self-hosted music discovery and library companion: teach your taste, review daily suggestions, manage playlists and follow approved downloads into Emby and Symfonium.

**Early alpha.** Extracted from a personal installation; this is the first portable distribution, not an audited stable release. English and Portuguese interface catalogues are included. Some provider messages and backend activity records currently remain in Portuguese.

## Scope

Cadence, its background workers, Emby and slskd. No Immich, photo management, Proxmox, CT creation, host provisioning, Cloudflare account configuration or mandatory VPN. You choose your host, storage and remote-access arrangement. Emby, Soulseek and Symfonium are separate products with their own terms and licenses.

## Install

Requires Docker Engine, Docker Compose v2, Git and a POSIX shell. Linux containers are required; Docker Desktop users need a compatible Linux container environment. The installer does not install Docker or change your host firewall.

```sh
git clone https://github.com/stevengdc/cadence.git
cd cadence
sh install.sh
```

Or as one command:

```sh
git clone https://github.com/stevengdc/cadence.git && cd cadence && sh install.sh
```

The first run builds the frontend and backend. Open `http://localhost:8787`. Username defaults to `admin`; read the generated password from `.secrets/admin-password`. No shared default password is shipped. Edit `.env` before starting if you want other ports, a LAN bind address, timezone or public service links. UI defaults to English; select Português at sign-in or in the top bar.

### Connect integrations

1. Open Emby at `http://localhost:8096`, complete its setup and add a **Music** library pointing to `/media/music`. Enable its music metadata and artwork providers as desired.
2. Create an API key in Emby. Configure Cadence interactively (the key is entered without echo):

   ```sh
   docker compose run --rm cadence python configure.py
   ```

3. Enter the internal Emby URL, API key and account to associate. Optionally enter Soulseek credentials, then restart slskd:

   ```sh
   docker compose restart slskd
   ```

4. Rate suggestions and create playlists. Downloads are initially **paused**; resume them explicitly in Cadence after checking your integrations. Do not run a library remaster until you have a recoverable backup.

For Symfonium, add your Emby address and Emby account. Use an address reachable from your phone, not the Docker service name. Remote access, TLS, VPNs and port forwarding belong to your environment. Web ports bind to localhost by default. The Soulseek peer port is separately published for peer connectivity; review it for your network.

## Storage and recovery

`data/` holds state, music, downloads, service configurations and local backups; `.secrets/` holds the first administrator password. Neither is tracked. Music mounts read-only in Emby and redistribution mounts read-only in slskd. Sharing is disabled unless an administrator explicitly authorizes eligible files. Only share material you have permission to redistribute.

Local SQLite backups do **not** back up your music or provide an off-host backup. Back up `data/` and `.secrets/` to a separate destination appropriate for your environment. Never use `docker compose down -v` as a backup strategy.

## Manage

```sh
docker compose ps
docker compose logs --tail=100 cadence worker
docker compose stop
docker compose up -d
```

Update by reading the release notes, backing up first, then pulling the selected release and rebuilding. Updating images and persistent database migrations needs validation before a stable release.

## Development

- `backend/`: Python API, accounts, catalogue discovery, acquisition, loudness, playlists and workers.
- `ui/`: React + Chakra UI, `locales/en.json` and `locales/pt.json`.
- `compose.yml`: standalone containers; no Docker socket mounted into Cadence.
- `install.sh`: repeatable local installation; existing data and credentials are preserved.

```sh
pip install -r requirements.txt
cd backend
python -m unittest discover -q
```

Roadmap: complete backend localization, browser-based integration onboarding, configurable chart providers, pinned release images, upgrade/restore tests and a documented release policy. No external AI API is required by this version.

## Security and contribution

See [SECURITY.md](SECURITY.md). Do not include personal databases, music, tokens, passwords, provider responses or screenshots containing user information in issues or pull requests. Submit small changes with relevant tests. Cadence is licensed under the [MIT License](LICENSE). Third-party dependencies and services retain their own licenses.

Initial validation: 99 backend tests passed inside the built container; a clean Compose deployment started successfully and fresh administrator sign-in returned HTTP 200. Provider account onboarding still requires manual credentials.
