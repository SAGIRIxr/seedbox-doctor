# seedbox-doctor

One command. No writes. A report you can safely share.

`seedbox-doctor` is a zero-runtime-dependency, read-only health and security
auditor for qBittorrent 4.x/5.x and small seedboxes.

The project is being built in public as a set of independently reviewable
features. The first release will provide:

- qBittorrent v4/v5 Web API support
- security, torrent, tracker, and disk checks
- a risk score with actionable remediation
- redacted terminal, JSON, and Markdown reports
- safe defaults: no torrent deletion and no settings mutation

```text
PASS  api.connection                Authenticated to qBittorrent 5.0.4
WARN  storage.root_1                A download filesystem is running low on space
FAIL  torrents.missing_files        3 torrents have missing files
WARN  security.listen_address       Web UI listens on every network interface
```

## Quick start

Install from GitHub with Python 3.10 or newer:

```bash
python -m pip install git+https://github.com/SAGIRIxr/seedbox-doctor.git
```

Copy the [example configuration](examples/config.ini), then provide the password
through the environment instead of putting it in a file:

```bash
export QB_MAIN_PASSWORD='your-password'
seedbox-doctor check --config ./config.ini --profile main
```

Windows PowerShell:

```powershell
$env:QB_MAIN_PASSWORD = 'your-password'
seedbox-doctor check --config .\config.ini --profile main
```

Generate a machine-readable or support-friendly report:

```bash
seedbox-doctor check --config ./config.ini --format json --output report.json
seedbox-doctor check --config ./config.ini --format markdown --output report.md
```

Exit policy defaults to non-zero only on failed checks. Use `--fail-on warn` for
strict automation, or `--fail-on never` when collecting diagnostics.

## Checks

- authenticated qBittorrent Web API connection and version
- CSRF, Host header, clickjacking, auth bypass, UPnP, HTTPS, and listen address
- missing-file, error, unknown, and long-stalled torrent states
- tracker outages without exposing announce URLs or passkeys
- connection state, DHT bootstrap, and transfer counters
- local filesystem existence and free capacity
- local FFmpeg and FFprobe availability/version

## Design principles

1. **Read-only by default and by design.** Audits never mutate qBittorrent.
2. **Zero runtime dependencies.** Python's standard library is enough.
3. **Useful automation output.** Human-readable and machine-readable reports.
4. **Privacy first.** Passwords, cookies, passkeys, and paths are redacted.

## Privacy and safety

The auditor calls read-only Web API endpoints. It never pauses or deletes a
torrent and never changes qBittorrent preferences. Default reports omit torrent
names, hashes, tracker URLs, passkeys, usernames, cookies, and passwords.

## Requirements

- Python 3.10+
- qBittorrent with its Web UI enabled

## License

[MIT](LICENSE)
