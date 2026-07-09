"""Expose pytest-style function tests to unittest discovery."""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from typing import Any


def load_function_tests(namespace: dict[str, Any], base_suite: unittest.TestSuite | None = None) -> unittest.TestSuite:
    """Append zero-arg and tmp_path-style function tests to a unittest suite."""
    suite = base_suite if base_suite is not None else unittest.TestSuite()
    for name, candidate in sorted(namespace.items()):
        if not name.startswith("test_") or not callable(candidate):
            continue
        parameters = inspect.signature(candidate).parameters

        def run_case(test_func: Any = candidate, param_count: int = len(parameters)) -> None:
            if param_count == 0:
                test_func()
                return
            if param_count == 1:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    test_func(Path(tmp_dir))
                return
            raise TypeError(f"Unsupported unittest wrapper signature for {test_func.__name__}")

        run_case.__name__ = name
        suite.addTest(unittest.FunctionTestCase(run_case, description=name))
    return suite
