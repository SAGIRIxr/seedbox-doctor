"""Shared data structures for checks and reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping


class Status(str, Enum):
    """Outcome of an individual audit check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


_STATUS_RANK = {
    Status.SKIP: 0,
    Status.PASS: 1,
    Status.WARN: 2,
    Status.FAIL: 3,
}

_SCORE_PENALTY = {
    Status.SKIP: 0,
    Status.PASS: 0,
    Status.WARN: 8,
    Status.FAIL: 20,
}


@dataclass(frozen=True, slots=True)
class Finding:
    """One actionable result produced by an audit check."""

    check_id: str
    status: Status
    summary: str
    evidence: tuple[str, ...] = ()
    remediation: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.check_id or any(char.isspace() for char in self.check_id):
            raise ValueError("check_id must be a non-empty, whitespace-free string")
        if not self.summary.strip():
            raise ValueError("summary must not be empty")


@dataclass(frozen=True, slots=True)
class AuditReport:
    """An immutable collection of findings for one qBittorrent instance."""

    instance: str
    findings: tuple[Finding, ...]
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    schema_version: str = "1"

    @classmethod
    def from_findings(
        cls, instance: str, findings: Iterable[Finding]
    ) -> "AuditReport":
        return cls(instance=instance, findings=tuple(findings))

    @property
    def score(self) -> int:
        """Return a conservative 0-100 health score."""

        penalty = sum(_SCORE_PENALTY[finding.status] for finding in self.findings)
        return max(0, 100 - penalty)

    @property
    def worst_status(self) -> Status:
        if not self.findings:
            return Status.SKIP
        return max(self.findings, key=lambda item: _STATUS_RANK[item.status]).status

    @property
    def counts(self) -> dict[Status, int]:
        counts = {status: 0 for status in Status}
        for finding in self.findings:
            counts[finding.status] += 1
        return counts

