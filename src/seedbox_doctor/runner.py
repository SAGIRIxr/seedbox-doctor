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
        version = client.app_version()
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

    findings.append(
        Finding(
            "api.connection",
            Status.PASS,
            f"Authenticated to qBittorrent {version}",
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
    tracker_error: QbittorrentError | None = None
    for torrent in torrents:
        torrent_hash = str(torrent.get("hash", ""))
        if not torrent_hash:
            continue
        try:
            tracker_groups.append(client.trackers(torrent_hash))
        except QbittorrentError as error:
            tracker_error = error
            break
    if tracker_error is not None:
        findings.append(_api_failure("api.trackers", "tracker state", tracker_error))
    elif torrents:
        findings.extend(audit_tracker_health(tracker_groups))

    findings.extend(
        audit_storage(
            config.download_roots,
            is_local=config.local,
        )
    )
    findings.extend(audit_media_tools(is_local=config.local))
    client.logout()
    return AuditReport.from_findings(config.name, findings)

