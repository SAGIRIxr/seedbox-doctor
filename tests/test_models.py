import unittest
from datetime import datetime, timezone

from seedbox_doctor.models import AuditReport, Finding, Status


class FindingTests(unittest.TestCase):
    def test_rejects_invalid_check_ids(self) -> None:
        with self.assertRaises(ValueError):
            Finding("has spaces", Status.WARN, "Invalid ID")

    def test_rejects_blank_summary(self) -> None:
        with self.assertRaises(ValueError):
            Finding("security.csrf", Status.FAIL, "   ")


class AuditReportTests(unittest.TestCase):
    def test_score_counts_and_worst_status(self) -> None:
        report = AuditReport.from_findings(
            "main",
            [
                Finding("api.reachable", Status.PASS, "API is reachable"),
                Finding("storage.free", Status.WARN, "Disk is getting full"),
                Finding("security.csrf", Status.FAIL, "CSRF protection is off"),
                Finding("host.local", Status.SKIP, "Remote host check skipped"),
            ],
        )

        self.assertEqual(report.score, 72)
        self.assertEqual(report.worst_status, Status.FAIL)
        self.assertEqual(report.counts[Status.WARN], 1)

    def test_generated_at_is_timezone_aware(self) -> None:
        report = AuditReport("main", (), datetime.now(timezone.utc))
        self.assertIsNotNone(report.generated_at.tzinfo)
        self.assertEqual(report.worst_status, Status.SKIP)


if __name__ == "__main__":
    unittest.main()
