"""qBittorrent Web UI security preference checks."""

from __future__ import annotations

import ipaddress
from typing import Any, Mapping
from urllib.parse import urlsplit

from seedbox_doctor.models import Finding, Status


def _boolean_control(
    preferences: Mapping[str, Any],
    *,
    key: str,
    check_id: str,
    label: str,
    safe_value: bool,
    unsafe_status: Status,
    remediation: str,
) -> Finding:
    if key not in preferences:
        return Finding(
            check_id,
            Status.SKIP,
            f"{label} is not reported by this qBittorrent version",
        )
    value = preferences[key]
    if not isinstance(value, bool):
        return Finding(
            check_id,
            unsafe_status,
            f"{label} could not be verified",
            evidence=(f"type={type(value).__name__}",),
            remediation=f"{remediation} Confirm the Web API returns a boolean value.",
        )
    if value is safe_value:
        return Finding(check_id, Status.PASS, f"{label} is configured safely")
    return Finding(
        check_id,
        unsafe_status,
        f"{label} is configured unsafely",
        evidence=(f"{key}={str(value).lower()}",),
        remediation=remediation,
    )


def _is_loopback_url(url: str) -> bool:
    host = urlsplit(url).hostname
    if host is None:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def audit_webui_security(
    preferences: Mapping[str, Any], base_url: str
) -> tuple[Finding, ...]:
    """Audit Web UI controls without changing any preferences."""

    findings = [
        _boolean_control(
            preferences,
            key="web_ui_csrf_protection_enabled",
            check_id="security.csrf",
            label="CSRF protection",
            safe_value=True,
            unsafe_status=Status.FAIL,
            remediation="Enable Web UI CSRF protection in qBittorrent settings.",
        ),
        _boolean_control(
            preferences,
            key="web_ui_host_header_validation_enabled",
            check_id="security.host_header",
            label="Host header validation",
            safe_value=True,
            unsafe_status=Status.FAIL,
            remediation="Enable Web UI host header validation.",
        ),
        _boolean_control(
            preferences,
            key="web_ui_clickjacking_protection_enabled",
            check_id="security.clickjacking",
            label="Clickjacking protection",
            safe_value=True,
            unsafe_status=Status.WARN,
            remediation="Enable Web UI clickjacking protection.",
        ),
        _boolean_control(
            preferences,
            key="bypass_local_auth",
            check_id="security.local_auth",
            label="Local authentication",
            safe_value=False,
            unsafe_status=Status.WARN,
            remediation="Require authentication from localhost unless the host is isolated.",
        ),
        _boolean_control(
            preferences,
            key="bypass_auth_subnet_whitelist_enabled",
            check_id="security.subnet_auth",
            label="Subnet authentication bypass",
            safe_value=False,
            unsafe_status=Status.FAIL,
            remediation="Disable subnet authentication bypass or tightly restrict the subnet list.",
        ),
        _boolean_control(
            preferences,
            key="web_ui_upnp",
            check_id="security.upnp",
            label="Web UI UPnP exposure",
            safe_value=False,
            unsafe_status=Status.FAIL,
            remediation="Disable UPnP for the Web UI and expose it through an authenticated proxy.",
        ),
    ]

    parsed = urlsplit(base_url)
    if parsed.scheme.lower() == "https":
        findings.append(
            Finding("security.transport", Status.PASS, "Web UI transport uses HTTPS")
        )
    elif _is_loopback_url(base_url):
        findings.append(
            Finding(
                "security.transport",
                Status.PASS,
                "Plain HTTP is limited to a loopback address",
            )
        )
    else:
        findings.append(
            Finding(
                "security.transport",
                Status.FAIL,
                "Credentials may cross the network over plain HTTP",
                evidence=(
                    f"scheme={parsed.scheme or 'unknown'}",
                    f"use_https={str(bool(preferences.get('use_https', False))).lower()}",
                ),
                remediation="Use HTTPS directly or access a loopback Web UI through SSH/VPN.",
            )
        )

    listen_address = str(preferences.get("web_ui_address", "")).strip()
    if listen_address in {"*", "0.0.0.0", "::"}:
        findings.append(
            Finding(
                "security.listen_address",
                Status.WARN,
                "Web UI listens on every network interface",
                evidence=(f"web_ui_address={listen_address}",),
                remediation="Bind to loopback or a private management interface when possible.",
            )
        )
    elif listen_address:
        findings.append(
            Finding(
                "security.listen_address",
                Status.PASS,
                "Web UI uses an explicit listen address",
            )
        )
    else:
        findings.append(
            Finding(
                "security.listen_address",
                Status.SKIP,
                "Web UI listen address is not reported",
            )
        )

    return tuple(findings)

