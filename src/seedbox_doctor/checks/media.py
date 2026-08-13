"""Local FFmpeg and FFprobe readiness checks."""

from __future__ import annotations

import shutil
import subprocess
from typing import Callable, Protocol, Sequence

from seedbox_doctor.models import Finding, Status


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


Resolver = Callable[[str], str | None]
CommandRunner = Callable[..., CommandResult]


def _check_command(
    name: str,
    *,
    resolver: Resolver,
    command_runner: CommandRunner,
) -> Finding:
    executable = resolver(name)
    check_id = f"media.{name}"
    if not executable:
        return Finding(
            check_id,
            Status.WARN,
            f"{name} is not available on PATH",
            remediation=f"Install {name} or expose it on the service user's PATH.",
        )

    try:
        result = command_runner(
            [executable, "-hide_banner", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return Finding(
            check_id,
            Status.WARN,
            f"{name} was found but could not be executed",
            evidence=(type(error).__name__,),
            remediation=f"Verify permissions and run `{name} -version` as the service user.",
        )

    output = (result.stdout or result.stderr).strip().splitlines()
    first_line = output[0] if output else "no version output"
    if result.returncode != 0:
        return Finding(
            check_id,
            Status.WARN,
            f"{name} returned a non-zero status",
            evidence=(f"exit_code={result.returncode}", first_line),
            remediation=f"Run `{name} -version` manually and repair the installation.",
        )
    return Finding(
        check_id,
        Status.PASS,
        f"{name} is ready",
        evidence=(first_line,),
    )


def audit_media_tools(
    *,
    is_local: bool,
    resolver: Resolver = shutil.which,
    command_runner: CommandRunner = subprocess.run,
    commands: Sequence[str] = ("ffmpeg", "ffprobe"),
) -> tuple[Finding, ...]:
    """Check media tools only when the profile represents the local host."""

    if not is_local:
        return (
            Finding(
                "media.tools",
                Status.SKIP,
                "Media-tool checks are disabled for this remote profile",
            ),
        )
    return tuple(
        _check_command(name, resolver=resolver, command_runner=command_runner)
        for name in commands
    )

