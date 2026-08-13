"""Local download-root capacity and accessibility checks."""

from __future__ import annotations

import shutil
from collections.abc import Hashable
from pathlib import Path
from typing import Callable, Iterable, NamedTuple

from seedbox_doctor.models import Finding, Status


class DiskUsage(NamedTuple):
    total: int
    used: int
    free: int


def _gib(value: int) -> float:
    return value / (1024**3)


def _filesystem_identity(path: Path) -> Hashable:
    """Return the operating system's stable device identity for a path."""

    return path.stat().st_dev


def audit_storage(
    roots: Iterable[Path],
    *,
    is_local: bool,
    warn_percent: float = 15.0,
    fail_percent: float = 5.0,
    warn_free_gib: float = 25.0,
    usage_reader: Callable[[Path], DiskUsage] = shutil.disk_usage,
    identity_reader: Callable[[Path], Hashable] = _filesystem_identity,
) -> tuple[Finding, ...]:
    """Inspect configured local download filesystems without writing to them."""

    if not 0 <= fail_percent < warn_percent <= 100:
        raise ValueError("capacity thresholds must satisfy 0 <= fail < warn <= 100")
    if warn_free_gib < 0:
        raise ValueError("warn_free_gib must not be negative")

    paths = tuple(dict.fromkeys(Path(root).expanduser() for root in roots))
    if not is_local:
        return (
            Finding(
                "storage.capacity",
                Status.SKIP,
                "Host storage checks are disabled for this remote profile",
            ),
        )
    if not paths:
        return (
            Finding(
                "storage.capacity",
                Status.SKIP,
                "No local download roots are configured",
            ),
        )

    findings: list[Finding] = []
    seen_filesystems: set[Hashable] = set()
    for index, path in enumerate(paths, start=1):
        check_id = f"storage.root_{index}"
        if not path.exists():
            findings.append(
                Finding(
                    check_id,
                    Status.FAIL,
                    "A configured download root does not exist",
                    remediation="Mount or create the configured root before starting downloads.",
                )
            )
            continue
        if not path.is_dir():
            findings.append(
                Finding(
                    check_id,
                    Status.FAIL,
                    "A configured download root is not a directory",
                    remediation="Point the profile at an existing directory.",
                )
            )
            continue

        try:
            identity = identity_reader(path)
        except OSError as error:
            findings.append(
                Finding(
                    check_id,
                    Status.FAIL,
                    "Download root filesystem could not be identified",
                    evidence=(f"error={type(error).__name__}",),
                    remediation="Restore access to the configured root and rerun the audit.",
                )
            )
            continue
        if identity in seen_filesystems:
            findings.append(
                Finding(
                    check_id,
                    Status.SKIP,
                    "Download root shares a filesystem already checked",
                )
            )
            continue

        try:
            usage = usage_reader(path)
        except OSError as error:
            findings.append(
                Finding(
                    check_id,
                    Status.FAIL,
                    "Download filesystem capacity could not be read",
                    evidence=(f"error={type(error).__name__}",),
                    remediation="Restore the mount or its permissions and rerun the audit.",
                )
            )
            continue
        seen_filesystems.add(identity)

        free_percent = 100.0 if usage.total == 0 else usage.free * 100 / usage.total
        free_gib = _gib(usage.free)
        metadata = {
            "free_percent": round(free_percent, 1),
            "free_gib": round(free_gib, 1),
        }
        evidence = (f"free={free_percent:.1f}% ({free_gib:.1f} GiB)",)
        if free_percent <= fail_percent:
            findings.append(
                Finding(
                    check_id,
                    Status.FAIL,
                    "A download filesystem is critically full",
                    evidence=evidence,
                    remediation="Free space or move data before qBittorrent exhausts the filesystem.",
                    metadata=metadata,
                )
            )
        elif free_percent <= warn_percent or free_gib <= warn_free_gib:
            findings.append(
                Finding(
                    check_id,
                    Status.WARN,
                    "A download filesystem is running low on space",
                    evidence=evidence,
                    remediation="Plan cleanup or additional capacity before the next large download.",
                    metadata=metadata,
                )
            )
        else:
            findings.append(
                Finding(
                    check_id,
                    Status.PASS,
                    "Download filesystem has healthy free capacity",
                    evidence=evidence,
                    metadata=metadata,
                )
            )

    return tuple(findings)

