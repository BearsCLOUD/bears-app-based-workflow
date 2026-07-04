"""Fast contract tests for pytest-style function exposure to unittest."""

from __future__ import annotations

import unittest


def _discovered_count(pattern: str) -> int:
    suite = unittest.defaultTestLoader.discover("tests", pattern=pattern)
    return suite.countTestCases()


class FunctionTestLoaderContractTest(unittest.TestCase):
    def test_role_gate_methodology_mixed_module_keeps_class_and_function_tests(self) -> None:
        self.assertGreaterEqual(_discovered_count("test_role_gate_methodology.py"), 1)

    def test_validate_overlay_function_tests_are_visible_to_unittest(self) -> None:
        self.assertGreaterEqual(_discovered_count("test_validate_overlay.py"), 1)

    def test_plugin_marketplace_function_test_is_visible_to_unittest(self) -> None:
        self.assertEqual(_discovered_count("test_plugin_marketplace.py"), 1)


if __name__ == "__main__":
    unittest.main()
