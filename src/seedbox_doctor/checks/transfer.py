"""qBittorrent connectivity and session-statistics checks."""

from __future__ import annotations

from typing import Any, Mapping

from seedbox_doctor.models import Finding, Status


def _integer(info: Mapping[str, Any], key: str) -> int | None:
    value = info.get(key)
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def audit_transfer_health(
    info: Mapping[str, Any],
    *,
    dht_enabled: bool | None = None,
) -> tuple[Finding, ...]:
    """Evaluate connection state and aggregate session counters."""

    findings: list[Finding] = []
    connection = str(info.get("connection_status", "")).lower()
    if connection == "connected":
        findings.append(
            Finding("transfer.connection", Status.PASS, "qBittorrent is connected")
        )
    elif connection == "firewalled":
        findings.append(
            Finding(
                "transfer.connection",
                Status.WARN,
                "qBittorrent reports a firewalled connection",
                remediation="Verify the listening port, VPN forwarding, and firewall rules.",
            )
        )
    elif connection == "disconnected":
        findings.append(
            Finding(
                "transfer.connection",
                Status.FAIL,
                "qBittorrent is disconnected",
                remediation="Check the network interface, VPN health, proxy, and application logs.",
            )
        )
    else:
        findings.append(
            Finding(
                "transfer.connection",
                Status.SKIP,
                "qBittorrent did not report a recognized connection state",
            )
        )

    dht_nodes = _integer(info, "dht_nodes")
    if dht_enabled is False:
        findings.append(
            Finding(
                "transfer.dht",
                Status.SKIP,
                "DHT is disabled in qBittorrent preferences",
            )
        )
    elif dht_nodes is None:
        findings.append(
            Finding("transfer.dht", Status.SKIP, "DHT node count is not reported")
        )
    elif dht_nodes == 0:
        summary = (
            "DHT is enabled but has no known nodes"
            if dht_enabled is True
            else "DHT reports no known nodes"
        )
        findings.append(
            Finding(
                "transfer.dht",
                Status.WARN,
                summary,
                remediation="Wait for bootstrap or check UDP reachability; private trackers may disable DHT.",
                metadata={"nodes": 0},
            )
        )
    else:
        findings.append(
            Finding(
                "transfer.dht",
                Status.PASS,
                f"DHT is connected to {dht_nodes} node(s)",
                metadata={"nodes": dht_nodes},
            )
        )

    uploaded = _integer(info, "up_info_data")
    downloaded = _integer(info, "dl_info_data")
    if uploaded is None or downloaded is None:
        findings.append(
            Finding(
                "transfer.session_totals",
                Status.SKIP,
                "Session transfer totals are incomplete",
            )
        )
    else:
        findings.append(
            Finding(
                "transfer.session_totals",
                Status.PASS,
                "Session transfer counters are available",
                metadata={"uploaded_bytes": uploaded, "downloaded_bytes": downloaded},
            )
        )

    return tuple(findings)

