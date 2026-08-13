"""Aggregate qBittorrent tracker health without leaking announce URLs."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from seedbox_doctor.models import Finding, Status


_SPECIAL_TRACKERS = {"** [DHT] **", "** [PeX] **", "** [LSD] **"}
_WORKING = 2
_NOT_CONTACTED = 1
_NOT_WORKING = 4


def audit_tracker_health(
    tracker_groups: Iterable[Iterable[Mapping[str, Any]]],
) -> tuple[Finding, ...]:
    """Return aggregate tracker findings.

    Tracker domains, paths, passkeys, and server messages are deliberately not
    copied into findings, making reports safe to share by default.
    """

    trackers = [
        tracker
        for group in tracker_groups
        for tracker in group
        if str(tracker.get("url", "")) not in _SPECIAL_TRACKERS
        and not str(tracker.get("url", "")).startswith("**")
    ]
    if not trackers:
        return (
            Finding(
                "trackers.inventory",
                Status.SKIP,
                "No regular trackers were reported",
            ),
            Finding(
                "trackers.failures",
                Status.SKIP,
                "Tracker availability cannot be evaluated",
            ),
        )

    statuses = Counter(int(tracker.get("status", 0)) for tracker in trackers)
    findings = [
        Finding(
            "trackers.inventory",
            Status.PASS,
            f"qBittorrent reports {len(trackers)} tracker endpoint(s)",
            metadata={"total": len(trackers)},
        )
    ]

    failed = statuses[_NOT_WORKING]
    working = statuses[_WORKING]
    if failed == 0:
        findings.append(
            Finding(
                "trackers.failures",
                Status.PASS,
                "No trackers report a failed state",
            )
        )
    elif working == 0:
        findings.append(
            Finding(
                "trackers.failures",
                Status.FAIL,
                f"All contacted trackers are failing ({failed} endpoint(s))",
                remediation="Check DNS, proxy/firewall rules, credentials, and tracker announcements.",
                metadata={"failed": failed, "working": working},
            )
        )
    else:
        findings.append(
            Finding(
                "trackers.failures",
                Status.WARN,
                f"{failed} tracker endpoint(s) fail while {working} remain healthy",
                remediation="Review affected tracker messages inside qBittorrent.",
                metadata={"failed": failed, "working": working},
            )
        )

    not_contacted = statuses[_NOT_CONTACTED]
    if not_contacted:
        findings.append(
            Finding(
                "trackers.not_contacted",
                Status.WARN,
                f"{not_contacted} tracker endpoint(s) have not been contacted",
                remediation="Confirm the torrents are started and tracker tiers are enabled.",
                metadata={"count": not_contacted},
            )
        )
    else:
        findings.append(
            Finding(
                "trackers.not_contacted",
                Status.PASS,
                "Every tracker has a contact status",
            )
        )

    return tuple(findings)

