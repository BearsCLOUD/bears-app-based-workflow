#!/usr/bin/env python3
"""Write-only Secret Factory for Bears Infisical secret creation."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import string
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "assets" / "catalog" / "secret-factory.v1.json"
REQUIRED_SCHEMA = "bears-secret-factory.v1"
SECRET_MANAGER_CREATE_TARGET_KEY = "secret_manager_create_target"
LEGACY_INFISICAL_TARGET_KEY = "infisical" + "_write_target"


def _secret_manager_create_target(catalog: dict[str, Any]) -> Any:
    return catalog.get(SECRET_MANAGER_CREATE_TARGET_KEY, catalog.get(LEGACY_INFISICAL_TARGET_KEY))


SAFE_OUTPUT_FIELDS = {"status", "secret_name", "generator_kind", "secret_path", "provider_handoff"}
ALLOWED_REQUEST_FIELDS = {"secret_name", "kind", "secret_path", "bytes", "length"}
REQUEST_SCHEMA_REQUIRED_FIELDS = ["secret_name", "kind"]
REQUEST_SCHEMA_OPTIONAL_FIELDS = ["secret_path", "bytes", "length"]
REQUEST_SCHEMA_MANDATORY_FORBIDDEN_FIELDS = {
    "secret_value",
    "token",
    "credential",
    "credentials",
    "private_key",
}
INFISICAL_NETWORK_POLICY_KEY = "infisical_network_policy"
NAMES_ONLY_HANDOFF_REF_FIELDS = {
    "provider",
    "secret_name",
    "secret_path",
    "handoff_owner",
    "purpose",
    "existence_status",
}
NAMES_ONLY_HANDOFF_STATUSES = {"operator_required", "documented_unconfirmed", "operator_confirmed_live_ref"}
UNCONFIRMED_REF_STATUS = "documented_unconfirmed"
CONFIRMED_LIVE_REF_STATUS = "operator_confirmed_live_ref"
UNCONFIRMED_REF_REQUIRED_TASKS = {"T085", "T109"}
UNCONFIRMED_REF_REQUIRED_CONFIRMATION_METHODS = {
    "operator_confirmed_exact_secret_name_and_path",
    "safe_metadata_only_list_folders_then_list_secret_names",
}
UNCONFIRMED_REF_REQUIRED_FORBIDDEN_METHODS = {
    "get_secret_or_readback",
    "list_secrets_without_names_only_or_exclude_values_mode",
    "provider_cli_secret_value_readback",
}
PROVIDER_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
PROVIDER_API_ROUTING_REQUIRED_FIELDS = {
    "api_scheme",
    "api_host",
    "api_path_prefix",
    "token_secret_name",
    "token_secret_path",
    "infisical_project_id",
    "infisical_environment",
    "preferred_auth_header",
    "accepted_auth_headers",
    "smoke_probe_path",
    "forbidden_hosts",
    "confirmation",
    "output_policy",
}
PASSWORD_ALPHABETS = {
    "letters_digits_symbols": string.ascii_letters + string.digits + "!#$%&()*+,-.:;<=>?@[]^_{|}~"
}
MANDATORY_REFUSAL_KINDS = (
    "provider_issued_api_key",
    "oauth_client_secret",
    "ssh_private_key",
    "tls_private_key",
    "payment_credential",
    "wallet_private_key",
)
_CAMEL_CASE_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")


class SecretFactoryError(RuntimeError):
    """Controlled Secret Factory failure without secret value material."""


class RefusalError(SecretFactoryError):
    """Raised when a request must be handled by a provider or human owner."""

    def __init__(self, packet: dict[str, Any]) -> None:
        super().__init__("provider handoff required")
        self.packet = packet


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    """Load the Secret Factory catalog."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SecretFactoryError("catalog root must be an object")
    return data


def _allowed_generators(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["kind"]: item
        for item in catalog.get("allowed_generators", [])
        if isinstance(item, dict) and isinstance(item.get("kind"), str)
    }


def _refusal_classes(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["kind"]: item
        for item in catalog.get("refusal_classes", [])
        if isinstance(item, dict) and isinstance(item.get("kind"), str)
    }


def _catalog_int(
    item: dict[str, Any],
    field: str,
    *,
    kind: str,
    errors: list[str] | None = None,
) -> int | None:
    value = item.get(field)
    if not isinstance(value, int):
        if errors is not None:
            errors.append(f"{kind}.{field} must be an integer")
        return None
    return value


def _validate_generator_bounds(item: dict[str, Any], *, kind: str, errors: list[str]) -> None:
    if kind in {"random_base64url", "random_hex"}:
        default_bytes = _catalog_int(item, "default_bytes", kind=kind, errors=errors)
        min_bytes = _catalog_int(item, "min_bytes", kind=kind, errors=errors)
        max_bytes = _catalog_int(item, "max_bytes", kind=kind, errors=errors)
        if min_bytes is not None and min_bytes < 16:
            errors.append(f"{kind}.min_bytes must be at least 16")
        if max_bytes is not None and max_bytes > 128:
            errors.append(f"{kind}.max_bytes must be at most 128")
        if None not in {default_bytes, min_bytes, max_bytes} and not min_bytes <= default_bytes <= max_bytes:
            errors.append(f"{kind}.default_bytes must be within min_bytes and max_bytes")
        return

    if kind == "random_password":
        default_length = _catalog_int(item, "default_length", kind=kind, errors=errors)
        min_length = _catalog_int(item, "min_length", kind=kind, errors=errors)
        max_length = _catalog_int(item, "max_length", kind=kind, errors=errors)
        if min_length is not None and min_length < 24:
            errors.append("random_password.min_length must be at least 24")
        if max_length is not None and max_length > 128:
            errors.append("random_password.max_length must be at most 128")
        if None not in {default_length, min_length, max_length} and not min_length <= default_length <= max_length:
            errors.append("random_password.default_length must be within min_length and max_length")
        alphabet = item.get("alphabet")
        if not isinstance(alphabet, str) or alphabet not in PASSWORD_ALPHABETS:
            errors.append("random_password.alphabet must map to a known runtime alphabet")


def _normalize_request_key_words(key: str) -> tuple[str, ...]:
    separated = _CAMEL_CASE_BOUNDARY.sub(r"\1_\2", key)
    parts = re.split(r"[^A-Za-z0-9]+", separated)
    return tuple(part.casefold() for part in parts if part)


def _is_forbidden_request_key(key: str) -> bool:
    words = _normalize_request_key_words(key)
    if not words:
        return False
    collapsed = "".join(words)
    if "token" in words or collapsed.endswith("token") or collapsed.startswith("token"):
        return True
    if "credential" in words or "credentials" in words or "credential" in collapsed:
        return True
    if {"secret", "value"}.issubset(words) or "secretvalue" in collapsed:
        return True
    if {"private", "key"}.issubset(words) or "privatekey" in collapsed:
        return True
    return False


def _validate_request_payload(request: dict[str, Any]) -> None:
    unknown_fields = sorted(key for key in request if key not in ALLOWED_REQUEST_FIELDS)
    if unknown_fields:
        raise SecretFactoryError(
            "request file contains unsupported fields; allowed fields are "
            + ", ".join(sorted(ALLOWED_REQUEST_FIELDS))
        )
    if _contains_forbidden_request_field(request):
        raise SecretFactoryError("request file contains forbidden value-bearing fields")


def _safe_static_secret_path(raw_path: Any, label: str) -> str:
    if not isinstance(raw_path, str):
        raise SecretFactoryError(f"{label} must be a string")
    if not raw_path.startswith("/") or ".." in Path(raw_path).parts:
        raise SecretFactoryError(f"{label} must be an absolute Infisical path without parent traversal")
    return raw_path


def _expected_infisical_host(catalog: dict[str, Any]) -> str:
    default_url = str((_secret_manager_create_target(catalog) or {}).get("default_api_url", ""))
    parsed = urllib.parse.urlsplit(default_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SecretFactoryError("catalog default_api_url must be https with a host")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise SecretFactoryError("catalog default_api_url must not include path, query, or fragment")
    return parsed.hostname.casefold()


def _infisical_policy_allowed_hosts(catalog: dict[str, Any]) -> set[str]:
    policy = catalog.get(INFISICAL_NETWORK_POLICY_KEY)
    if not isinstance(policy, dict):
        raise SecretFactoryError("infisical_network_policy must be an object")
    if policy.get("required_api_scheme") != "https":
        raise SecretFactoryError("infisical_network_policy.required_api_scheme must be https")
    allowed_hosts = policy.get("allowed_hosts")
    if (
        not isinstance(allowed_hosts, list)
        or not allowed_hosts
        or not all(isinstance(host, str) and host.strip() for host in allowed_hosts)
    ):
        raise SecretFactoryError("infisical_network_policy.allowed_hosts must be a non-empty string list")
    return {host.casefold() for host in allowed_hosts}


def _validated_infisical_api_url(catalog: dict[str, Any]) -> str:
    target = _secret_manager_create_target(catalog) or {}
    raw_url = os.environ.get("INFISICAL_API_URL", target.get("default_api_url", "https://app.infisical.com"))
    parsed = urllib.parse.urlsplit(str(raw_url))
    if parsed.scheme != "https":
        raise SecretFactoryError("INFISICAL_API_URL must use https")
    if not parsed.hostname:
        raise SecretFactoryError("INFISICAL_API_URL must include a host")
    if parsed.username or parsed.password:
        raise SecretFactoryError("INFISICAL_API_URL must not include credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise SecretFactoryError("INFISICAL_API_URL must not include path, query, or fragment")
    allowed_hosts = _infisical_policy_allowed_hosts(catalog)
    if parsed.hostname.casefold() not in allowed_hosts:
        raise SecretFactoryError("INFISICAL_API_URL host is not allowed")
    netloc = parsed.hostname
    if parsed.port is not None:
        netloc = f"{parsed.hostname}:{parsed.port}"
    return urllib.parse.urlunsplit(("https", netloc, "", "", ""))


def _validate_request_schema_contract(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    request_schema = catalog.get("request_schema")
    if not isinstance(request_schema, dict):
        return ["request_schema must be an object"]

    required_fields = request_schema.get("required_fields")
    optional_fields = request_schema.get("optional_fields")
    forbidden_fields = request_schema.get("forbidden_fields")
    if required_fields != REQUEST_SCHEMA_REQUIRED_FIELDS:
        errors.append("request_schema.required_fields must be exactly secret_name, kind")
    if optional_fields != REQUEST_SCHEMA_OPTIONAL_FIELDS:
        errors.append("request_schema.optional_fields must be exactly secret_path, bytes, length")
    if not isinstance(forbidden_fields, list) or not all(isinstance(item, str) for item in forbidden_fields):
        errors.append("request_schema.forbidden_fields must be a list of strings")
        forbidden_set: set[str] = set()
    else:
        forbidden_set = set(forbidden_fields)
        missing = sorted(REQUEST_SCHEMA_MANDATORY_FORBIDDEN_FIELDS - forbidden_set)
        if missing:
            errors.append("request_schema.forbidden_fields missing " + ", ".join(missing))
    schema_allowed = set(required_fields or []) | set(optional_fields or [])
    if schema_allowed != ALLOWED_REQUEST_FIELDS:
        errors.append("request_schema allowed fields must match runtime request parser fields")
    return errors


def _validate_infisical_network_policy(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    policy = catalog.get(INFISICAL_NETWORK_POLICY_KEY)
    if not isinstance(policy, dict):
        return ["infisical_network_policy must be an object"]
    if policy.get("required_api_scheme") != "https":
        errors.append("infisical_network_policy.required_api_scheme must be https")
    try:
        expected_host = _expected_infisical_host(catalog)
    except SecretFactoryError as exc:
        errors.append(f"infisical_network_policy cannot resolve expected host: {exc}")
        expected_host = None
    allowed_hosts = policy.get("allowed_hosts")
    if not isinstance(allowed_hosts, list) or not allowed_hosts:
        errors.append("infisical_network_policy.allowed_hosts must be a non-empty list")
        normalized_hosts: list[str] = []
    elif not all(isinstance(host, str) and host.strip() for host in allowed_hosts):
        errors.append("infisical_network_policy.allowed_hosts must contain only non-empty strings")
        normalized_hosts = []
    else:
        normalized_hosts = [host.casefold() for host in allowed_hosts]
    if len(normalized_hosts) != len(set(normalized_hosts)):
        errors.append("infisical_network_policy.allowed_hosts must not contain duplicates")
    if expected_host is not None and expected_host not in normalized_hosts:
        errors.append("infisical_network_policy.allowed_hosts must include the default Infisical create host")
    if policy.get("reject_host_changes") is not True:
        errors.append("infisical_network_policy.reject_host_changes must be true")
    return errors


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Block redirects so generated secret values never follow a new host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _open_without_redirects(request: urllib.request.Request, *, timeout: int) -> Any:
    opener = urllib.request.build_opener(_NoRedirectHandler)
    return opener.open(request, timeout=timeout)


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    """Return validation errors for the Secret Factory catalog."""

    errors: list[str] = []
    if catalog.get("schema") != REQUIRED_SCHEMA:
        errors.append(f"schema must be {REQUIRED_SCHEMA}")
    if catalog.get("owner_plugin") != "bears":
        errors.append("owner_plugin must be bears")

    target = _secret_manager_create_target(catalog) or {}
    if not isinstance(target, dict):
        errors.append("secret_manager_create_target must be an object")
        target = {}
    if target.get("api_family") != "v4":
        errors.append("secret_manager_create_target.api_family must be v4")
    if target.get("create_endpoint_template") != "/api/v4/secrets/{secretName}":
        errors.append("secret_manager_create_target.create_endpoint_template must be /api/v4/secrets/{secretName}")
    if target.get("allowed_http_methods") != ["POST"]:
        errors.append("secret_manager_create_target.allowed_http_methods must be POST only")
    forbidden_methods = set(target.get("forbidden_http_methods", []))
    if not {"GET", "PUT", "PATCH", "DELETE"}.issubset(forbidden_methods):
        errors.append("secret_manager_create_target.forbidden_http_methods must block read and mutation methods except POST create")
    try:
        _expected_infisical_host(catalog)
    except SecretFactoryError as exc:
        errors.append(str(exc))
    for env_name in ("INFISICAL_TOKEN", "INFISICAL_PROJECT_ID", "INFISICAL_ENVIRONMENT"):
        if env_name not in target.get("required_env", []):
            errors.append(f"secret_manager_create_target.required_env missing {env_name}")
    errors.extend(_validate_infisical_network_policy(catalog))
    errors.extend(_validate_request_schema_contract(catalog))

    generators = _allowed_generators(catalog)
    for required in ("random_base64url", "random_hex", "random_password"):
        if required not in generators:
            errors.append(f"allowed_generators missing {required}")
    for kind, item in generators.items():
        _validate_generator_bounds(item, kind=kind, errors=errors)

    refusals = _refusal_classes(catalog)
    for required in MANDATORY_REFUSAL_KINDS:
        if required not in refusals:
            errors.append(f"refusal_classes missing {required}")

    controls = catalog.get("write_only_controls")
    if not isinstance(controls, dict):
        errors.append("write_only_controls must be an object")
        controls = {}
    for field in (
        "print_secret_value",
        "read_secret_value",
        "store_secret_value_on_disk",
        "pass_secret_value_in_argv",
        "commit_secret_value",
        "log_secret_value",
        "include_secret_value_in_tests",
        "include_secret_value_in_docs",
    ):
        if controls.get(field) is not False:
            errors.append(f"write_only_controls.{field} must be false")
    if controls.get("discard_infisical_response_body") is not True:
        errors.append("write_only_controls.discard_infisical_response_body must be true")
    stdout_fields = set(controls.get("stdout_fields", []))
    if not stdout_fields or not stdout_fields.issubset(SAFE_OUTPUT_FIELDS):
        errors.append("write_only_controls.stdout_fields must stay presence-only")

    name_policy = catalog.get("secret_name_policy")
    if not isinstance(name_policy, dict):
        errors.append("secret_name_policy must be an object")
    else:
        try:
            re.compile(str(name_policy.get("pattern", "")))
        except re.error as exc:
            errors.append(f"secret_name_policy.pattern is invalid: {exc}")

    errors.extend(validate_names_only_handoff_refs(catalog))
    return errors


def validate_names_only_handoff_refs(catalog: dict[str, Any]) -> list[str]:
    """Validate cataloged Infisical handoff refs without Infisical readback."""

    errors: list[str] = []
    packet = catalog.get("names_only_handoff_refs")
    if not isinstance(packet, dict):
        errors.append("names_only_handoff_refs must be an object")
        return errors
    if packet.get("live_infisical_existence_policy") != "operator_confirmed_no_agent_readback":
        errors.append("names_only_handoff_refs.live_infisical_existence_policy must be operator_confirmed_no_agent_readback")
    if set(packet.get("required_ref_fields", [])) != NAMES_ONLY_HANDOFF_REF_FIELDS:
        errors.append("names_only_handoff_refs.required_ref_fields must match names-only ref fields")
    if set(packet.get("allowed_existence_statuses", [])) != NAMES_ONLY_HANDOFF_STATUSES:
        errors.append("names_only_handoff_refs.allowed_existence_statuses must match supported status set")
    refs = packet.get("refs")
    if not isinstance(refs, list) or not refs:
        errors.append("names_only_handoff_refs.refs must be a non-empty list")
        return errors
    if any(isinstance(ref, dict) and ref.get("existence_status") == UNCONFIRMED_REF_STATUS for ref in refs):
        resolution = packet.get("unconfirmed_ref_resolution")
        if not isinstance(resolution, dict):
            errors.append("names_only_handoff_refs.unconfirmed_ref_resolution must be an object")
        else:
            if resolution.get("applies_to_existence_status") != UNCONFIRMED_REF_STATUS:
                errors.append("names_only_handoff_refs.unconfirmed_ref_resolution.applies_to_existence_status must be documented_unconfirmed")
            task_ids = set(resolution.get("required_before_task_ids", []))
            if not UNCONFIRMED_REF_REQUIRED_TASKS.issubset(task_ids):
                errors.append("names_only_handoff_refs.unconfirmed_ref_resolution.required_before_task_ids must include T085 and T109")
            confirmation_methods = set(resolution.get("allowed_confirmation_methods", []))
            if not UNCONFIRMED_REF_REQUIRED_CONFIRMATION_METHODS.issubset(confirmation_methods):
                errors.append("names_only_handoff_refs.unconfirmed_ref_resolution.allowed_confirmation_methods must include operator exact ref and metadata-only list checks")
            forbidden_methods = set(resolution.get("forbidden_methods", []))
            if not UNCONFIRMED_REF_REQUIRED_FORBIDDEN_METHODS.issubset(forbidden_methods):
                errors.append("names_only_handoff_refs.unconfirmed_ref_resolution.forbidden_methods must block readback and unsafe list methods")
            if not isinstance(resolution.get("reason"), str) or not resolution["reason"]:
                errors.append("names_only_handoff_refs.unconfirmed_ref_resolution.reason must be a non-empty string")
    errors.extend(_validate_provider_api_routing(packet, refs, catalog))
    seen_refs: set[tuple[str, str]] = set()
    for index, ref in enumerate(refs):
        label = f"names_only_handoff_refs.refs[{index}]"
        if not isinstance(ref, dict):
            errors.append(f"{label} must be an object")
            continue
        fields = set(ref)
        if fields != NAMES_ONLY_HANDOFF_REF_FIELDS:
            errors.append(f"{label} must contain only names-only ref fields")
            continue
        if _contains_forbidden_request_field(ref):
            errors.append(f"{label} contains forbidden value-bearing fields")
        provider = ref.get("provider")
        if not isinstance(provider, str) or not PROVIDER_NAME_RE.fullmatch(provider):
            errors.append(f"{label}.provider must be a stable lowercase provider id")
        secret_name = ref.get("secret_name")
        if not isinstance(secret_name, str):
            errors.append(f"{label}.secret_name must be a string")
        else:
            try:
                validate_secret_name(secret_name, catalog)
            except SecretFactoryError as exc:
                errors.append(f"{label}.secret_name invalid: {exc}")
        secret_path = ref.get("secret_path")
        if not isinstance(secret_path, str):
            errors.append(f"{label}.secret_path must be a string")
        else:
            try:
                _safe_static_secret_path(secret_path, f"{label}.secret_path")
            except SecretFactoryError as exc:
                errors.append(str(exc))
        handoff_owner = ref.get("handoff_owner")
        refusal_owners = {item.get("handoff_owner") for item in _refusal_classes(catalog).values()}
        if handoff_owner not in refusal_owners:
            errors.append(f"{label}.handoff_owner must match a configured refusal handoff owner")
        if not isinstance(ref.get("purpose"), str) or not ref["purpose"]:
            errors.append(f"{label}.purpose must be a non-empty string")
        if ref.get("existence_status") not in NAMES_ONLY_HANDOFF_STATUSES:
            errors.append(f"{label}.existence_status must be a supported names-only handoff status")
        ref_key = (str(secret_name), str(secret_path))
        if ref_key in seen_refs:
            errors.append(f"{label} duplicates a names-only Infisical ref")
        seen_refs.add(ref_key)
    return errors


def _validate_provider_api_routing(
    packet: dict[str, Any],
    refs: list[Any],
    catalog: dict[str, Any],
) -> list[str]:
    """Validate provider API routing metadata without secret value access."""

    errors: list[str] = []
    routing = packet.get("provider_api_routing", {})
    if routing == {}:
        return errors
    if not isinstance(routing, dict):
        return ["names_only_handoff_refs.provider_api_routing must be an object"]
    ref_keys = {
        (ref.get("provider"), ref.get("secret_name"), ref.get("secret_path"))
        for ref in refs
        if isinstance(ref, dict)
    }
    for provider, route in routing.items():
        label = f"names_only_handoff_refs.provider_api_routing.{provider}"
        if not isinstance(provider, str) or not PROVIDER_NAME_RE.fullmatch(provider):
            errors.append(f"{label} provider key must be a stable lowercase provider id")
            continue
        if not isinstance(route, dict):
            errors.append(f"{label} must be an object")
            continue
        fields = set(route)
        if fields != PROVIDER_API_ROUTING_REQUIRED_FIELDS:
            errors.append(f"{label} fields must match provider API routing fields")
            continue
        api_scheme = route.get("api_scheme")
        if api_scheme != "https":
            errors.append(f"{label}.api_scheme must be https")
        api_host = route.get("api_host")
        if not isinstance(api_host, str) or not api_host:
            errors.append(f"{label}.api_host must be a non-empty string")
        elif provider == "gitlab" and api_host != "bears.gitlab.yandexcloud.net":
            errors.append(f"{label}.api_host must be bears.gitlab.yandexcloud.net")
        api_path_prefix = route.get("api_path_prefix")
        if not isinstance(api_path_prefix, str) or not api_path_prefix.startswith("/api/"):
            errors.append(f"{label}.api_path_prefix must be an absolute API path prefix")
        elif provider == "gitlab" and api_path_prefix != "/api/v4":
            errors.append(f"{label}.api_path_prefix must be /api/v4")
        token_secret_name = route.get("token_secret_name")
        if not isinstance(token_secret_name, str):
            errors.append(f"{label}.token_secret_name must be a string")
        else:
            try:
                validate_secret_name(token_secret_name, catalog)
            except SecretFactoryError as exc:
                errors.append(f"{label}.token_secret_name invalid: {exc}")
        token_secret_path = route.get("token_secret_path")
        if not isinstance(token_secret_path, str):
            errors.append(f"{label}.token_secret_path must be a string")
        else:
            try:
                _safe_static_secret_path(token_secret_path, f"{label}.token_secret_path")
            except SecretFactoryError as exc:
                errors.append(str(exc))
        if (provider, token_secret_name, token_secret_path) not in ref_keys:
            errors.append(f"{label} must reference a cataloged names-only Infisical ref")
        project_id = route.get("infisical_project_id")
        if not isinstance(project_id, str) or not UUID_RE.fullmatch(project_id):
            errors.append(f"{label}.infisical_project_id must be a UUID string")
        environment = route.get("infisical_environment")
        if not isinstance(environment, str) or not environment:
            errors.append(f"{label}.infisical_environment must be a non-empty string")
        accepted_headers = route.get("accepted_auth_headers")
        if not isinstance(accepted_headers, list) or not accepted_headers:
            errors.append(f"{label}.accepted_auth_headers must be a non-empty list")
            accepted_header_values: list[str] = []
        elif not all(isinstance(header, str) and header for header in accepted_headers):
            errors.append(f"{label}.accepted_auth_headers entries must be non-empty strings")
            accepted_header_values = []
        else:
            accepted_header_values = accepted_headers
        preferred_header = route.get("preferred_auth_header")
        if not isinstance(preferred_header, str) or preferred_header not in accepted_header_values:
            errors.append(f"{label}.preferred_auth_header must be listed in accepted_auth_headers")
        smoke_probe_path = route.get("smoke_probe_path")
        if not isinstance(smoke_probe_path, str) or not smoke_probe_path.startswith("/") or "://" in smoke_probe_path:
            errors.append(f"{label}.smoke_probe_path must be an absolute API path")
        forbidden_hosts = route.get("forbidden_hosts")
        if not isinstance(forbidden_hosts, list) or not forbidden_hosts:
            errors.append(f"{label}.forbidden_hosts must be a non-empty list")
        elif not all(isinstance(host, str) and host for host in forbidden_hosts):
            errors.append(f"{label}.forbidden_hosts entries must be non-empty strings")
        for text_field in ("confirmation", "output_policy"):
            if not isinstance(route.get(text_field), str) or not route[text_field]:
                errors.append(f"{label}.{text_field} must be a non-empty string")
    return errors


def validate_secret_name(secret_name: str, catalog: dict[str, Any]) -> None:
    """Validate an Infisical secret key name without inspecting a value."""

    policy = catalog.get("secret_name_policy", {})
    pattern = str(policy.get("pattern", ""))
    if not re.fullmatch(pattern, secret_name):
        raise SecretFactoryError("secret_name violates catalog pattern")
    for fragment in policy.get("forbidden_fragments", []):
        if isinstance(fragment, str) and fragment in secret_name:
            raise SecretFactoryError("secret_name contains a forbidden fragment")


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int, field: str) -> int:
    if value is None:
        return default
    if not isinstance(value, int):
        raise SecretFactoryError(f"{field} must be an integer")
    if value < minimum or value > maximum:
        raise SecretFactoryError(f"{field} is outside the allowed range")
    return value


def generate_secret_value(kind: str, request: dict[str, Any], catalog: dict[str, Any]) -> str:
    """Generate an allowed value in process memory."""

    generators = _allowed_generators(catalog)
    if kind not in generators:
        raise SecretFactoryError("generator kind is not allowed")
    spec = generators[kind]

    if kind == "random_base64url":
        default_bytes = _catalog_int(spec, "default_bytes", kind=kind)
        min_bytes = _catalog_int(spec, "min_bytes", kind=kind)
        max_bytes = _catalog_int(spec, "max_bytes", kind=kind)
        if None in {default_bytes, min_bytes, max_bytes}:
            raise SecretFactoryError(f"{kind} catalog bounds are invalid")
        nbytes = _bounded_int(
            request.get("bytes"),
            default=default_bytes,
            minimum=min_bytes,
            maximum=max_bytes,
            field="bytes",
        )
        return base64.urlsafe_b64encode(secrets.token_bytes(nbytes)).decode("ascii").rstrip("=")
    if kind == "random_hex":
        default_bytes = _catalog_int(spec, "default_bytes", kind=kind)
        min_bytes = _catalog_int(spec, "min_bytes", kind=kind)
        max_bytes = _catalog_int(spec, "max_bytes", kind=kind)
        if None in {default_bytes, min_bytes, max_bytes}:
            raise SecretFactoryError(f"{kind} catalog bounds are invalid")
        nbytes = _bounded_int(
            request.get("bytes"),
            default=default_bytes,
            minimum=min_bytes,
            maximum=max_bytes,
            field="bytes",
        )
        return secrets.token_hex(nbytes)
    if kind == "random_password":
        default_length = _catalog_int(spec, "default_length", kind=kind)
        min_length = _catalog_int(spec, "min_length", kind=kind)
        max_length = _catalog_int(spec, "max_length", kind=kind)
        alphabet_name = spec.get("alphabet")
        if None in {default_length, min_length, max_length} or not isinstance(alphabet_name, str):
            raise SecretFactoryError(f"{kind} catalog bounds are invalid")
        alphabet = PASSWORD_ALPHABETS.get(alphabet_name)
        if alphabet is None:
            raise SecretFactoryError(f"{kind} alphabet is not supported")
        length = _bounded_int(
            request.get("length"),
            default=default_length,
            minimum=min_length,
            maximum=max_length,
            field="length",
        )
        return "".join(secrets.choice(alphabet) for _ in range(length))

    raise SecretFactoryError("generator kind is not implemented")


def _json_output(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, sort_keys=True))


def names_only_handoff_readiness(catalog: dict[str, Any], *, provider: str | None = None) -> dict[str, Any]:
    """Return names-only Infisical handoff refs and no live secret existence claim."""

    errors = validate_names_only_handoff_refs(catalog)
    if errors:
        raise SecretFactoryError("names-only handoff refs are invalid")
    if provider is not None and not PROVIDER_NAME_RE.fullmatch(provider):
        raise SecretFactoryError("provider filter must be a stable lowercase provider id")
    refs = catalog["names_only_handoff_refs"]["refs"]
    routing = catalog["names_only_handoff_refs"].get("provider_api_routing", {})
    resolution = catalog["names_only_handoff_refs"].get("unconfirmed_ref_resolution", {})
    represented_refs = []
    ready_refs = []
    for ref in refs:
        if provider is not None and ref["provider"] != provider:
            continue
        represented = {
            "provider": ref["provider"],
            "secret_name": ref["secret_name"],
            "secret_path": ref["secret_path"],
            "handoff_owner": ref["handoff_owner"],
            "existence_status": ref["existence_status"],
        }
        if ref["existence_status"] == UNCONFIRMED_REF_STATUS:
            represented.update(
                {
                    "confirmation_required_before_use": True,
                    "required_before_task_ids": resolution.get("required_before_task_ids", []),
                    "allowed_confirmation_methods": resolution.get("allowed_confirmation_methods", []),
                    "forbidden_methods": resolution.get("forbidden_methods", []),
                }
            )
        if ref["existence_status"] == CONFIRMED_LIVE_REF_STATUS:
            represented["confirmation_required_before_use"] = False
            if isinstance(routing, dict) and ref["provider"] in routing:
                represented["provider_api_routing"] = routing[ref["provider"]]
            ready_refs.append(
                {
                    "provider": ref["provider"],
                    "secret_name": ref["secret_name"],
                    "secret_path": ref["secret_path"],
                    "action": "use_exact_infisical_ref_for_provider_api_without_token_output",
                }
            )
        represented_refs.append(represented)
    operator_required = [
        {
            "provider": ref["provider"],
            "secret_name": ref["secret_name"],
            "secret_path": ref["secret_path"],
            "action": (
                "confirm_exact_ref_or_metadata_only_names_before_task"
                if ref["existence_status"] == UNCONFIRMED_REF_STATUS
                else "create_or_confirm_in_infisical_without_value_readback"
            ),
        }
        for ref in represented_refs
        if ref["existence_status"] != CONFIRMED_LIVE_REF_STATUS
    ]
    return {
        "status": "OPERATOR_HANDOFF_REQUIRED" if operator_required else "READY_WITH_INFISICAL_REF",
        "metadata_only": True,
        "secret_values_printed": False,
        "infisical_readback": "forbidden",
        "live_infisical_existence_checked": False,
        "existence_reason": catalog["names_only_handoff_refs"]["reason"],
        "represented_refs": represented_refs,
        "ready_refs": ready_refs,
        "operator_required": operator_required,
    }


def _safe_secret_path(raw_path: str | None, catalog: dict[str, Any]) -> str:
    default_path = (_secret_manager_create_target(catalog) or {}).get("default_secret_path", "/")
    if raw_path is not None and not isinstance(raw_path, str):
        raise SecretFactoryError("secret_path must be a string")
    env_path = os.environ.get("INFISICAL_SECRET_PATH")
    path = raw_path or env_path or str(default_path)
    if not path.startswith("/") or ".." in Path(path).parts:
        raise SecretFactoryError("secret_path must be an absolute Infisical path without parent traversal")
    return path


def classify_request(request: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    """Classify a request as allowed or provider handoff."""

    _validate_request_payload(request)
    secret_name = request.get("secret_name")
    kind = request.get("kind")
    if not isinstance(secret_name, str) or not secret_name:
        raise SecretFactoryError("secret_name is required")
    if not isinstance(kind, str) or not kind:
        raise SecretFactoryError("kind is required")
    validate_secret_name(secret_name, catalog)
    secret_path = _safe_secret_path(request.get("secret_path"), catalog)

    generators = _allowed_generators(catalog)
    if kind in generators:
        return {
            "status": "ALLOWED",
            "secret_name": secret_name,
            "generator_kind": kind,
            "secret_path": secret_path,
            "provider_handoff": None,
        }

    refusal = _refusal_classes(catalog).get(kind)
    if refusal:
        handoff = {
            "status": catalog.get("provider_handoff", {}).get("status", "HANDOFF_REQUIRED"),
            "secret_name": secret_name,
            "requested_kind": kind,
            "handoff_owner": refusal["handoff_owner"],
            "target_project_id_present": bool(os.environ.get("INFISICAL_PROJECT_ID")),
            "target_environment": os.environ.get("INFISICAL_ENVIRONMENT", request.get("environment", "")),
            "secret_path": secret_path,
            "reason": refusal["reason"],
        }
        raise RefusalError(handoff)

    raise SecretFactoryError("kind is neither allowed nor configured for handoff")


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SecretFactoryError(f"required environment variable is missing: {name}")
    return value


def write_to_infisical(
    *,
    secret_name: str,
    secret_value: str,
    secret_path: str,
    catalog: dict[str, Any],
    opener: Any = urllib.request.urlopen,
) -> None:
    """POST a generated value to Infisical without printing or reading it back."""

    target = _secret_manager_create_target(catalog)
    api_url = _validated_infisical_api_url(catalog)
    token = _required_env("INFISICAL_TOKEN")
    project_id = _required_env("INFISICAL_PROJECT_ID")
    environment = _required_env("INFISICAL_ENVIRONMENT")
    encoded_name = urllib.parse.quote(secret_name, safe="")
    endpoint_template = str(target.get("create_endpoint_template", "/api/v4/secrets/{secretName}"))
    url = f"{api_url}{endpoint_template.replace('{secretName}', encoded_name)}"
    body = {
        "projectId": project_id,
        "environment": environment,
        "secretValue": secret_value,
        "secretPath": secret_path,
        "secretComment": "Created by Bears Secret Factory write-only path.",
        "skipMultilineEncoding": True,
        "type": "shared",
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        request_opener = _open_without_redirects if opener is urllib.request.urlopen else opener
        response = request_opener(request, timeout=30)
        response_url = getattr(response, "geturl", lambda: url)()
        if urllib.parse.urlsplit(str(response_url)).hostname not in {urllib.parse.urlsplit(url).hostname, None}:
            raise SecretFactoryError("Infisical create request redirected to an unexpected host")
        close = getattr(response, "close", None)
        if callable(close):
            close()
    except urllib.error.HTTPError as exc:
        raise SecretFactoryError(f"Infisical create request failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SecretFactoryError("Infisical create request failed at transport layer") from exc


def create_secret(request: dict[str, Any], catalog: dict[str, Any], *, dry_run: bool = False, opener: Any = urllib.request.urlopen) -> dict[str, Any]:
    """Create an allowed secret and return presence-only status."""

    plan = classify_request(request, catalog)
    if dry_run:
        return {**plan, "status": "DRY_RUN_ALLOWED"}

    value = generate_secret_value(plan["generator_kind"], request, catalog)
    try:
        write_to_infisical(
            secret_name=plan["secret_name"],
            secret_value=value,
            secret_path=plan["secret_path"],
            catalog=catalog,
            opener=opener,
        )
    finally:
        value = ""
    return {**plan, "status": "CREATED"}


def _load_request(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SecretFactoryError("request file must contain a JSON object")
    _validate_request_payload(payload)
    return payload


def _contains_forbidden_request_field(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and _is_forbidden_request_key(key):
                return True
            if _contains_forbidden_request_field(child):
                return True
    if isinstance(value, list):
        return any(_contains_forbidden_request_field(item) for item in value)
    return False


def _cmd_validate(_args: argparse.Namespace) -> int:
    errors = validate_catalog(load_catalog())
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: secret factory catalog valid")
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    request = _load_request(args.request)
    try:
        packet = classify_request(request, catalog)
    except RefusalError as exc:
        _json_output({"status": "HANDOFF_REQUIRED", "provider_handoff": exc.packet})
        return 2
    _json_output(packet)
    return 0


def _cmd_create(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    request = _load_request(args.request)
    try:
        packet = create_secret(request, catalog, dry_run=args.dry_run)
    except RefusalError as exc:
        _json_output({"status": "HANDOFF_REQUIRED", "provider_handoff": exc.packet})
        return 2
    _json_output(packet)
    return 0


def _cmd_handoff_readiness(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    packet = names_only_handoff_readiness(catalog, provider=args.provider)
    _json_output(packet)
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bears write-only Secret Factory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate the Secret Factory catalog")
    validate.set_defaults(func=_cmd_validate)

    plan = subparsers.add_parser("plan", help="classify a request without generating a value")
    plan.add_argument("request", help="JSON request file without value-bearing fields")
    plan.set_defaults(func=_cmd_plan)

    create = subparsers.add_parser("create", help="create an allowed value and write it to Infisical")
    create.add_argument("request", help="JSON request file without value-bearing fields")
    create.add_argument("--dry-run", action="store_true", help="validate and report without generating or writing")
    create.set_defaults(func=_cmd_create)

    readiness = subparsers.add_parser(
        "handoff-readiness",
        help="report cataloged names-only Infisical handoff refs without readback",
    )
    readiness.add_argument("--provider", help="optional lowercase provider id filter")
    readiness.set_defaults(func=_cmd_handoff_readiness)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return int(args.func(args))
    except SecretFactoryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
