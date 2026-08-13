import unittest

import seedbox_doctor


class SmokeTests(unittest.TestCase):
    def test_version_is_exposed(self) -> None:
        self.assertEqual(seedbox_doctor.__version__, "0.1.1")


if __name__ == "__main__":
    unittest.main()
