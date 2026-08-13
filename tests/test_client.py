import json
import unittest
from urllib.error import URLError
from urllib.parse import parse_qs

from seedbox_doctor.client import (
    AuthenticationError,
    ProtocolError,
    QbittorrentClient,
    TransportError,
)


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class FakeOpener:
    def __init__(self, responses: list[bytes | Exception]) -> None:
        self.responses = responses
        self.requests = []

    def open(self, request, timeout: float):
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return FakeResponse(response)


class ClientTests(unittest.TestCase):
    def test_login_and_read_only_endpoints(self) -> None:
        opener = FakeOpener(
            [
                b"Ok.",
                b"5.0.4",
                json.dumps({"web_ui_port": 8080}).encode(),
                json.dumps([{"hash": "abc", "state": "uploading"}]).encode(),
                json.dumps({"connection_status": "connected"}).encode(),
                b"",
            ]
        )
        client = QbittorrentClient(
            "http://localhost:8080", "admin", "secret", opener=opener
        )

        client.login()
        self.assertEqual(client.app_version(), "5.0.4")
        self.assertEqual(client.preferences()["web_ui_port"], 8080)
        self.assertEqual(client.torrents()[0]["hash"], "abc")
        self.assertEqual(client.transfer_info()["connection_status"], "connected")
        client.logout()

        login_request, timeout = opener.requests[0]
        self.assertEqual(login_request.method, "POST")
        self.assertEqual(timeout, 10.0)
        fields = parse_qs(login_request.data.decode())
        self.assertEqual(fields["username"], ["admin"])
        self.assertEqual(fields["password"], ["secret"])
        self.assertEqual(login_request.headers["Referer"], "http://localhost:8080/")

    def test_rejects_failed_login(self) -> None:
        client = QbittorrentClient(
            "http://localhost:8080", "admin", "wrong", opener=FakeOpener([b"Fails."])
        )
        with self.assertRaises(AuthenticationError):
            client.login()

    def test_requires_login_before_api_reads(self) -> None:
        client = QbittorrentClient(
            "http://localhost:8080", "admin", "secret", opener=FakeOpener([])
        )
        with self.assertRaises(AuthenticationError):
            client.preferences()

    def test_wraps_transport_errors_without_exposing_password(self) -> None:
        client = QbittorrentClient(
            "http://localhost:8080",
            "admin",
            "top-secret",
            opener=FakeOpener([URLError("connection refused")]),
        )
        with self.assertRaises(TransportError) as context:
            client.login()
        self.assertNotIn("top-secret", str(context.exception))

    def test_rejects_malformed_json(self) -> None:
        client = QbittorrentClient(
            "http://localhost:8080",
            "admin",
            "secret",
            opener=FakeOpener([b"Ok.", b"not-json"]),
        )
        client.login()
        with self.assertRaises(ProtocolError):
            client.preferences()


if __name__ == "__main__":
    unittest.main()
