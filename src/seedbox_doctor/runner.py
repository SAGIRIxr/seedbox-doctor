"""Orchestrate independent read-only checks for one qBittorrent instance."""

from __future__ import annotations

from typing import Any, Callable

from seedbox_doctor.checks.media import audit_media_tools
from seedbox_doctor.checks.security import audit_webui_security
from seedbox_doctor.checks.storage import audit_storage
from seedbox_doctor.checks.torrents import audit_torrent_health
from seedbox_doctor.checks.trackers import audit_tracker_health
from seedbox_doctor.checks.transfer import audit_transfer_health
from seedbox_doctor.client import QbittorrentClient, QbittorrentError
from seedbox_doctor.config import InstanceConfig
from seedbox_doctor.models import AuditReport, Finding, Status


ClientFactory = Callable[..., QbittorrentClient]


def _api_failure(check_id: str, label: str, error: Exception) -> Finding:
    return Finding(
        check_id,
        Status.FAIL,
        f"Unable to read {label} from qBittorrent",
        evidence=(type(error).__name__,),
        remediation="Check qBittorrent logs, Web API permissions, and version compatibility.",
    )


def _run_authenticated_audit(
    config: InstanceConfig,
    client: QbittorrentClient,
    findings: list[Finding],
    *,
    now: float | None = None,
) -> AuditReport:
    """Run checks that require an already authenticated client."""

    findings.append(
        Finding(
            "api.connection",
            Status.PASS,
            "Authenticated to qBittorrent",
        )
    )

    try:
        version = client.app_version()
    except QbittorrentError as error:
        findings.append(_api_failure("api.version", "application version", error))
    else:
        findings.append(
            Finding(
                "api.version",
                Status.PASS,
                f"qBittorrent reports version {version}",
                metadata={"version": version},
            )
        )

    try:
        preferences = client.preferences()
    except QbittorrentError as error:
        findings.append(_api_failure("api.preferences", "preferences", error))
    else:
        findings.extend(audit_webui_security(preferences, config.url))

    torrents: list[dict[str, Any]] = []
    try:
        torrents = client.torrents()
    except QbittorrentError as error:
        findings.append(_api_failure("api.torrents", "torrent state", error))
    else:
        findings.extend(audit_torrent_health(torrents, now=now))

    try:
        transfer = client.transfer_info()
    except QbittorrentError as error:
        findings.append(_api_failure("api.transfer", "transfer state", error))
    else:
        findings.extend(audit_transfer_health(transfer))

    tracker_groups: list[list[dict[str, Any]]] = []
    tracker_errors: list[QbittorrentError] = []
    tracker_attempts = 0
    for torrent in torrents:
        torrent_hash = str(torrent.get("hash", ""))
        if not torrent_hash:
            continue
        tracker_attempts += 1
        try:
            tracker_groups.append(client.trackers(torrent_hash))
        except QbittorrentError as error:
            tracker_errors.append(error)

    if tracker_attempts:
        tracker_failures = len(tracker_errors)
        tracker_successes = len(tracker_groups)
        metadata = {
            "attempted": tracker_attempts,
            "succeeded": tracker_successes,
            "failed": tracker_failures,
        }
        if tracker_failures == 0:
            findings.append(
                Finding(
                    "api.trackers",
                    Status.PASS,
                    "Tracker data was read for every torrent",
                    metadata=metadata,
                )
            )
        elif tracker_successes == 0:
            findings.append(
                Finding(
                    "api.trackers",
                    Status.FAIL,
                    "Tracker data could not be read for any torrent",
                    evidence=tuple(
                        sorted({type(error).__name__ for error in tracker_errors})
                    ),
                    remediation="Check qBittorrent logs, Web API permissions, and torrent state.",
                    metadata=metadata,
                )
            )
        else:
            findings.append(
                Finding(
                    "api.trackers",
                    Status.WARN,
                    f"Tracker data could not be read for {tracker_failures} of {tracker_attempts} torrents",
                    evidence=tuple(
                        sorted({type(error).__name__ for error in tracker_errors})
                    ),
                    remediation="Retry the audit and inspect recently removed or changed torrents.",
                    metadata=metadata,
                )
            )

    if tracker_groups:
        findings.extend(audit_tracker_health(tracker_groups))

    findings.extend(
        audit_storage(
            config.download_roots,
            is_local=config.local,
        )
    )
    findings.extend(audit_media_tools(is_local=config.local))
    return AuditReport.from_findings(config.name, findings)


def run_audit(
    config: InstanceConfig,
    *,
    client_factory: ClientFactory = QbittorrentClient,
    now: float | None = None,
) -> AuditReport:
    """Run all available checks, isolating optional endpoint failures."""

    findings: list[Finding] = []
    client = client_factory(
        config.url,
        config.username,
        config.password,
        timeout=config.timeout,
    )
    try:
        client.login()
    except QbittorrentError as error:
        findings.append(
            Finding(
                "api.connection",
                Status.FAIL,
                "Unable to establish an authenticated qBittorrent session",
                evidence=(type(error).__name__,),
                remediation="Verify the URL, credentials, Web UI state, and network path.",
            )
        )
        findings.extend(
            audit_storage(
                config.download_roots,
                is_local=config.local,
            )
        )
        findings.extend(audit_media_tools(is_local=config.local))
        return AuditReport.from_findings(config.name, findings)

    try:
        return _run_authenticated_audit(
            config,
            client,
            findings,
            now=now,
        )
    finally:
        client.logout()

