import unittest

from seedbox_doctor.checks.torrents import audit_torrent_health
from seedbox_doctor.models import Status


class TorrentHealthTests(unittest.TestCase):
    def by_id(self, torrents, **kwargs):
        return {
            finding.check_id: finding
            for finding in audit_torrent_health(torrents, **kwargs)
        }

    def test_empty_instance_is_healthy(self) -> None:
        findings = self.by_id([])
        self.assertEqual(findings["torrents.inventory"].metadata["total"], 0)
        self.assertEqual(findings["torrents.errors"].status, Status.PASS)

    def test_reports_missing_and_error_counts_without_names(self) -> None:
        torrents = [
            {"name": "private-title-one", "state": "missingFiles"},
            {"name": "private-title-two", "state": "error"},
            {"name": "private-title-three", "state": "unknown"},
        ]
        findings = self.by_id(torrents)

        self.assertEqual(findings["torrents.missing_files"].status, Status.FAIL)
        self.assertEqual(findings["torrents.errors"].metadata["count"], 2)
        rendered = repr(tuple(findings.values()))
        self.assertNotIn("private-title", rendered)

    def test_only_flags_stalls_older_than_threshold(self) -> None:
        now = 1_000_000.0
        torrents = [
            {"state": "stalledUP", "last_activity": now - 25 * 3600},
            {"state": "stalledDL", "last_activity": now - 2 * 3600},
            {"state": "uploading", "last_activity": now - 200 * 3600},
        ]
        findings = self.by_id(torrents, now=now, stalled_hours=24)

        self.assertEqual(findings["torrents.stalled"].status, Status.WARN)
        self.assertEqual(findings["torrents.stalled"].metadata["count"], 1)

    def test_rejects_non_positive_threshold(self) -> None:
        with self.assertRaises(ValueError):
            audit_torrent_health([], stalled_hours=0)


if __name__ == "__main__":
    unittest.main()
