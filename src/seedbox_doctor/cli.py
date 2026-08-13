"""Command-line interface for seedbox-doctor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Sequence

from seedbox_doctor import __version__
from seedbox_doctor.config import ConfigError, InstanceConfig, load_profile
from seedbox_doctor.models import AuditReport, Status
from seedbox_doctor.reporters import render_json, render_markdown, render_text
from seedbox_doctor.runner import run_audit


ProfileLoader = Callable[..., InstanceConfig]
AuditRunner = Callable[[InstanceConfig], AuditReport]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seedbox-doctor",
        description="Read-only qBittorrent and seedbox health/security auditor",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="audit one configured instance")
    check.add_argument(
        "--config",
        type=Path,
        default=Path("~/.config/seedbox-doctor/config.ini").expanduser(),
        help="INI configuration path",
    )
    check.add_argument("--profile", default="main", help="profile name (default: main)")
    check.add_argument(
        "--format",
        choices=("text", "json", "markdown"),
        default="text",
        help="report format",
    )
    check.add_argument(
        "--output",
        type=Path,
        help="write report to a file instead of stdout",
    )
    check.add_argument(
        "--fail-on",
        choices=("never", "warn", "fail"),
        default="fail",
        help="choose which outcome produces exit code 1",
    )
    return parser


def _render(report: AuditReport, output_format: str) -> str:
    if output_format == "json":
        return render_json(report)
    if output_format == "markdown":
        return render_markdown(report)
    return render_text(report)


def _exit_code(status: Status, fail_on: str) -> int:
    if fail_on == "never":
        return 0
    if fail_on == "warn" and status in {Status.WARN, Status.FAIL}:
        return 1
    if fail_on == "fail" and status is Status.FAIL:
        return 1
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    loader: ProfileLoader = load_profile,
    runner: AuditRunner = run_audit,
) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "check":
        return 2

    try:
        config = loader(args.config, args.profile)
    except ConfigError as error:
        print(f"seedbox-doctor: configuration error: {error}", file=sys.stderr)
        return 2

    report = runner(config)
    rendered = _render(report, args.format)
    if args.output:
        try:
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as error:
            print(f"seedbox-doctor: cannot write report: {error}", file=sys.stderr)
            return 2
    else:
        print(rendered, end="")
    return _exit_code(report.worst_status, args.fail_on)


if __name__ == "__main__":
    raise SystemExit(main())

