"""Validate the plugin JSON Schema subset without third-party packages."""

from __future__ import annotations

import json
import re
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SchemaIssue:
    """Validation issue with a stable packet path and message."""

    path: list[str | int]
    message: str


def validate_json_schema(packet: Any, schema_path: Path, label: str) -> list[str]:
    """Validate a packet against the local schema subset used by this plugin."""
    schema = _load_json(schema_path)
    if not isinstance(schema, dict):
        return [f"{label}.<root>: schema must be an object"]
    issues = _validate_schema_node(packet, schema, schema, [])
    return [
        f"{label}.{_render_path(issue.path)}: {issue.message}"
        for issue in sorted(issues, key=lambda row: [str(part) for part in row.path])
    ]


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _render_path(path: list[str | int]) -> str:
    if not path:
        return "<root>"
    rendered = ""
    for part in path:
        if isinstance(part, int):
            rendered += f"[{part}]"
        elif rendered:
            rendered += f".{part}"
        else:
            rendered = str(part)
    return rendered


def _json_type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _json_type_name(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if value is None:
        return "null"
    return type(value).__name__


def _resolve_schema_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        return {}
    current: Any = root_schema
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict):
            return {}
        current = current.get(part)
    return current if isinstance(current, dict) else {}


def _validate_schema_node(
    value: Any,
    schema: Any,
    root_schema: dict[str, Any],
    path: list[str | int],
) -> list[SchemaIssue]:
    if schema is True:
        return []
    if schema is False:
        return [SchemaIssue(path, "is not allowed")]
    if not isinstance(schema, dict):
        return []

    if "$ref" in schema:
        ref_schema = _resolve_schema_ref(root_schema, str(schema["$ref"]))
        return _validate_schema_node(value, ref_schema, root_schema, path)

    errors: list[SchemaIssue] = []
    errors.extend(_validate_value_keywords(value, schema, path))

    expected_type = schema.get("type")
    expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
    if expected_type is not None and not any(
        isinstance(item, str) and _json_type_matches(value, item) for item in expected_types
    ):
        errors.append(SchemaIssue(path, f"must be {expected_type}, got {_json_type_name(value)}"))
        return errors

    errors.extend(_validate_object(value, schema, root_schema, path))
    errors.extend(_validate_array(value, schema, root_schema, path))
    errors.extend(_validate_string(value, schema, path))
    errors.extend(_validate_numeric(value, schema, path))
    errors.extend(_validate_composition(value, schema, root_schema, path))
    return errors


def _validate_value_keywords(value: Any, schema: dict[str, Any], path: list[str | int]) -> list[SchemaIssue]:
    errors: list[SchemaIssue] = []
    if "const" in schema and value != schema["const"]:
        errors.append(SchemaIssue(path, f"must equal {schema['const']!r}"))
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        errors.append(SchemaIssue(path, "must be one of " + ", ".join(repr(item) for item in enum_values)))
    return errors


def _validate_object(
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: list[str | int],
) -> list[SchemaIssue]:
    if not isinstance(value, dict):
        return []
    errors: list[SchemaIssue] = []
    required = schema.get("required", [])
    if isinstance(required, list):
        for field in required:
            if isinstance(field, str) and field not in value:
                errors.append(SchemaIssue(path + [field], "is required"))
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return errors
    for field, field_schema in properties.items():
        if field in value:
            errors.extend(_validate_schema_node(value[field], field_schema, root_schema, path + [field]))
    additional = schema.get("additionalProperties", True)
    for field, field_value in value.items():
        if field in properties:
            continue
        if additional is False:
            errors.append(SchemaIssue(path + [field], "is not an allowed property"))
        elif isinstance(additional, dict):
            errors.extend(_validate_schema_node(field_value, additional, root_schema, path + [field]))
    return errors


def _validate_array(
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: list[str | int],
) -> list[SchemaIssue]:
    if not isinstance(value, list):
        return []
    errors: list[SchemaIssue] = []
    min_items = schema.get("minItems")
    if isinstance(min_items, int) and len(value) < min_items:
        errors.append(SchemaIssue(path, f"must contain at least {min_items} items"))
    if schema.get("uniqueItems") is True:
        seen: set[str] = set()
        for item in value:
            marker = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if marker in seen:
                errors.append(SchemaIssue(path, "must contain unique items"))
                break
            seen.add(marker)
    item_schema = schema.get("items")
    if item_schema is not None:
        for index, item in enumerate(value):
            errors.extend(_validate_schema_node(item, item_schema, root_schema, path + [index]))
    return errors


def _validate_string(value: Any, schema: dict[str, Any], path: list[str | int]) -> list[SchemaIssue]:
    if not isinstance(value, str):
        return []
    errors: list[SchemaIssue] = []
    min_length = schema.get("minLength")
    if isinstance(min_length, int) and len(value) < min_length:
        errors.append(SchemaIssue(path, f"must contain at least {min_length} characters"))
    pattern = schema.get("pattern")
    if isinstance(pattern, str) and re.search(pattern, value) is None:
        errors.append(SchemaIssue(path, f"must match pattern {pattern}"))
    schema_format = schema.get("format")
    if schema_format == "date-time" and not _is_date_time(value):
        errors.append(SchemaIssue(path, "must be a valid date-time"))
    elif schema_format == "uri" and not _is_uri(value):
        errors.append(SchemaIssue(path, "must be a valid uri"))
    return errors


def _is_date_time(value: str) -> bool:
    if "T" not in value:
        return False
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return True


def _is_uri(value: str) -> bool:
    return re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://[^\s]+$", value) is not None


def _validate_numeric(value: Any, schema: dict[str, Any], path: list[str | int]) -> list[SchemaIssue]:
    minimum = schema.get("minimum")
    if isinstance(minimum, (int, float)) and isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < minimum:
            return [SchemaIssue(path, f"must be greater than or equal to {minimum}")]
    return []


def _validate_composition(
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: list[str | int],
) -> list[SchemaIssue]:
    errors: list[SchemaIssue] = []
    not_schema = schema.get("not")
    if isinstance(not_schema, dict) and not _validate_schema_node(value, not_schema, root_schema, path):
        errors.append(SchemaIssue(path, "must not match prohibited schema"))
    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        match_count = sum(
            1 for candidate in one_of if not _validate_schema_node(value, candidate, root_schema, path)
        )
        if match_count != 1:
            errors.append(SchemaIssue(path, "must match exactly one schema"))
    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for candidate in all_of:
            errors.extend(_validate_schema_node(value, candidate, root_schema, path))
    if_schema = schema.get("if")
    then_schema = schema.get("then")
    if isinstance(if_schema, dict) and isinstance(then_schema, dict):
        if not _validate_schema_node(value, if_schema, root_schema, path):
            errors.extend(_validate_schema_node(value, then_schema, root_schema, path))
    return errors
