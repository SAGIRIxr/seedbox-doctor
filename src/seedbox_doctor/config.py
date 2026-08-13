"""INI profile loading with secret-safe environment overrides."""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit


class ConfigError(ValueError):
    """Raised when a profile is missing or unsafe."""


_PROFILE_FIELDS = {
    "url",
    "username",
    "password_env",
    "timeout",
    "local",
    "download_roots",
}


@dataclass(frozen=True, slots=True)
class InstanceConfig:
    """Connection details for one qBittorrent instance."""

    name: str
    url: str
    username: str
    password: str = field(repr=False)
    timeout: float = 10.0
    local: bool = False
    download_roots: tuple[Path, ...] = ()


def _as_bool(value: str, field_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{field_name} must be true or false")


def _validate_url(value: str) -> str:
    raw_url = value.strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in raw_url):
        raise ConfigError("url must not contain control characters")
    url = raw_url.rstrip("/")
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        parsed.port
    except ValueError as error:
        raise ConfigError("url contains an invalid host or port") from error
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not hostname:
        raise ConfigError("url must be an absolute http:// or https:// URL")
    if parsed.username or parsed.password:
        raise ConfigError("credentials must not be embedded in the URL")
    if parsed.query or parsed.fragment:
        raise ConfigError("url must not contain a query string or fragment")
    return url


def load_profile(
    path: str | Path,
    profile: str = "main",
    *,
    environ: Mapping[str, str] | None = None,
    overrides: Mapping[str, str] | None = None,
) -> InstanceConfig:
    """Load one ``[profile.NAME]`` section.

    Values in ``overrides`` take precedence over generic environment variables,
    which take precedence over the INI profile. Passwords are accepted only via
    an environment variable, never as plaintext configuration.
    """

    env = os.environ if environ is None else environ
    supplied = {} if overrides is None else dict(overrides)
    unknown_overrides = set(supplied).difference(_PROFILE_FIELDS | {"password"})
    if unknown_overrides:
        names = ", ".join(sorted(unknown_overrides))
        raise ConfigError(f"unknown override field(s): {names}")
    parser = configparser.ConfigParser(interpolation=None)
    config_path = Path(path).expanduser()
    try:
        loaded = parser.read(config_path, encoding="utf-8")
    except (configparser.Error, UnicodeError) as error:
        raise ConfigError("configuration file could not be parsed") from error
    if not loaded:
        raise ConfigError(f"configuration file not found: {config_path}")

    section_name = f"profile.{profile}"
    if not parser.has_section(section_name):
        raise ConfigError(f"missing [{section_name}] section")
    section = parser[section_name]

    forbidden = {"password", "pass", "token"}.intersection(section.keys())
    if forbidden:
        names = ", ".join(sorted(forbidden))
        raise ConfigError(f"plaintext secret field(s) are forbidden: {names}")
    unknown_fields = set(section.keys()).difference(_PROFILE_FIELDS)
    if unknown_fields:
        names = ", ".join(sorted(unknown_fields))
        raise ConfigError(f"unknown profile field(s): {names}")

    def resolve(key: str, default: str = "") -> str:
        if key in supplied:
            return supplied[key]
        env_key = f"SEEDBOX_DOCTOR_{key.upper()}"
        if env_key in env:
            return env[env_key]
        return section.get(key, default)

    password_env = section.get("password_env", "").strip()
    password = supplied.get("password", "")
    if not password:
        password = env.get("SEEDBOX_DOCTOR_PASSWORD", "")
    if not password and password_env:
        password = env.get(password_env, "")
    if not password:
        raise ConfigError(
            "password is missing; set password_env or SEEDBOX_DOCTOR_PASSWORD"
        )

    try:
        timeout = float(resolve("timeout", "10"))
    except ValueError as error:
        raise ConfigError("timeout must be a number") from error
    if not 0 < timeout <= 300:
        raise ConfigError("timeout must be greater than 0 and at most 300 seconds")

    roots = tuple(
        Path(item.strip()).expanduser()
        for item in resolve("download_roots").split(",")
        if item.strip()
    )
    username = resolve("username", "admin").strip()
    if not username:
        raise ConfigError("username must not be empty")

    return InstanceConfig(
        name=profile,
        url=_validate_url(resolve("url")),
        username=username,
        password=password,
        timeout=timeout,
        local=_as_bool(resolve("local", "false"), "local"),
        download_roots=roots,
    )

