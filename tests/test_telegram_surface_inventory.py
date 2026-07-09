"""Tests for Telegram surface inventory governance."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path
import unittest


def _load_module():
    plugin_root = Path(__file__).resolve().parents[1]
    module_path = plugin_root / "scripts" / "telegram_surface_inventory.py"
    spec = importlib.util.spec_from_file_location("telegram_surface_inventory", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_INVENTORY = _load_module()


class TelegramSurfaceInventoryTests(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _run_main(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = _INVENTORY.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_covered_discovered_path_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "projects/samplebot/app/main.py"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                "from aiogram import Bot, Dispatcher\n"
                "dp = Dispatcher()\n"
                "bot = Bot(token='x')\n",
                encoding="utf-8",
            )
            catalog = root / "catalog.json"
            backlog = root / "backlog.json"
            self._write_json(
                catalog,
                {
                    "surfaces": [
                        {
                            "name": "samplebot",
                            "path": "projects/samplebot",
                            "migration_status": "already-aiogram3-hardening",
                        }
                    ]
                },
            )
            self._write_json(backlog, {"items": []})

            code, stdout, stderr = self._run_main(
                "validate",
                "--workspace-root",
                str(root),
                "--catalog",
                str(catalog),
                "--backlog",
                str(backlog),
            )

            self.assertEqual(code, 0)
            self.assertIn("covered_paths: 1", stdout)
            self.assertIn("inventory ok", stdout)
            self.assertEqual(stderr, "")

    def test_uncovered_telegram_like_path_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret_like = "SHOULD_NOT_APPEAR_SECRET_123456"
            source = root / "projects/uncovered/src/bot.py"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                "from aiogram import Bot, Dispatcher\n"
                "dp = Dispatcher()\n"
                f"TOKEN = '{secret_like}'\n",
                encoding="utf-8",
            )
            catalog = root / "catalog.json"
            backlog = root / "backlog.json"
            self._write_json(catalog, {"surfaces": []})
            self._write_json(backlog, {"items": []})

            code, stdout, stderr = self._run_main(
                "validate",
                "--workspace-root",
                str(root),
                "--catalog",
                str(catalog),
                "--backlog",
                str(backlog),
            )

            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertIn("projects/uncovered/src/bot.py", stderr)
            self.assertIn("classification=bot-runtime-aiogram", stderr)
            self.assertNotIn(secret_like, stderr)

    def test_excluded_directories_and_test_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hidden_vendor = root / "projects/mobile/.android-sdk-ndk/sdk/python/bot.py"
            hidden_vendor.parent.mkdir(parents=True, exist_ok=True)
            hidden_vendor.write_text("from aiogram import Bot\ndp = Dispatcher()\n", encoding="utf-8")
            node_modules = root / "projects/sample/node_modules/pkg/bot.py"
            node_modules.parent.mkdir(parents=True, exist_ok=True)
            node_modules.write_text("from aiogram import Bot\ndp = Dispatcher()\n", encoding="utf-8")
            test_file = root / "projects/sample/test-aiogram-socks.py"
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text("from aiogram import Bot\ndp = Dispatcher()\n", encoding="utf-8")

            report = _INVENTORY.evaluate_inventory(root, {"surfaces": []}, {"items": []})

            self.assertEqual(report["discovered_count"], 0)
            self.assertEqual(report["uncovered_count"], 0)


    def test_notification_and_custom_bot_classification_are_precise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notifier = root / "projects/sample/app/notifier.py"
            notifier.parent.mkdir(parents=True, exist_ok=True)
            notifier.write_text(
                "class TelegramNotifier:\n"
                "    async def send_message(self, chat_id):\n"
                "        return chat_id\n",
                encoding="utf-8",
            )
            custom_bot = root / "projects/custom/src/bot_service.py"
            custom_bot.parent.mkdir(parents=True, exist_ok=True)
            custom_bot.write_text(
                "class TelegramBotService:\n"
                "    def send_message(self, chat_id):\n"
                "        return chat_id\n",
                encoding="utf-8",
            )

            discoveries = {
                item["path"]: item["classification"]
                for item in _INVENTORY.discover_surfaces(root)
            }

            self.assertEqual(
                discoveries["projects/sample/app/notifier.py"],
                "non-bot-notification-bridge",
            )
            self.assertEqual(
                discoveries["projects/custom/src/bot_service.py"],
                "bot-runtime-custom",
            )

    def test_summary_emits_paths_not_source_snippets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret_like = "INLINE_SOURCE_SNIPPET_SHOULD_STAY_PRIVATE"
            source = root / "projects/notifier/telegram_notify.py"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                "import urllib.request\n"
                f"TOKEN = '{secret_like}'\n"
                "URL = 'https://api.telegram.org'\n"
                "def send_telegram():\n    return 'ok'\n",
                encoding="utf-8",
            )
            catalog = {
                "surfaces": [
                    {
                        "name": "notifier",
                        "path": "projects/notifier/telegram_notify.py",
                        "migration_status": "not-applicable-non-bot",
                        "inventory_coverage_status": "non-bot-notifier",
                    }
                ]
            }
            backlog = {"items": []}

            report = _INVENTORY.evaluate_inventory(root, catalog, backlog)
            summary = _INVENTORY.render_summary(report)

            self.assertIn("projects/notifier/telegram_notify.py", summary)
            self.assertIn("classification=non-bot-notification-bridge", summary)
            self.assertIn("catalog_inventory_only_surfaces: 1", summary)
            self.assertNotIn(secret_like, summary)


if __name__ == "__main__":
    unittest.main()
