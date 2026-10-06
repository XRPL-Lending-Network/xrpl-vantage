"""Tests for is_private_address.

Network-free: the exporter module is imported but no collector or server is
started. Run from the repository root:

    python3 -m unittest discover -s tests
"""

import importlib.util
import os
import unittest

_PATH = os.path.join(os.path.dirname(__file__), "..", "exporter", "xrpl_vantage.py")
_spec = importlib.util.spec_from_file_location("xrpl_vantage", _PATH)
xrpl_vantage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(xrpl_vantage)

is_private_address = xrpl_vantage.is_private_address


class IPv4MappedTest(unittest.TestCase):

    def test_private_ranges(self):
        for address in [
                "::ffff:10.0.0.20",
                "[::ffff:192.168.1.20]:51235",
                "[::ffff:a00:14]:51235",
                "::FFFF:172.16.0.1",
                "::ffff:172.31.255.255",
                "::ffff:127.0.0.1",
                "::ffff:169.254.1.1",
                "[::ffff:10.0.0.20]"]:
            with self.subTest(address=address):
                self.assertTrue(is_private_address(address))

    def test_public_ranges(self):
        for address in [
                "[::ffff:8.8.8.8]:51235",
                "::ffff:172.15.255.255",
                "::ffff:172.32.0.0"]:
            with self.subTest(address=address):
                self.assertFalse(is_private_address(address))

    def test_outside_exporter_policy(self):
        # Not in the exporter's private ranges, so counted as public. That is
        # the current policy, not a claim that these are globally routable.
        for address in [
                "::ffff:192.0.2.1",
                "::ffff:198.18.0.1",
                "::ffff:100.64.0.1",
                "::ffff:0.0.0.0"]:
            with self.subTest(address=address):
                self.assertFalse(is_private_address(address))


class UnchangedClassificationTest(unittest.TestCase):

    def test_private(self):
        for address in ["10.0.0.20:51235", "::1", "fd00::1", "fe80::1"]:
            with self.subTest(address=address):
                self.assertTrue(is_private_address(address))

    def test_public(self):
        for address in ["8.8.8.8"]:
            with self.subTest(address=address):
                self.assertFalse(is_private_address(address))


if __name__ == "__main__":
    unittest.main()
