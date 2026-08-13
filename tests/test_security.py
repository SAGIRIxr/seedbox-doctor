import unittest

from seedbox_doctor.checks.security import audit_webui_security
from seedbox_doctor.models import Status


SAFE_PREFERENCES = {
    "web_ui_csrf_protection_enabled": True,
    "web_ui_host_header_validation_enabled": True,
    "web_ui_clickjacking_protection_enabled": True,
    "bypass_local_auth": False,
    "bypass_auth_subnet_whitelist_enabled": False,
    "web_ui_upnp": False,
    "use_https": True,
    "web_ui_address": "127.0.0.1",
}


class SecurityAuditTests(unittest.TestCase):
    def by_id(self, preferences, url="https://qb.example.test"):
        return {
            finding.check_id: finding
            for finding in audit_webui_security(preferences, url)
        }

    def test_safe_preferences_pass(self) -> None:
        findings = self.by_id(SAFE_PREFERENCES)
        self.assertTrue(all(item.status is Status.PASS for item in findings.values()))

    def test_flags_disabled_browser_protections_and_auth_bypass(self) -> None:
        preferences = {
            **SAFE_PREFERENCES,
            "web_ui_csrf_protection_enabled": False,
            "web_ui_host_header_validation_enabled": False,
            "bypass_auth_subnet_whitelist_enabled": True,
            "web_ui_upnp": True,
        }
        findings = self.by_id(preferences)

        self.assertEqual(findings["security.csrf"].status, Status.FAIL)
        self.assertEqual(findings["security.host_header"].status, Status.FAIL)
        self.assertEqual(findings["security.subnet_auth"].status, Status.FAIL)
        self.assertEqual(findings["security.upnp"].status, Status.FAIL)

    def test_plain_http_is_only_accepted_on_loopback(self) -> None:
        remote = self.by_id(
            {**SAFE_PREFERENCES, "use_https": False}, "http://seedbox.example.test:8080"
        )
        local = self.by_id(
            {**SAFE_PREFERENCES, "use_https": False}, "http://127.0.0.1:8080"
        )

        self.assertEqual(remote["security.transport"].status, Status.FAIL)
        self.assertEqual(local["security.transport"].status, Status.PASS)

    def test_https_preference_does_not_hide_plain_http_connection(self) -> None:
        findings = self.by_id(
            {**SAFE_PREFERENCES, "use_https": True},
            "http://seedbox.example.test:8080",
        )

        transport = findings["security.transport"]
        self.assertEqual(transport.status, Status.FAIL)
        self.assertIn("use_https=true", transport.evidence)

    def test_https_proxy_is_safe_when_qbittorrent_https_is_disabled(self) -> None:
        findings = self.by_id(
            {**SAFE_PREFERENCES, "use_https": False},
            "https://seedbox.example.test",
        )

        self.assertEqual(findings["security.transport"].status, Status.PASS)

    def test_warns_for_all_interface_binding(self) -> None:
        findings = self.by_id({**SAFE_PREFERENCES, "web_ui_address": "0.0.0.0"})
        self.assertEqual(findings["security.listen_address"].status, Status.WARN)

    def test_missing_version_specific_controls_are_skipped(self) -> None:
        findings = self.by_id({}, "http://localhost:8080")
        self.assertEqual(findings["security.csrf"].status, Status.SKIP)
        self.assertEqual(findings["security.transport"].status, Status.PASS)


if __name__ == "__main__":
    unittest.main()
