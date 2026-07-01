"""Tests for Bears Secret Factory write-only Infisical governance."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "secret_factory.py"
spec = importlib.util.spec_from_file_location("secret_factory", SCRIPT_PATH)
secret_factory = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(secret_factory)  # type: ignore[arg-type]


class FakeResponse:
    def __init__(self) -> None:
        self.closed = False
        self.url = "https://app.infisical.com/api/v4/secrets/APP_RANDOM_HEX"

    def close(self) -> None:
        self.closed = True

    def geturl(self) -> str:
        return self.url


class SecretFactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = secret_factory.load_catalog()

    def _test_env(self, **overrides: str) -> dict[str, str]:
        env = {
            "INFISICAL_TOKEN": "test-token-not-secret-fixture",
            "INFISICAL_PROJECT_ID": "project-id-fixture",
            "INFISICAL_ENVIRONMENT": "dev",
            "INFISICAL_API_URL": "https://app.infisical.com",
        }
        env.update(overrides)
        return env

    def test_catalog_validates(self) -> None:
        self.assertEqual(secret_factory.validate_catalog(self.catalog), [])

    def test_request_schema_catalog_contract_is_runtime_parser_source_guard(self) -> None:
        schema = self.catalog["request_schema"]
        self.assertEqual(schema["required_fields"], ["secret_name", "kind"])
        self.assertEqual(schema["optional_fields"], ["secret_path", "bytes", "length"])
        self.assertEqual(
            set(schema["required_fields"]) | set(schema["optional_fields"]),
            secret_factory.ALLOWED_REQUEST_FIELDS,
        )
        self.assertGreaterEqual(
            set(schema["forbidden_fields"]),
            {"secret_value", "token", "credential", "credentials", "private_key"},
        )

    def test_catalog_validation_rejects_missing_request_schema(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog.pop("request_schema")
        self.assertIn("request_schema must be an object", secret_factory.validate_catalog(catalog))

    def test_catalog_validation_rejects_request_schema_drift(self) -> None:
        cases = [
            ("required_fields", ["secret_name"]),
            ("optional_fields", ["secret_path", "bytes", "length", "note"]),
            ("forbidden_fields", ["secret_value"]),
        ]
        for field, value in cases:
            with self.subTest(field=field):
                catalog = json.loads(json.dumps(self.catalog))
                catalog["request_schema"][field] = value
                rendered = "\n".join(secret_factory.validate_catalog(catalog))
                self.assertIn(f"request_schema.{field}", rendered)

    def test_infisical_network_policy_contract_is_validated(self) -> None:
        policy = self.catalog["infisical_network_policy"]
        self.assertEqual(policy["required_api_scheme"], "https")
        self.assertEqual(policy["allowed_hosts"], ["app.infisical.com"])
        self.assertTrue(policy["reject_host_changes"])

    def test_catalog_validation_rejects_infisical_network_policy_drift(self) -> None:
        cases = [
            ("required_api_scheme", "http", "required_api_scheme"),
            ("allowed_hosts", ["example.invalid"], "allowed_hosts"),
            ("reject_host_changes", False, "reject_host_changes"),
        ]
        for field, value, expected in cases:
            with self.subTest(field=field):
                catalog = json.loads(json.dumps(self.catalog))
                catalog["infisical_network_policy"][field] = value
                rendered = "\n".join(secret_factory.validate_catalog(catalog))
                self.assertIn(expected, rendered)

    def test_catalog_validation_commands_cover_full_control_chain(self) -> None:
        expected = [
            "python3 scripts/platform_roles.py validate",
            "python3 scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json",
            "python3 scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json",
            "python3 scripts/secret_factory.py validate",
            "python3 -m unittest tests/test_secret_factory.py tests/test_platform_roles.py",
            "python3 scripts/validate_overlay.py --json validate --strict-overlay-skills",
        ]
        self.assertEqual(self.catalog["validation"]["commands"], expected)

    def test_names_only_handoff_readiness_lists_required_refs(self) -> None:
        packet = secret_factory.names_only_handoff_readiness(self.catalog)
        represented = {(ref["secret_name"], ref["secret_path"]) for ref in packet["represented_refs"]}
        refs_by_name = {ref["secret_name"]: ref for ref in packet["represented_refs"]}
        self.assertEqual(packet["status"], "OPERATOR_HANDOFF_REQUIRED")
        self.assertTrue(packet["metadata_only"])
        self.assertFalse(packet["live_infisical_existence_checked"])
        self.assertEqual(packet["infisical_readback"], "forbidden")
        self.assertIn(("SERVERSPACE_API_KEY", "/srv/bears"), represented)
        self.assertIn(("S2CTL_APIKEY", "/serverspace/universal-platform/users/s2ctl-apikey"), represented)
        self.assertIn(("S2CTL_APIKEY", "/serverspace/universal-platform/gateway/s2ctl-apikey"), represented)
        self.assertIn(("S2CTL_APIKEY", "/serverspace/universal-platform/payments/s2ctl-apikey"), represented)
        self.assertIn(("GITLAB_NAMES_ONLY_TOKEN", "/gitlab/bears/names-only-inventory"), represented)
        gitlab_ref = refs_by_name["GITLAB_NAMES_ONLY_TOKEN"]
        self.assertEqual(gitlab_ref["existence_status"], "operator_confirmed_live_ref")
        self.assertFalse(gitlab_ref["confirmation_required_before_use"])
        self.assertEqual(gitlab_ref["provider_api_routing"]["api_scheme"], "https")
        self.assertEqual(gitlab_ref["provider_api_routing"]["api_host"], "bears.gitlab.yandexcloud.net")
        self.assertEqual(gitlab_ref["provider_api_routing"]["api_path_prefix"], "/api/v4")
        self.assertEqual(gitlab_ref["provider_api_routing"]["token_secret_name"], "GITLAB_NAMES_ONLY_TOKEN")
        self.assertEqual(
            gitlab_ref["provider_api_routing"]["token_secret_path"],
            "/gitlab/bears/names-only-inventory",
        )
        operator_actions = {
            (item["secret_name"], item["secret_path"]): item["action"]
            for item in packet["operator_required"]
        }
        self.assertNotIn(("GITLAB_NAMES_ONLY_TOKEN", "/gitlab/bears/names-only-inventory"), operator_actions)
        ready_actions = {
            (item["secret_name"], item["secret_path"]): item["action"]
            for item in packet["ready_refs"]
        }
        self.assertEqual(
            ready_actions[("GITLAB_NAMES_ONLY_TOKEN", "/gitlab/bears/names-only-inventory")],
            "use_exact_infisical_ref_for_provider_api_without_token_output",
        )
        rendered = json.dumps(packet).casefold()
        self.assertNotIn('"secret_value"', rendered)
        self.assertNotIn('"value"', rendered)
        self.assertNotIn('"private_key"', rendered)

    def test_names_only_handoff_readiness_filters_provider(self) -> None:
        packet = secret_factory.names_only_handoff_readiness(self.catalog, provider="gitlab")
        self.assertEqual(packet["status"], "READY_WITH_INFISICAL_REF")
        self.assertEqual(len(packet["represented_refs"]), 1)
        self.assertEqual(packet["represented_refs"][0]["secret_name"], "GITLAB_NAMES_ONLY_TOKEN")
        self.assertEqual(packet["represented_refs"][0]["secret_path"], "/gitlab/bears/names-only-inventory")
        self.assertEqual(packet["represented_refs"][0]["existence_status"], "operator_confirmed_live_ref")
        self.assertFalse(packet["represented_refs"][0]["confirmation_required_before_use"])
        self.assertEqual(packet["represented_refs"][0]["provider_api_routing"]["api_scheme"], "https")
        self.assertEqual(
            packet["represented_refs"][0]["provider_api_routing"]["api_host"],
            "bears.gitlab.yandexcloud.net",
        )
        self.assertEqual(packet["represented_refs"][0]["provider_api_routing"]["api_path_prefix"], "/api/v4")
        self.assertEqual(packet["operator_required"], [])

    def test_validate_names_only_unconfirmed_ref_requires_resolution_policy(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["names_only_handoff_refs"]["refs"][-1]["existence_status"] = "documented_unconfirmed"
        catalog["names_only_handoff_refs"].pop("unconfirmed_ref_resolution")
        errors = secret_factory.validate_names_only_handoff_refs(catalog)
        self.assertIn("names_only_handoff_refs.unconfirmed_ref_resolution must be an object", errors)

    def test_validate_names_only_unconfirmed_ref_requires_t085_t109_guard(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["names_only_handoff_refs"]["refs"][-1]["existence_status"] = "documented_unconfirmed"
        catalog["names_only_handoff_refs"]["unconfirmed_ref_resolution"]["required_before_task_ids"] = ["T085"]
        errors = secret_factory.validate_names_only_handoff_refs(catalog)
        self.assertIn(
            "names_only_handoff_refs.unconfirmed_ref_resolution.required_before_task_ids must include T085 and T109",
            errors,
        )

    def test_validate_gitlab_provider_api_routing_pins_bears_gitlab_host(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["names_only_handoff_refs"]["provider_api_routing"]["gitlab"]["api_host"] = "gitlab.com"
        errors = secret_factory.validate_names_only_handoff_refs(catalog)
        self.assertIn(
            "names_only_handoff_refs.provider_api_routing.gitlab.api_host must be bears.gitlab.yandexcloud.net",
            errors,
        )

    def test_validate_names_only_handoff_refs_rejects_value_field(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["names_only_handoff_refs"]["refs"][0]["secret_value"] = "do-not-store"
        errors = secret_factory.validate_names_only_handoff_refs(catalog)
        self.assertIn("names_only_handoff_refs.refs[0] must contain only names-only ref fields", errors)

    def test_dry_run_allowed_is_presence_only(self) -> None:
        request = {"secret_name": "APP_SESSION_SECRET", "kind": "random_base64url", "bytes": 32}
        packet = secret_factory.create_secret(request, self.catalog, dry_run=True)
        self.assertEqual(packet["status"], "DRY_RUN_ALLOWED")
        self.assertEqual(packet["secret_name"], "APP_SESSION_SECRET")
        self.assertEqual(packet["generator_kind"], "random_base64url")
        self.assertNotIn("secret_value", packet)
        self.assertNotIn("value", packet)

    def test_provider_owned_kinds_return_handoff_without_value(self) -> None:
        required_fields = set(self.catalog["provider_handoff"]["required_fields"])
        for refusal_kind in secret_factory.MANDATORY_REFUSAL_KINDS:
            with self.subTest(refusal_kind=refusal_kind):
                request = {"secret_name": "STRIPE_API_KEY", "kind": refusal_kind}
                with self.assertRaises(secret_factory.RefusalError) as raised:
                    secret_factory.classify_request(request, self.catalog)
                packet = raised.exception.packet
                self.assertEqual(packet["status"], "HANDOFF_REQUIRED")
                self.assertEqual(packet["secret_name"], "STRIPE_API_KEY")
                self.assertEqual(set(packet), required_fields | {"status"})
                self.assertEqual(packet["requested_kind"], refusal_kind)
                rendered = json.dumps(packet)
                for forbidden in ("secret_value", "token", "credential", "private_key"):
                    self.assertNotIn(forbidden, packet)
                    self.assertNotIn(f'"{forbidden}":', rendered.casefold())

    def test_request_file_rejects_value_bearing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "request.json"
            path.write_text(json.dumps({"secret_name": "BAD_SECRET", "kind": "random_hex", "secret_value": "x"}))
            with self.assertRaises(secret_factory.SecretFactoryError):
                secret_factory._load_request(str(path))

    def test_request_file_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "request.json"
            path.write_text(json.dumps({"secret_name": "BAD_SECRET", "kind": "random_hex", "note": "x"}))
            with self.assertRaises(secret_factory.SecretFactoryError) as raised:
                secret_factory._load_request(str(path))
        self.assertIn("unsupported fields", str(raised.exception))

    def test_request_file_rejects_nested_value_bearing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "request.json"
            path.write_text(
                json.dumps(
                    {
                        "secret_name": "BAD_SECRET",
                        "kind": "random_hex",
                        "metadata": [{"Token": "x"}],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(secret_factory.SecretFactoryError):
                secret_factory._load_request(str(path))

    def test_request_file_rejects_value_bearing_key_variants(self) -> None:
        variants = ("secretValue", "secret-value", "apiToken", "dbCredential", "walletPrivateKey")
        for variant in variants:
            with self.subTest(variant=variant):
                with tempfile.TemporaryDirectory() as tmpdir:
                    path = Path(tmpdir) / "request.json"
                    path.write_text(
                        json.dumps(
                            {
                                "secret_name": "BAD_SECRET",
                                "kind": "random_hex",
                                "secret_path": "/ops",
                                "bytes": 16,
                                variant: "x",
                            }
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaises(secret_factory.SecretFactoryError):
                        secret_factory._load_request(str(path))

    def test_create_posts_value_but_returns_presence_only(self) -> None:
        captured: dict[str, str] = {}

        def fake_opener(req, timeout=0):  # type: ignore[no-untyped-def]
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = req.data.decode("utf-8")
            captured["authorization"] = req.headers.get("Authorization", "")
            return FakeResponse()

        request = {"secret_name": "APP_RANDOM_HEX", "kind": "random_hex", "bytes": 16}
        with mock.patch.dict(os.environ, self._test_env(), clear=False):
            with mock.patch.object(secret_factory, "generate_secret_value", return_value="FIXED_GENERATED_VALUE"):
                packet = secret_factory.create_secret(request, self.catalog, opener=fake_opener)
        self.assertEqual(packet["status"], "CREATED")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "https://app.infisical.com/api/v4/secrets/APP_RANDOM_HEX")
        body = json.loads(captured["body"])
        self.assertEqual(body["secretValue"], "FIXED_GENERATED_VALUE")
        self.assertNotIn("FIXED_GENERATED_VALUE", json.dumps(packet))
        self.assertEqual(captured["authorization"], "Bearer test-token-not-secret-fixture")

    def test_validate_catalog_requires_all_mandatory_refusal_kinds(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["refusal_classes"] = [
            item for item in catalog["refusal_classes"] if item["kind"] != "payment_credential"
        ]
        errors = secret_factory.validate_catalog(catalog)
        self.assertIn("refusal_classes missing payment_credential", errors)

    def test_validate_catalog_rejects_missing_default_bytes(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        del catalog["allowed_generators"][0]["default_bytes"]
        errors = secret_factory.validate_catalog(catalog)
        self.assertIn("random_base64url.default_bytes must be an integer", errors)

    def test_validate_catalog_rejects_non_int_default_length(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["allowed_generators"][2]["default_length"] = "40"
        errors = secret_factory.validate_catalog(catalog)
        self.assertIn("random_password.default_length must be an integer", errors)

    def test_validate_catalog_rejects_default_outside_bounds(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["allowed_generators"][1]["default_bytes"] = 129
        errors = secret_factory.validate_catalog(catalog)
        self.assertIn("random_hex.default_bytes must be within min_bytes and max_bytes", errors)

    def test_validate_catalog_rejects_unknown_password_alphabet(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["allowed_generators"][2]["alphabet"] = "unknown"
        errors = secret_factory.validate_catalog(catalog)
        self.assertIn("random_password.alphabet must map to a known runtime alphabet", errors)

    def test_random_password_uses_catalog_runtime_alphabet(self) -> None:
        request = {"secret_name": "APP_PASSWORD", "kind": "random_password", "length": 32}
        secret_value = secret_factory.generate_secret_value("random_password", request, self.catalog)
        alphabet_name = self.catalog["allowed_generators"][2]["alphabet"]
        runtime_alphabet = secret_factory.PASSWORD_ALPHABETS[alphabet_name]
        self.assertTrue(set(secret_value).issubset(set(runtime_alphabet)))
        self.assertEqual(len(secret_value), 32)

    def test_cli_plan_handoff_prints_no_value_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            request_path = Path(tmpdir) / "request.json"
            request_path.write_text(json.dumps({"secret_name": "OAUTH_CLIENT_SECRET", "kind": "oauth_client_secret"}))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = secret_factory.main(["plan", str(request_path)])
        self.assertEqual(code, 2)
        output = stdout.getvalue()
        self.assertIn("HANDOFF_REQUIRED", output)
        self.assertNotIn("secret_value", output.casefold())
        self.assertNotIn("private_key", output.casefold())

    def test_cli_handoff_readiness_prints_names_only_refs(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = secret_factory.main(["handoff-readiness", "--provider", "serverspace"])
        self.assertEqual(code, 0)
        packet = json.loads(stdout.getvalue())
        self.assertFalse(packet["live_infisical_existence_checked"])
        self.assertFalse(packet["secret_values_printed"])
        self.assertEqual({ref["provider"] for ref in packet["represented_refs"]}, {"serverspace"})
        represented = {(ref["secret_name"], ref["secret_path"]) for ref in packet["represented_refs"]}
        self.assertIn(("SERVERSPACE_API_KEY", "/srv/bears"), represented)
        self.assertNotIn('"secret_value"', stdout.getvalue().casefold())
        self.assertNotIn("private_key", stdout.getvalue().casefold())

    def test_secret_name_policy_blocks_value_fragments(self) -> None:
        with self.assertRaises(secret_factory.SecretFactoryError):
            secret_factory.validate_secret_name("SECRET_VALUE", self.catalog)

    def test_secret_path_rejects_parent_traversal(self) -> None:
        with self.assertRaises(secret_factory.SecretFactoryError):
            secret_factory.classify_request(
                {"secret_name": "APP_RANDOM_HEX", "kind": "random_hex", "secret_path": "/ops/../prod"},
                self.catalog,
            )

    def test_write_to_infisical_rejects_non_https_url(self) -> None:
        with mock.patch.dict(os.environ, self._test_env(INFISICAL_API_URL="http://app.infisical.com"), clear=False):
            with self.assertRaises(secret_factory.SecretFactoryError) as raised:
                secret_factory.write_to_infisical(
                    secret_name="APP_RANDOM_HEX",
                    secret_value="FIXED_GENERATED_VALUE",
                    secret_path="/",
                    catalog=self.catalog,
                )
        self.assertIn("must use https", str(raised.exception))

    def test_write_to_infisical_rejects_foreign_host(self) -> None:
        with mock.patch.dict(os.environ, self._test_env(INFISICAL_API_URL="https://evil.example"), clear=False):
            with self.assertRaises(secret_factory.SecretFactoryError) as raised:
                secret_factory.write_to_infisical(
                    secret_name="APP_RANDOM_HEX",
                    secret_value="FIXED_GENERATED_VALUE",
                    secret_path="/",
                    catalog=self.catalog,
                )
        self.assertIn("host is not allowed", str(raised.exception))

    def test_runtime_api_url_uses_policy_allowlist_before_default_host(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["secret_manager_create_target"]["default_api_url"] = "https://default-drift.example"
        catalog["infisical_network_policy"]["allowed_hosts"] = ["app.infisical.com"]

        with mock.patch.dict(os.environ, self._test_env(INFISICAL_API_URL="https://app.infisical.com"), clear=False):
            self.assertEqual(
                secret_factory._validated_infisical_api_url(catalog),
                "https://app.infisical.com",
            )

    def test_catalog_validation_requires_default_host_inside_policy_allowlist(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["secret_manager_create_target"]["default_api_url"] = "https://default-drift.example"
        errors = secret_factory.validate_catalog(catalog)
        self.assertIn(
            "infisical_network_policy.allowed_hosts must include the default Infisical create host",
            errors,
        )

    def test_write_to_infisical_rejects_base_url_path(self) -> None:
        with mock.patch.dict(os.environ, self._test_env(INFISICAL_API_URL="https://app.infisical.com/custom"), clear=False):
            with self.assertRaises(secret_factory.SecretFactoryError) as raised:
                secret_factory.write_to_infisical(
                    secret_name="APP_RANDOM_HEX",
                    secret_value="FIXED_GENERATED_VALUE",
                    secret_path="/",
                    catalog=self.catalog,
                )
        self.assertIn("must not include path", str(raised.exception))

    def test_write_to_infisical_rejects_redirected_host(self) -> None:
        class RedirectedResponse(FakeResponse):
            def __init__(self) -> None:
                super().__init__()
                self.url = "https://evil.example/api/v4/secrets/APP_RANDOM_HEX"

        def redirected_opener(req, timeout=0):  # type: ignore[no-untyped-def]
            return RedirectedResponse()

        with mock.patch.dict(os.environ, self._test_env(), clear=False):
            with self.assertRaises(secret_factory.SecretFactoryError) as raised:
                secret_factory.write_to_infisical(
                    secret_name="APP_RANDOM_HEX",
                    secret_value="FIXED_GENERATED_VALUE",
                    secret_path="/",
                    catalog=self.catalog,
                    opener=redirected_opener,
                )
        self.assertIn("unexpected host", str(raised.exception))

    def test_infisical_error_does_not_echo_body(self) -> None:
        class FailingOpener:
            def __call__(self, req, timeout=0):  # type: ignore[no-untyped-def]
                raise secret_factory.urllib.error.HTTPError(
                    req.full_url,
                    403,
                    "Forbidden",
                    hdrs=None,
                    fp=io.BytesIO(b"raw upstream body with FIXED_GENERATED_VALUE"),
                )

        stderr = io.StringIO()
        request = {"secret_name": "APP_RANDOM_HEX", "kind": "random_hex", "bytes": 16}
        with mock.patch.dict(os.environ, self._test_env(), clear=False):
            with mock.patch.object(secret_factory, "generate_secret_value", return_value="FIXED_GENERATED_VALUE"):
                with contextlib.redirect_stderr(stderr):
                    with self.assertRaises(secret_factory.SecretFactoryError) as raised:
                        secret_factory.create_secret(request, self.catalog, opener=FailingOpener())
        self.assertIn("HTTP 403", str(raised.exception))
        self.assertNotIn("FIXED_GENERATED_VALUE", str(raised.exception))
        self.assertNotIn("upstream body", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
