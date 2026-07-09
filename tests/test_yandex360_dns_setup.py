from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import urllib.error
import urllib.request
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "skills" / "yandex360-dns" / "scripts" / "infisical_yandex360_setup.py"
spec = importlib.util.spec_from_file_location("infisical_yandex360_setup", SCRIPT_PATH)
setup = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(setup)  # type: ignore[arg-type]

DNS_SCRIPT_PATH = PLUGIN_ROOT / "skills" / "yandex360-dns" / "scripts" / "yandex360_dns.py"
dns_spec = importlib.util.spec_from_file_location("yandex360_dns", DNS_SCRIPT_PATH)
dns = importlib.util.module_from_spec(dns_spec)
assert dns_spec.loader is not None
dns_spec.loader.exec_module(dns)  # type: ignore[arg-type]

CUTOVER_VALIDATOR_PATH = PLUGIN_ROOT / "skills" / "yandex360-dns" / "scripts" / "validate_yandex360_dns_cutover.py"
SECRET_MARKER = "audit-secret-marker-not-real"
FORBIDDEN_ENV_PATH = "/srv/bears/.env"


def subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    raise AssertionError("parser has no subcommands")


def option_strings(parser: argparse.ArgumentParser, command: str) -> set[str]:
    return {
        option
        for action in subcommands(parser)[command]._actions
        for option in action.option_strings
    }


class Yandex360InfisicalSetupTest(unittest.TestCase):
    def test_planned_keys_are_names_only_for_prompt_free_dry_run(self) -> None:
        self.assertEqual(
            setup.planned_keys(),
            [
                "YANDEX360_DNS_API_BASE",
                "YANDEX360_DNS_CLIENT_ID",
                "YANDEX360_DNS_CLIENT_SECRET",
                "YANDEX360_DNS_DOMAIN",
                "YANDEX360_DNS_OAUTH_TOKEN",
                "YANDEX360_DNS_ORG_ID",
                "YANDEX360_DNS_SCOPE",
            ],
        )

    def test_setup_dry_run_is_operator_instruction_only(self) -> None:
        args = setup.parser().parse_args(["--dry-run"])
        packet = setup.operator_instruction_packet(args)

        self.assertEqual(packet["category"], "operator_manual_secret_entry_required")
        self.assertEqual(packet["write_mode"], "disabled_no_file_secret_transport")
        self.assertFalse(packet["secret_values_printed"])
        self.assertFalse(packet["stored"])
        self.assertIn("YANDEX360_DNS_OAUTH_TOKEN", packet["would_update_keys"])
        self.assertNotIn(SECRET_MARKER, json.dumps(packet))

    def test_setup_non_dry_run_does_not_collect_or_echo_runtime_secrets(self) -> None:
        stdout = io.StringIO()
        argv = [str(SCRIPT_PATH), "--from-runtime-env"]
        env = {
            "YANDEX360_DNS_CLIENT_ID": "client-id",
            "YANDEX360_DNS_CLIENT_SECRET": SECRET_MARKER,
            "YANDEX360_DNS_ORG_ID": "12345",
            "YANDEX360_DNS_OAUTH_TOKEN": SECRET_MARKER,
        }

        with mock.patch.object(sys, "argv", argv), mock.patch.dict(os.environ, env, clear=True):
            with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as raised:
                setup.main()

        self.assertEqual(raised.exception.code, 2)
        output = stdout.getvalue()
        self.assertNotIn(SECRET_MARKER, output)
        payload = json.loads(output)
        self.assertEqual(payload["category"], "operator_manual_secret_entry_required")
        self.assertFalse(payload["secret_values_printed"])
        self.assertNotIn("stdout", payload)
        self.assertNotIn("stderr", payload)
        self.assertIn("YANDEX360_DNS_CLIENT_SECRET", payload["present_keys"])

    def test_upstream_failure_packet_is_stable_category_only(self) -> None:
        payload = setup.upstream_failure_packet(17)
        output = json.dumps(payload)

        self.assertEqual(payload["category"], "infisical_upstream_failure")
        self.assertEqual(payload["exit_code"], 17)
        self.assertFalse(payload["secret_values_printed"])
        self.assertNotIn("stdout", payload)
        self.assertNotIn("stderr", payload)
        self.assertNotIn(SECRET_MARKER, output)

    def test_plugin_default_env_check_uses_runtime_env_only(self) -> None:
        env = {
            "YANDEX360_DNS_CLIENT_ID": "client",
            "YANDEX360_DNS_CLIENT_SECRET": "secret",
            "YANDEX360_DNS_DOMAIN": "bears.ru",
            "YANDEX360_DNS_ORG_ID": "12345",
            "YANDEX360_DNS_OAUTH_TOKEN": "token",
            "YANDEX360_DNS_API_BASE": "https://api360.yandex.net",
            "YANDEX360_DNS_SCOPE": "directory:read_organization directory:manage_dns",
        }
        args = dns.parser().parse_args(["env-check"])

        with mock.patch.dict(os.environ, env, clear=True):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                args.func(args)

        payload = json.loads(out.getvalue())
        self.assertIsNone(args.env)
        self.assertEqual(payload["env"], "runtime")
        self.assertEqual(payload["local_env_file_loading"], "disabled")
        self.assertNotIn(FORBIDDEN_ENV_PATH, out.getvalue())
        self.assertTrue(all(row["present"] for row in payload["keys"]))

    def test_forbidden_root_env_path_not_echoed(self) -> None:
        result = subprocess.run(
            [sys.executable, str(DNS_SCRIPT_PATH), "--env", FORBIDDEN_ENV_PATH, "env-check"],
            check=False,
            capture_output=True,
            text=True,
            env={"PYTHONDONTWRITEBYTECODE": "1", "YANDEX360_DNS_OAUTH_TOKEN": SECRET_MARKER},
        )

        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Local env file loading is disabled", combined)
        self.assertNotIn(SECRET_MARKER, combined)
        self.assertNotIn(FORBIDDEN_ENV_PATH, combined)

        with self.assertRaises(SystemExit) as raised:
            dns.load_env(Path(FORBIDDEN_ENV_PATH))
        self.assertIn("Local env file loading is disabled", str(raised.exception))
        self.assertNotIn(FORBIDDEN_ENV_PATH, str(raised.exception))

    def test_no_local_env_file_is_loaded_or_written(self) -> None:
        with self.assertRaises(SystemExit) as load_raised:
            dns.load_env(Path("ignored-local.env"))
        self.assertIn("Local env file loading is disabled", str(load_raised.exception))
        self.assertNotIn("ignored-local.env", str(load_raised.exception))

        with self.assertRaises(SystemExit) as save_raised:
            dns.save_env_values(Path("ignored-local.env"), {"YANDEX360_DNS_OAUTH_TOKEN": SECRET_MARKER})
        message = str(save_raised.exception)
        self.assertIn("Local credential persistence is disabled", message)
        self.assertNotIn("ignored-local.env", message)
        self.assertNotIn(SECRET_MARKER, message)

    def test_http_error_reports_stable_category_without_upstream_body(self) -> None:
        upstream_body = '{"error_description":"token audit-secret-marker-not-real leaked"}'
        http_error = urllib.error.HTTPError(
            "https://api360.yandex.net/directory/v1/org/123/domains/bears.ru/dns",
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(upstream_body.encode("utf-8")),
        )
        stderr = io.StringIO()

        with mock.patch.object(dns, "urlopen_no_proxy", side_effect=http_error):
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as raised:
                    dns.request_json(
                        "GET",
                        "https://api360.yandex.net/directory/v1/org/123/domains/bears.ru/dns",
                        SECRET_MARKER,
                    )

        self.assertEqual(raised.exception.code, 1)
        output = stderr.getvalue()
        self.assertNotIn(SECRET_MARKER, output)
        self.assertNotIn("error_description", output)
        payload = json.loads(output)
        self.assertEqual(payload["category"], "dns_api_http_error")
        self.assertEqual(payload["http_status"], 401)
        self.assertEqual(payload["error_class"], "unauthorized")

    def test_api_base_validator_allows_only_canonical_https_root(self) -> None:
        self.assertEqual(
            dns.validate_api_base("https://api360.yandex.net"),
            "https://api360.yandex.net",
        )
        rejected = [
            "http://api360.yandex.net",
            "https://evil.example.invalid",
            "https://127.0.0.1",
            "https://10.0.0.1",
            "https://user:pass@api360.yandex.net",
            "https://api360.yandex.net:444",
            "https://api360.yandex.net/evil",
            "https://api360.yandex.net?next=evil",
        ]
        for raw_base in rejected:
            with self.subTest(raw_base=raw_base):
                with self.assertRaises(SystemExit) as raised:
                    dns.validate_api_base(raw_base)
                self.assertNotIn(SECRET_MARKER, str(raised.exception))

    def test_request_json_rejects_hostile_url_before_authorization_request(self) -> None:
        with mock.patch.object(dns, "urlopen_no_proxy") as urlopen:
            with self.assertRaises(SystemExit) as raised:
                dns.request_json("GET", "https://evil.example.invalid/directory/v1/org", SECRET_MARKER)

        urlopen.assert_not_called()
        self.assertNotIn(SECRET_MARKER, str(raised.exception))

    def test_redirect_response_does_not_forward_oauth_token_to_new_host(self) -> None:
        req = urllib.request.Request(
            "https://api360.yandex.net/directory/v1/org",
            headers={"Authorization": f"OAuth {SECRET_MARKER}"},
        )
        redirect_request = dns.NoRedirectHandler().redirect_request(
            req,
            fp=None,
            code=302,
            msg="Found",
            headers={},
            newurl="https://evil.example.invalid/capture",
        )
        self.assertIsNone(redirect_request)

    def test_cutover_validator_is_presence_only_and_cache_safe(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CUTOVER_VALIDATOR_PATH)],
            check=False,
            capture_output=True,
            text=True,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
        )

        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertNotIn(SECRET_MARKER, combined)
        self.assertNotIn(FORBIDDEN_ENV_PATH, combined)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        check_status = {check["name"]: check["status"] for check in payload["checks"]}
        self.assertEqual(check_status["env_check_presence_only"], "ok")
        self.assertEqual(check_status["helper_dry_run"], "ok")
        self.assertEqual(check_status["plugin_root_env_refusal"], "ok")
        self.assertIn(check_status["cache_root_env_refusal"], {"ok", "skip", "fail"})


class Yandex360DnsCliSurfaceTest(unittest.TestCase):
    def test_parser_has_no_credential_persistence_commands(self) -> None:
        choices = subcommands(dns.parser())

        self.assertNotIn("save-token", choices)
        self.assertNotIn("exchange-code", choices)

    def test_create_and_delete_have_no_apply_flag(self) -> None:
        parser = dns.parser()

        self.assertIn("create", subcommands(parser))
        self.assertIn("delete", subcommands(parser))
        self.assertNotIn("--yes", option_strings(parser, "create"))
        self.assertNotIn("--yes", option_strings(parser, "delete"))

    def test_removed_commands_fail_before_secret_collection(self) -> None:
        for command in ("save-token", "exchange-code"):
            with self.subTest(command=command):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
                    dns.parser().parse_args([command, SECRET_MARKER])
                output = stderr.getvalue()
                self.assertNotIn(SECRET_MARKER, output)
                self.assertIn("invalid choice", output)

    def test_create_is_always_dry_run_and_never_calls_network(self) -> None:
        env = {
            "YANDEX360_DNS_ORG_ID": "12345",
            "YANDEX360_DNS_DOMAIN": "bears.ru",
            "YANDEX360_DNS_OAUTH_TOKEN": SECRET_MARKER,
        }
        args = dns.parser().parse_args([
            "create",
            "--type",
            "TXT",
            "--name",
            "review",
            "--text",
            "public-review-value",
        ])
        stdout = io.StringIO()

        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(dns, "urlopen_no_proxy") as urlopen:
            with contextlib.redirect_stdout(stdout):
                args.func(args)

        urlopen.assert_not_called()
        output = stdout.getvalue()
        self.assertNotIn(SECRET_MARKER, output)
        payload = json.loads(output)
        self.assertTrue(payload["dry_run"])
        self.assertTrue(payload["apply_disabled"])
        self.assertEqual(payload["blocked_method"], "POST")

    def test_delete_is_always_dry_run_and_never_calls_network(self) -> None:
        env = {
            "YANDEX360_DNS_ORG_ID": "12345",
            "YANDEX360_DNS_DOMAIN": "bears.ru",
            "YANDEX360_DNS_OAUTH_TOKEN": SECRET_MARKER,
        }
        args = dns.parser().parse_args(["delete", "--record-id", "123"])
        stdout = io.StringIO()

        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(dns, "urlopen_no_proxy") as urlopen:
            with contextlib.redirect_stdout(stdout):
                args.func(args)

        urlopen.assert_not_called()
        output = stdout.getvalue()
        self.assertNotIn(SECRET_MARKER, output)
        payload = json.loads(output)
        self.assertTrue(payload["dry_run"])
        self.assertTrue(payload["apply_disabled"])
        self.assertEqual(payload["blocked_method"], "DELETE")

    def test_create_yes_apply_is_not_a_parser_path(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
            dns.parser().parse_args(["create", "--type", "TXT", "--name", "x", "--yes"])

        output = stderr.getvalue()
        self.assertIn("unrecognized arguments: --yes", output)
        self.assertNotIn(SECRET_MARKER, output)


if __name__ == "__main__":
    unittest.main()
