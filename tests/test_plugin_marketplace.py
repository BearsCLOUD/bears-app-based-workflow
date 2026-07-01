import json
from pathlib import Path
import unittest

from tests.function_test_loader import load_function_tests


ROOT = Path(__file__).resolve().parents[1]


def test_git_backed_marketplace_points_to_plugin_root() -> None:
    marketplace_path = ROOT / ".agents" / "plugins" / "marketplace.json"
    marketplace = json.loads(marketplace_path.read_text())

    assert marketplace["name"] == "bears-workflow-plugin"
    assert marketplace["interface"]["displayName"] == "Bears Workflow Plugin"

    plugins = marketplace["plugins"]
    assert len(plugins) == 1
    plugin = plugins[0]
    assert plugin["name"] == "bears"
    assert plugin["source"] == {"source": "local", "path": "."}
    assert plugin["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert plugin["category"] == "Development"
    plugin_path = (ROOT / plugin["source"]["path"]).resolve()
    assert plugin_path == ROOT
    assert (plugin_path / ".codex-plugin" / "plugin.json").is_file()
    assert not (ROOT / "plugins" / "bears").exists()


def load_tests(
    loader: unittest.TestLoader,
    tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    """Expose pytest-style function tests to unittest discovery."""
    del loader, pattern
    return load_function_tests(globals(), tests)
