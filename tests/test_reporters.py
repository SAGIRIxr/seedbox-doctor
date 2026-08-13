import json
import unittest
from datetime import datetime, timezone

from seedbox_doctor.models import AuditReport, Finding, Status
from seedbox_doctor.reporters import render_json, render_markdown, render_text


class ReporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report = AuditReport(
            instance="main|seedbox",
            generated_at=datetime(2026, 8, 13, 2, 30, tzinfo=timezone.utc),
            findings=(
                Finding("api.connection", Status.PASS, "API reachable"),
                Finding(
                    "storage.capacity",
                    Status.WARN,
                    "Disk is low | cleanup soon",
                    evidence=("free=9.0% (18.0 GiB)",),
                    remediation="Free at least 25 GiB.\nThen rerun the audit.",
                    metadata={"free_gib": 18.0},
                ),
                Finding("host.systemd", Status.SKIP, "Remote check skipped"),
            ),
        )

    def test_json_has_stable_schema_and_types(self) -> None:
        payload = json.loads(render_json(self.report))
        self.assertEqual(payload["schema_version"], "1")
        self.assertEqual(payload["score"], 92)
        self.assertEqual(payload["status"], "warn")
        self.assertEqual(payload["counts"]["skip"], 1)
        self.assertEqual(payload["findings"][1]["metadata"]["free_gib"], 18.0)

    def test_text_includes_evidence_and_fix(self) -> None:
        output = render_text(self.report)
        self.assertIn("Score: 92/100", output)
        self.assertIn("WARN  storage.capacity", output)
        self.assertIn("evidence: free=9.0%", output)
        self.assertIn("fix: Free at least 25 GiB", output)

    def test_markdown_escapes_tables_and_flattens_lines(self) -> None:
        output = render_markdown(self.report)
        self.assertIn("main\\|seedbox", output)
        self.assertIn("Disk is low \\| cleanup soon", output)
        self.assertIn("Free at least 25 GiB. Then rerun", output)
        self.assertNotIn("tracker.example", output)


if __name__ == "__main__":
    unittest.main()
