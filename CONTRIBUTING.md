# Contributing

Use English for code, commit messages and technical documentation. Keep user-facing interface strings in both `ui/src/locales/en.json` and `ui/src/locales/pt.json`; avoid deployment-specific domains, IPs, names and passwords.

Run the backend tests and frontend build before submitting a change. Use synthetic fixtures and temporary directories. Never copy a production SQLite database or music library into a test or issue attachment.

Changes affecting imports, replacement, deletion, redistribution, user isolation or upgrades need relevant recovery and regression tests. New integrations should remain optional. Do not add host provisioning, Proxmox or Immich dependencies to the core project.
