# seedbox-doctor

`seedbox-doctor` is a zero-runtime-dependency, read-only health and security
auditor for qBittorrent and small seedboxes.

The project is being built in public as a set of independently reviewable
features. The first release will provide:

- qBittorrent v4/v5 Web API support
- security, torrent, tracker, and disk checks
- a risk score with actionable remediation
- redacted terminal, JSON, and Markdown reports
- safe defaults: no torrent deletion and no settings mutation

> Status: early development. The CLI will be available with the v0.1.0 release.

## Design principles

1. **Read-only by default and by design.** Audits never mutate qBittorrent.
2. **Zero runtime dependencies.** Python's standard library is enough.
3. **Useful automation output.** Human-readable and machine-readable reports.
4. **Privacy first.** Passwords, cookies, passkeys, and paths are redacted.

## Requirements

- Python 3.10+
- qBittorrent with its Web UI enabled

## License

[MIT](LICENSE)

