import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from seedbox_doctor.cli import main
from seedbox_doctor.config import ConfigError, InstanceConfig
from seedbox_doctor.models import AuditReport, Finding, Status


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = InstanceConfig(
            "main", "http://localhost:8080", "admin", "secret"
        )

    def loader(self, path, profile):
        self.assertEqual(profile, "main")
        return self.config

    def report(self, status=Status.PASS):
        return AuditReport(
            "main",
            (Finding("api.connection", status, "Connection checked"),),
            datetime(2026, 8, 13, 3, 0, tzinfo=timezone.utc),
        )

    def test_prints_json_report(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(
                ["check", "--format", "json"],
                loader=self.loader,
                runner=lambda _: self.report(),
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["instance"], "main")

    def test_writes_report_to_explicit_file(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        output = Path(directory.name) / "report.md"
        code = main(
            ["check", "--format", "markdown", "--output", str(output)],
            loader=self.loader,
            runner=lambda _: self.report(),
        )
        self.assertEqual(code, 0)
        self.assertIn("# seedbox-doctor report", output.read_text(encoding="utf-8"))

    def test_fail_on_policy_controls_exit_code(self) -> None:
        for policy, status, expected in [
            ("never", Status.FAIL, 0),
            ("warn", Status.WARN, 1),
            ("fail", Status.WARN, 0),
            ("fail", Status.FAIL, 1),
        ]:
            with self.subTest(policy=policy, status=status):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = main(
                        ["check", "--fail-on", policy],
                        loader=self.loader,
                        runner=lambda _, value=status: self.report(value),
                    )
                self.assertEqual(code, expected)

    def test_configuration_errors_return_usage_exit_code(self) -> None:
        def broken_loader(path, profile):
            raise ConfigError("missing password")

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(["check"], loader=broken_loader)
        self.assertEqual(code, 2)
        self.assertIn("configuration error", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
