"""Privacy-preserving torrent state checks."""

from __future__ import annotations

import time
from collections import Counter
from typing import Any, Iterable, Mapping

from seedbox_doctor.models import Finding, Status


_MISSING_STATES = {"missingFiles"}
_ERROR_STATES = {"error", "unknown"}
_STALLED_STATES = {"stalledUP", "stalledDL"}


def _age_hours(torrent: Mapping[str, Any], now: float) -> float:
    timestamp = torrent.get("last_activity") or torrent.get("added_on") or now
    try:
        return max(0.0, (now - float(timestamp)) / 3600)
    except (TypeError, ValueError):
        return 0.0


def audit_torrent_health(
    torrents: Iterable[Mapping[str, Any]],
    *,
    now: float | None = None,
    stalled_hours: float = 24.0,
) -> tuple[Finding, ...]:
    """Summarize unhealthy torrents without exposing names or hashes."""

    if stalled_hours <= 0:
        raise ValueError("stalled_hours must be greater than zero")
    current_time = time.time() if now is None else now
    items = list(torrents)
    states = Counter(str(item.get("state", "unknown")) for item in items)

    findings = [
        Finding(
            "torrents.inventory",
            Status.PASS,
            f"qBittorrent reports {len(items)} torrent(s)",
            metadata={"total": len(items)},
        )
    ]

    missing = sum(states[state] for state in _MISSING_STATES)
    if missing:
        findings.append(
            Finding(
                "torrents.missing_files",
                Status.FAIL,
                f"{missing} torrent(s) have missing files",
                remediation="Verify mount availability and run a forced recheck after restoring data.",
                metadata={"count": missing},
            )
        )
    else:
        findings.append(
            Finding(
                "torrents.missing_files",
                Status.PASS,
                "No torrents report missing files",
            )
        )

    errors = sum(states[state] for state in _ERROR_STATES)
    if errors:
        findings.append(
            Finding(
                "torrents.errors",
                Status.FAIL,
                f"{errors} torrent(s) are in an error or unknown state",
                remediation="Inspect qBittorrent logs, permissions, and the affected save paths.",
                metadata={"count": errors},
            )
        )
    else:
        findings.append(
            Finding("torrents.errors", Status.PASS, "No torrent state errors detected")
        )

    long_stalled = [
        item
        for item in items
        if str(item.get("state")) in _STALLED_STATES
        and _age_hours(item, current_time) >= stalled_hours
    ]
    if long_stalled:
        findings.append(
            Finding(
                "torrents.stalled",
                Status.WARN,
                f"{len(long_stalled)} torrent(s) have been stalled for at least {stalled_hours:g}h",
                remediation="Check peer availability, tracker status, queue limits, and connectivity.",
                metadata={"count": len(long_stalled), "threshold_hours": stalled_hours},
            )
        )
    else:
        findings.append(
            Finding(
                "torrents.stalled",
                Status.PASS,
                f"No torrents exceed the {stalled_hours:g}h stalled threshold",
            )
        )

    return tuple(findings)

