import subprocess
import unittest
from types import SimpleNamespace

from seedbox_doctor.checks.media import audit_media_tools
from seedbox_doctor.models import Status


class MediaReadinessTests(unittest.TestCase):
    def test_remote_profile_is_skipped_without_resolving_commands(self) -> None:
        def unexpected_resolver(name):
            self.fail("resolver must not run for remote profiles")

        finding = audit_media_tools(
            is_local=False, resolver=unexpected_resolver
        )[0]
        self.assertEqual(finding.status, Status.SKIP)

    def test_missing_binaries_warn(self) -> None:
        findings = audit_media_tools(is_local=True, resolver=lambda _: None)
        self.assertEqual([item.status for item in findings], [Status.WARN, Status.WARN])

    def test_reports_versions_when_binaries_execute(self) -> None:
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            name = command[0].split("/")[-1]
            return SimpleNamespace(returncode=0, stdout=f"{name} version 7.1\n", stderr="")

        findings = audit_media_tools(
            is_local=True,
            resolver=lambda name: f"/usr/bin/{name}",
            command_runner=runner,
        )

        self.assertEqual([item.status for item in findings], [Status.PASS, Status.PASS])
        self.assertEqual(calls[0][0], ["/usr/bin/ffmpeg", "-hide_banner", "-version"])
        self.assertEqual(calls[0][1]["timeout"], 5)

    def test_timeout_is_converted_to_warning(self) -> None:
        def runner(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])

        finding = audit_media_tools(
            is_local=True,
            resolver=lambda name: f"/usr/bin/{name}",
            command_runner=runner,
            commands=("ffmpeg",),
        )[0]
        self.assertEqual(finding.status, Status.WARN)
        self.assertEqual(finding.evidence, ("TimeoutExpired",))


if __name__ == "__main__":
    unittest.main()
