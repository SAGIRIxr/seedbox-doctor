"""Small read-only qBittorrent Web API client built on ``urllib``."""

from __future__ import annotations

import json
from http.cookiejar import CookieJar
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


class QbittorrentError(RuntimeError):
    """Base error for API communication failures."""


class AuthenticationError(QbittorrentError):
    """Raised when qBittorrent rejects credentials."""


class TransportError(QbittorrentError):
    """Raised when the Web API cannot be reached."""


class ProtocolError(QbittorrentError):
    """Raised for malformed or unexpected API responses."""


class _Response(Protocol):
    def __enter__(self) -> "_Response": ...

    def __exit__(self, *args: object) -> None: ...

    def read(self) -> bytes: ...


class _Opener(Protocol):
    def open(self, request: Request, timeout: float) -> _Response: ...


class QbittorrentClient:
    """Authenticated client exposing only read operations used by the auditor."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: float = 10.0,
        opener: _Opener | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self._password = password
        self.timeout = timeout
        self._opener: _Opener = opener or build_opener(
            HTTPCookieProcessor(CookieJar())
        )
        self._authenticated = False

    def __enter__(self) -> "QbittorrentClient":
        self.login()
        return self

    def __exit__(self, *args: object) -> None:
        self.logout()

    def _request(
        self,
        path: str,
        *,
        data: Mapping[str, str] | None = None,
    ) -> bytes:
        if not path.startswith("/api/v2/"):
            raise ValueError("qBittorrent API path must begin with /api/v2/")
        encoded = None if data is None else urlencode(data).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=encoded,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": f"{self.base_url}/",
                "User-Agent": "seedbox-doctor/0.1",
            },
            method="POST" if encoded is not None else "GET",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as error:
            if error.code in {401, 403}:
                raise AuthenticationError(
                    f"qBittorrent rejected the request (HTTP {error.code})"
                ) from error
            raise TransportError(
                f"qBittorrent returned HTTP {error.code}"
            ) from error
        except URLError as error:
            reason = getattr(error, "reason", "connection failed")
            raise TransportError(f"cannot reach qBittorrent: {reason}") from error
        except TimeoutError as error:
            raise TransportError("qBittorrent request timed out") from error

    def login(self) -> None:
        body = self._request(
            "/api/v2/auth/login",
            data={"username": self.username, "password": self._password},
        )
        if body.strip() != b"Ok.":
            raise AuthenticationError("qBittorrent rejected the supplied credentials")
        self._authenticated = True

    def logout(self) -> None:
        if not self._authenticated:
            return
        try:
            self._request("/api/v2/auth/logout", data={})
        except QbittorrentError:
            pass
        finally:
            self._authenticated = False

    def _json(self, path: str) -> Any:
        if not self._authenticated:
            raise AuthenticationError("login must be called before reading the API")
        body = self._request(path)
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProtocolError(f"invalid JSON returned by {path}") from error

    def app_version(self) -> str:
        if not self._authenticated:
            raise AuthenticationError("login must be called before reading the API")
        return self._request("/api/v2/app/version").decode("utf-8").strip()

    def preferences(self) -> dict[str, Any]:
        value = self._json("/api/v2/app/preferences")
        if not isinstance(value, dict):
            raise ProtocolError("preferences response is not an object")
        return value

    def torrents(self) -> list[dict[str, Any]]:
        value = self._json("/api/v2/torrents/info")
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise ProtocolError("torrent response is not a list of objects")
        return value

    def trackers(self, torrent_hash: str) -> list[dict[str, Any]]:
        value = self._json(
            f"/api/v2/torrents/trackers?{urlencode({'hash': torrent_hash})}"
        )
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise ProtocolError("tracker response is not a list of objects")
        return value

    def transfer_info(self) -> dict[str, Any]:
        value = self._json("/api/v2/transfer/info")
        if not isinstance(value, dict):
            raise ProtocolError("transfer response is not an object")
        return value

