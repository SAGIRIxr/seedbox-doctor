import tempfile
import unittest
from pathlib import Path

from seedbox_doctor.checks.storage import DiskUsage, audit_storage
from seedbox_doctor.models import Status


GIB = 1024**3


class StorageAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def audit(self, free_gib: int, **kwargs):
        return audit_storage(
            [self.root],
            is_local=True,
            usage_reader=lambda _: DiskUsage(100 * GIB, (100 - free_gib) * GIB, free_gib * GIB),
            **kwargs,
        )[0]

    def test_skips_remote_profiles_without_touching_paths(self) -> None:
        finding = audit_storage(
            [Path("/definitely/not/present")], is_local=False
        )[0]
        self.assertEqual(finding.status, Status.SKIP)

    def test_fails_for_missing_local_root(self) -> None:
        finding = audit_storage([self.root / "missing"], is_local=True)[0]
        self.assertEqual(finding.status, Status.FAIL)

    def test_classifies_healthy_low_and_critical_capacity(self) -> None:
        self.assertEqual(self.audit(40).status, Status.PASS)
        self.assertEqual(self.audit(10).status, Status.WARN)
        self.assertEqual(self.audit(4).status, Status.FAIL)

    def test_absolute_free_space_can_trigger_warning(self) -> None:
        finding = self.audit(20, warn_percent=15, warn_free_gib=25)
        self.assertEqual(finding.status, Status.WARN)
        self.assertEqual(finding.metadata["free_gib"], 20.0)

    def test_deduplicates_identical_paths_before_reading_usage(self) -> None:
        findings = audit_storage(
            [self.root, self.root],
            is_local=True,
            usage_reader=lambda _: DiskUsage(100 * GIB, 50 * GIB, 50 * GIB),
        )
        self.assertEqual(len(findings), 1)

    def test_deduplicates_roots_on_the_same_filesystem(self) -> None:
        first = self.root / "first"
        second = self.root / "second"
        first.mkdir()
        second.mkdir()

        findings = audit_storage(
            [first, second],
            is_local=True,
            usage_reader=lambda _: DiskUsage(100 * GIB, 50 * GIB, 50 * GIB),
            identity_reader=lambda _: "device-1",
        )

        self.assertEqual(findings[0].status, Status.PASS)
        self.assertEqual(findings[1].status, Status.SKIP)

    def test_equal_capacity_does_not_merge_different_filesystems(self) -> None:
        first = self.root / "first"
        second = self.root / "second"
        first.mkdir()
        second.mkdir()

        findings = audit_storage(
            [first, second],
            is_local=True,
            usage_reader=lambda _: DiskUsage(100 * GIB, 50 * GIB, 50 * GIB),
            identity_reader=lambda path: path.name,
        )

        self.assertEqual([item.status for item in findings], [Status.PASS, Status.PASS])

    def test_rejects_overlapping_thresholds(self) -> None:
        with self.assertRaises(ValueError):
            audit_storage([], is_local=True, fail_percent=20, warn_percent=10)


if __name__ == "__main__":
    unittest.main()
