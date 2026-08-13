import unittest

from seedbox_doctor.checks.trackers import audit_tracker_health
from seedbox_doctor.models import Status


class TrackerHealthTests(unittest.TestCase):
    def by_id(self, groups):
        return {
            finding.check_id: finding for finding in audit_tracker_health(groups)
        }

    def test_skips_dht_pex_and_lsd_pseudo_trackers(self) -> None:
        findings = self.by_id(
            [[{"url": "** [DHT] **", "status": 2}, {"url": "** [PeX] **", "status": 2}]]
        )
        self.assertEqual(findings["trackers.inventory"].status, Status.SKIP)

    def test_passes_when_regular_trackers_are_healthy(self) -> None:
        findings = self.by_id(
            [[{"url": "https://tracker.example/announce?passkey=secret", "status": 2}]]
        )
        self.assertEqual(findings["trackers.failures"].status, Status.PASS)
        self.assertNotIn("secret", repr(findings))

    def test_warns_for_partial_failure(self) -> None:
        findings = self.by_id(
            [[
                {"url": "https://one.example/announce", "status": 4},
                {"url": "https://two.example/announce", "status": 2},
            ]]
        )
        self.assertEqual(findings["trackers.failures"].status, Status.WARN)
        self.assertEqual(findings["trackers.failures"].metadata["failed"], 1)

    def test_fails_when_every_contacted_tracker_is_down(self) -> None:
        findings = self.by_id(
            [[
                {"url": "udp://one.example:80/announce", "status": 4},
                {"url": "https://two.example/announce", "status": 4},
            ]]
        )
        self.assertEqual(findings["trackers.failures"].status, Status.FAIL)

    def test_warns_for_trackers_not_yet_contacted(self) -> None:
        findings = self.by_id(
            [[{"url": "https://tracker.example/announce", "status": 1}]]
        )
        self.assertEqual(findings["trackers.not_contacted"].status, Status.WARN)


if __name__ == "__main__":
    unittest.main()
