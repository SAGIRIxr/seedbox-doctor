import unittest

from seedbox_doctor.checks.transfer import audit_transfer_health
from seedbox_doctor.models import Status


class TransferHealthTests(unittest.TestCase):
    def by_id(self, info):
        return {
            finding.check_id: finding for finding in audit_transfer_health(info)
        }

    def test_connected_session_passes(self) -> None:
        findings = self.by_id(
            {
                "connection_status": "connected",
                "dht_nodes": 321,
                "up_info_data": 1024,
                "dl_info_data": 2048,
            }
        )
        self.assertEqual(findings["transfer.connection"].status, Status.PASS)
        self.assertEqual(findings["transfer.dht"].metadata["nodes"], 321)
        self.assertEqual(
            findings["transfer.session_totals"].metadata["uploaded_bytes"], 1024
        )

    def test_firewalled_connection_warns(self) -> None:
        finding = self.by_id({"connection_status": "firewalled"})[
            "transfer.connection"
        ]
        self.assertEqual(finding.status, Status.WARN)
        self.assertIn("port", finding.remediation.lower())

    def test_disconnected_session_fails(self) -> None:
        finding = self.by_id({"connection_status": "disconnected"})[
            "transfer.connection"
        ]
        self.assertEqual(finding.status, Status.FAIL)

    def test_missing_fields_are_skipped(self) -> None:
        findings = self.by_id({})
        self.assertEqual(findings["transfer.connection"].status, Status.SKIP)
        self.assertEqual(findings["transfer.dht"].status, Status.SKIP)
        self.assertEqual(findings["transfer.session_totals"].status, Status.SKIP)

    def test_zero_dht_nodes_warns(self) -> None:
        finding = self.by_id({"dht_nodes": 0})["transfer.dht"]
        self.assertEqual(finding.status, Status.WARN)


if __name__ == "__main__":
    unittest.main()
