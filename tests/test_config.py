import tempfile
import textwrap
import unittest
from pathlib import Path

from seedbox_doctor.config import ConfigError, load_profile


class ProfileLoadingTests(unittest.TestCase):
    def write_config(self, content: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "config.ini"
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        return path

    def test_loads_profile_and_password_from_named_environment_variable(self) -> None:
        path = self.write_config(
            """
            [profile.main]
            url = http://127.0.0.1:8080/
            username = auditor
            password_env = QB_MAIN_PASSWORD
            timeout = 4.5
            local = yes
            download_roots = /data/torrents, /srv/archive
            """
        )

        profile = load_profile(path, environ={"QB_MAIN_PASSWORD": "secret"})

        self.assertEqual(profile.url, "http://127.0.0.1:8080")
        self.assertEqual(profile.username, "auditor")
        self.assertEqual(profile.password, "secret")
        self.assertTrue(profile.local)
        self.assertEqual(len(profile.download_roots), 2)
        self.assertNotIn("secret", repr(profile))

    def test_environment_and_explicit_overrides_have_priority(self) -> None:
        path = self.write_config(
            """
            [profile.main]
            url = http://qb.local:8080
            password_env = QB_PASSWORD
            """
        )

        profile = load_profile(
            path,
            environ={
                "QB_PASSWORD": "from-profile-env",
                "SEEDBOX_DOCTOR_URL": "https://env.example.test",
            },
            overrides={"url": "https://cli.example.test", "password": "cli-secret"},
        )

        self.assertEqual(profile.url, "https://cli.example.test")
        self.assertEqual(profile.password, "cli-secret")

    def test_rejects_plaintext_passwords(self) -> None:
        path = self.write_config(
            """
            [profile.main]
            url = http://localhost:8080
            password = unsafe
            """
        )
        with self.assertRaisesRegex(ConfigError, "plaintext secret"):
            load_profile(path, environ={})

    def test_rejects_credentials_in_url(self) -> None:
        path = self.write_config(
            """
            [profile.main]
            url = http://admin:secret@localhost:8080
            password_env = QB_PASSWORD
            """
        )
        with self.assertRaisesRegex(ConfigError, "embedded"):
            load_profile(path, environ={"QB_PASSWORD": "secret"})

    def test_rejects_malformed_ini_without_echoing_contents(self) -> None:
        secret_text = "do-not-echo-this"
        path = self.write_config(
            f"""
            [profile.main]
            url = http://localhost:8080
            url = {secret_text}
            """
        )

        with self.assertRaises(ConfigError) as context:
            load_profile(path, environ={"SEEDBOX_DOCTOR_PASSWORD": "secret"})

        self.assertIn("could not be parsed", str(context.exception))
        self.assertNotIn(secret_text, str(context.exception))

    def test_rejects_invalid_or_ambiguous_urls(self) -> None:
        invalid_urls = (
            "http://localhost:99999",
            "http://localhost:8080?target=/api",
            "http://localhost:8080/#credentials",
            "http://[broken",
            "http://",
        )
        for url in invalid_urls:
            with self.subTest(url=url):
                path = self.write_config(
                    f"""
                    [profile.main]
                    url = {url}
                    """
                )
                with self.assertRaises(ConfigError):
                    load_profile(
                        path,
                        environ={"SEEDBOX_DOCTOR_PASSWORD": "secret"},
                    )

    def test_allows_reverse_proxy_paths(self) -> None:
        path = self.write_config(
            """
            [profile.main]
            url = https://example.test/qbittorrent/
            """
        )

        profile = load_profile(
            path,
            environ={"SEEDBOX_DOCTOR_PASSWORD": "secret"},
        )

        self.assertEqual(profile.url, "https://example.test/qbittorrent")

    def test_rejects_empty_username_and_unknown_fields(self) -> None:
        for field in ("username =", "usrname = typo"):
            with self.subTest(field=field):
                path = self.write_config(
                    f"""
                    [profile.main]
                    url = http://localhost:8080
                    {field}
                    """
                )
                with self.assertRaises(ConfigError):
                    load_profile(
                        path,
                        environ={"SEEDBOX_DOCTOR_PASSWORD": "secret"},
                    )

    def test_rejects_unknown_override_fields(self) -> None:
        path = self.write_config(
            """
            [profile.main]
            url = http://localhost:8080
            """
        )

        with self.assertRaisesRegex(ConfigError, "unknown override"):
            load_profile(
                path,
                environ={"SEEDBOX_DOCTOR_PASSWORD": "secret"},
                overrides={"usrname": "typo"},
            )


if __name__ == "__main__":
    unittest.main()
