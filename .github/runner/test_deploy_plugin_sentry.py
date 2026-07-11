#!/usr/bin/env python3
"""Machine-only stub coverage for deploy gateway Sentry envelopes."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

MODULE_PATH = Path(__file__).with_name("deploy_plugin.py")
SPEC = importlib.util.spec_from_file_location("deploy_plugin_under_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("deploy gateway module is unavailable")
DEPLOY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DEPLOY
SPEC.loader.exec_module(DEPLOY)


class StubResponse:
    """Minimal context-managed response used without network access."""

    def __enter__(self) -> "StubResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _: int) -> bytes:
        return b""


class SentryGatewayCoverage(unittest.TestCase):
    def context(self) -> object:
        context = DEPLOY.DeployContext("a" * 40)
        context.version = "0.1.0+codex.20260711000000"
        return context

    def test_event_is_normalized_and_grouped(self) -> None:
        with mock.patch.dict(
            DEPLOY.os.environ,
            {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "4"},
            clear=False,
        ):
            event = DEPLOY.sentry_event("post-mutation-failure", self.context())
        self.assertEqual(
            event["fingerprint"],
            [DEPLOY.SENTRY_SERVICE, DEPLOY.SENTRY_COMPONENT, "post-mutation-failure"],
        )
        self.assertEqual(
            set(event["tags"]),
            {
                "error_code",
                "service",
                "component",
                "operation",
                "repository",
                "plugin",
                "git_sha",
                "plugin_version",
                "workflow_run",
                "receipt_schema",
            },
        )
        self.assertEqual(event["tags"]["workflow_run"], "123:4")
        encoded = json.dumps(event)
        for prohibited in ("stdout", "stderr", "request_body", "https://", "locals"):
            self.assertNotIn(prohibited, encoded)

    def test_transport_uses_stub_and_returns_event_reference(self) -> None:
        captured: dict[str, object] = {}

        def opener(outbound: object, *, timeout: int) -> StubResponse:
            captured["outbound"] = outbound
            captured["timeout"] = timeout
            return StubResponse()

        with mock.patch.object(
            DEPLOY,
            "read_sentry_dsn",
            return_value="https://public@example.invalid/42",
        ):
            reference = DEPLOY.report_sentry(
                "mutation-failure-after-start",
                self.context(),
                opener=opener,
            )
        self.assertRegex(reference or "", r"^sentry-event:[0-9a-f]{32}$")
        self.assertEqual(captured["timeout"], DEPLOY.SENTRY_TIMEOUT_SECONDS)
        outbound = captured["outbound"]
        self.assertEqual(outbound.full_url, "https://example.invalid/api/42/envelope/")
        self.assertIn("sentry_key=public", outbound.headers["X-sentry-auth"])

    def test_transport_failure_does_not_escape(self) -> None:
        def opener(*_: object, **__: object) -> StubResponse:
            raise OSError("stub transport failure")

        with mock.patch.object(
            DEPLOY,
            "read_sentry_dsn",
            return_value="https://public@example.invalid/42",
        ):
            reference = DEPLOY.report_sentry(
                "post-mutation-failure",
                self.context(),
                opener=opener,
            )
        self.assertIsNone(reference)


if __name__ == "__main__":
    unittest.main()
