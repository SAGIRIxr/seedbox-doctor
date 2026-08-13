import tempfile
import unittest
from pathlib import Path

from seedbox_doctor.client import TransportError
from seedbox_doctor.config import InstanceConfig
from seedbox_doctor.models import Status
from seedbox_doctor.runner import run_audit


class FakeClient:
    fail_preferences = False
    fail_login = False
    instances = []

    def __init__(self, base_url, username, password, *, timeout):
        self.logged_out = False
        self.logout_calls = 0
        FakeClient.instances.append(self)

    def login(self):
        if self.fail_login:
            raise TransportError("offline")

    def logout(self):
        self.logged_out = True
        self.logout_calls += 1

    def app_version(self):
        return "5.0.4"

    def preferences(self):
        if self.fail_preferences:
            raise TransportError("endpoint unavailable")
        return {
            "web_ui_csrf_protection_enabled": True,
            "web_ui_host_header_validation_enabled": True,
            "web_ui_clickjacking_protection_enabled": True,
            "bypass_local_auth": False,
            "bypass_auth_subnet_whitelist_enabled": False,
            "web_ui_upnp": False,
            "use_https": True,
            "web_ui_address": "127.0.0.1",
        }

    def torrents(self):
        return [{"hash": "abc", "state": "uploading"}]

    def transfer_info(self):
        return {
            "connection_status": "connected",
            "dht_nodes": 100,
            "up_info_data": 10,
            "dl_info_data": 20,
        }

    def trackers(self, torrent_hash):
        return [{"url": "https://tracker.example/announce", "status": 2}]


class RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeClient.instances = []
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config = InstanceConfig(
            name="main",
            url="https://qb.example.test",
            username="admin",
            password="secret",
            local=False,
            download_roots=(Path(directory.name),),
        )

    def by_id(self, report):
        return {finding.check_id: finding for finding in report.findings}

    def test_runs_remote_checks_and_skips_host_storage(self) -> None:
        report = run_audit(self.config, client_factory=FakeClient)
        findings = self.by_id(report)

        self.assertEqual(findings["api.connection"].status, Status.PASS)
        self.assertEqual(findings["security.csrf"].status, Status.PASS)
        self.assertEqual(findings["torrents.errors"].status, Status.PASS)
        self.assertEqual(findings["trackers.failures"].status, Status.PASS)
        self.assertEqual(findings["transfer.connection"].status, Status.PASS)
        self.assertEqual(findings["storage.capacity"].status, Status.SKIP)
        self.assertEqual(findings["media.tools"].status, Status.SKIP)
        self.assertEqual(FakeClient.instances[-1].logout_calls, 1)

    def test_endpoint_failure_does_not_abort_other_checks(self) -> None:
        class PartialClient(FakeClient):
            fail_preferences = True

        report = run_audit(self.config, client_factory=PartialClient)
        findings = self.by_id(report)

        self.assertEqual(findings["api.preferences"].status, Status.FAIL)
        self.assertEqual(findings["torrents.errors"].status, Status.PASS)
        self.assertEqual(findings["transfer.connection"].status, Status.PASS)

    def test_login_failure_returns_report_instead_of_raising(self) -> None:
        class OfflineClient(FakeClient):
            fail_login = True

        report = run_audit(self.config, client_factory=OfflineClient)
        findings = self.by_id(report)
        self.assertEqual(findings["api.connection"].status, Status.FAIL)
        self.assertEqual(findings["storage.capacity"].status, Status.SKIP)
        self.assertEqual(findings["media.tools"].status, Status.SKIP)
        self.assertEqual(len(findings), 3)
        self.assertEqual(FakeClient.instances[-1].logout_calls, 0)

    def test_version_failure_still_logs_out(self) -> None:
        class VersionFailureClient(FakeClient):
            def app_version(self):
                raise TransportError("version endpoint unavailable")

        report = run_audit(self.config, client_factory=VersionFailureClient)

        self.assertEqual(self.by_id(report)["api.connection"].status, Status.FAIL)
        self.assertEqual(FakeClient.instances[-1].logout_calls, 1)

    def test_unexpected_check_error_still_logs_out(self) -> None:
        class BrokenCheckClient(FakeClient):
            def preferences(self):
                raise RuntimeError("unexpected parser bug")

        with self.assertRaisesRegex(RuntimeError, "unexpected parser bug"):
            run_audit(self.config, client_factory=BrokenCheckClient)

        self.assertEqual(FakeClient.instances[-1].logout_calls, 1)

    def test_tracker_failure_keeps_other_torrent_results(self) -> None:
        class PartialTrackerClient(FakeClient):
            requested_hashes = []

            def torrents(self):
                return [
                    {"hash": "private-a", "state": "uploading"},
                    {"hash": "private-b", "state": "uploading"},
                    {"hash": "private-c", "state": "uploading"},
                ]

            def trackers(self, torrent_hash):
                self.requested_hashes.append(torrent_hash)
                if torrent_hash == "private-b":
                    raise TransportError("torrent disappeared: private-b")
                return [{"url": "https://tracker.example/announce", "status": 2}]

        report = run_audit(self.config, client_factory=PartialTrackerClient)
        findings = self.by_id(report)

        self.assertEqual(
            PartialTrackerClient.requested_hashes,
            ["private-a", "private-b", "private-c"],
        )
        self.assertEqual(findings["api.trackers"].status, Status.WARN)
        self.assertEqual(
            findings["api.trackers"].metadata,
            {"attempted": 3, "succeeded": 2, "failed": 1},
        )
        self.assertEqual(findings["trackers.failures"].status, Status.PASS)
        self.assertNotIn("private-b", repr(findings["api.trackers"]))

    def test_all_tracker_failures_are_aggregated_without_hashes(self) -> None:
        class UnavailableTrackerClient(FakeClient):
            requested_hashes = []

            def torrents(self):
                return [
                    {"hash": "private-a", "state": "uploading"},
                    {"hash": "private-b", "state": "uploading"},
                ]

            def trackers(self, torrent_hash):
                self.requested_hashes.append(torrent_hash)
                raise TransportError(f"unavailable: {torrent_hash}")

        report = run_audit(self.config, client_factory=UnavailableTrackerClient)
        findings = self.by_id(report)

        self.assertEqual(
            UnavailableTrackerClient.requested_hashes,
            ["private-a", "private-b"],
        )
        self.assertEqual(findings["api.trackers"].status, Status.FAIL)
        self.assertEqual(
            findings["api.trackers"].metadata,
            {"attempted": 2, "succeeded": 0, "failed": 2},
        )
        self.assertNotIn("trackers.inventory", findings)
        self.assertNotIn("private-a", repr(findings["api.trackers"]))


if __name__ == "__main__":
    unittest.main()
