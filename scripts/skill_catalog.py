#!/usr/bin/env python3
"""Validate and generate Bears plugin skill inventory fragments."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "assets" / "catalog" / "plugin-skill-catalog.v1.json"
ROLE_CATALOG_PATH = PLUGIN_ROOT / "assets" / "catalog" / "platform-role-catalog.v1.json"
ROLE_ROUTER_PATH = PLUGIN_ROOT / "scripts" / "subagents_roles.py"
ACTIVE_FILE = "SKILL.md"
DISABLED_FILE = "SKILL.disabled.md"
INVENTORY_START = "<!-- BEARS_SKILL_INVENTORY: START -->"
INVENTORY_END = "<!-- BEARS_SKILL_INVENTORY: END -->"


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    """Load the skill catalog JSON object."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("skill catalog root must be an object")
    return data


def _entry_map(entries: Any, section: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(entries, list):
        errors.append(f"{section} must be a list")
        return {}

    result: dict[str, dict[str, Any]] = {}
    seen_paths: dict[str, str] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"{section}[{index}] must be an object")
            continue
        name = entry.get("name")
        path = entry.get("path")
        description = entry.get("description") if section == "active_skills" else entry.get("reason")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{section}[{index}].name must be a non-empty string")
            continue
        if not isinstance(path, str) or not path.startswith("skills/"):
            errors.append(f"{section}.{name}.path must be a skills/ relative path")
            continue
        if not isinstance(description, str) or not description.strip():
            field = "description" if section == "active_skills" else "reason"
            errors.append(f"{section}.{name}.{field} must be a non-empty string")
        if name in result:
            errors.append(f"duplicate skill name in {section}: {name}")
        if path in seen_paths:
            errors.append(f"duplicate skill path in catalog: {path} used by {seen_paths[path]} and {name}")
        result[name] = entry
        seen_paths[path] = name
    return result


def _has_frontmatter(path: Path) -> bool:
    return path.read_text(encoding="utf-8").lstrip().startswith("---")


def _frontmatter_contains_name(path: Path, name: str) -> bool:
    text = path.read_text(encoding="utf-8")
    allowed = {f"name: {name}", f"name: \"{name}\"", f"name: '{name}'"}
    return any(line.strip() in allowed for line in text.splitlines())


def _load_platform_roles(plugin_root: Path) -> Any | None:
    """Load the local platform role router when the full plugin tree is present."""

    router_path = plugin_root / ROLE_ROUTER_PATH.relative_to(PLUGIN_ROOT)
    role_catalog_path = plugin_root / ROLE_CATALOG_PATH.relative_to(PLUGIN_ROOT)
    if not router_path.is_file() or not role_catalog_path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("bears_platform_roles_for_skill_catalog", router_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load platform role router: {router_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    required_attrs = ("load_json", "validate_catalog", "route_target")
    if not all(hasattr(module, attr) for attr in required_attrs):
        return None
    return module


def validate_active_skill_route_coverage(
    catalog: dict[str, Any], plugin_root: Path = PLUGIN_ROOT
) -> list[str]:
    """Require every active skill's exact SKILL.md file to route under a valid role catalog."""

    platform_roles = _load_platform_roles(plugin_root)
    if platform_roles is None:
        return []

    role_catalog_path = plugin_root / ROLE_CATALOG_PATH.relative_to(PLUGIN_ROOT)
    role_catalog = platform_roles.load_json(role_catalog_path)
    role_errors = platform_roles.validate_catalog(role_catalog, plugin_root=plugin_root)
    errors: list[str] = []
    if role_errors:
        errors.append("subagents roles catalog invalid while checking active skill routes: " + "; ".join(role_errors))
        return errors
    for entry in catalog.get("active_skills", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        rel_target = f"{entry['path']}/{ACTIVE_FILE}"
        target = str(plugin_root / rel_target)
        route_packet = platform_roles.route_target(role_catalog, target, plugin_root=plugin_root)
        if route_packet.get("status") != "matched":
            errors.append(
                "active skill exact route must match: "
                f"{rel_target} -> {route_packet.get('status')}:{route_packet.get('why_blocked')}"
            )
    return errors


def validate_catalog(catalog: dict[str, Any], plugin_root: Path = PLUGIN_ROOT) -> list[str]:
    """Return deterministic validation errors for skill catalog and filesystem state."""

    errors: list[str] = []
    if catalog.get("schema") != "bears-plugin-skill-catalog.v1":
        errors.append("schema must be bears-plugin-skill-catalog.v1")
    if catalog.get("owner_plugin") != "bears":
        errors.append("owner_plugin must be bears")

    policy = catalog.get("discovery_policy")
    if not isinstance(policy, dict):
        errors.append("discovery_policy must be an object")
        policy = {}
    if policy.get("active_skill_file") != ACTIVE_FILE:
        errors.append(f"discovery_policy.active_skill_file must be {ACTIVE_FILE}")
    if policy.get("disabled_skill_file") != DISABLED_FILE:
        errors.append(f"discovery_policy.disabled_skill_file must be {DISABLED_FILE}")
    if policy.get("manifest_skill_root") != "./skills/":
        errors.append("discovery_policy.manifest_skill_root must be ./skills/")

    active = _entry_map(catalog.get("active_skills"), "active_skills", errors)
    disabled = _entry_map(catalog.get("disabled_skills"), "disabled_skills", errors)
    overlap = set(active) & set(disabled)
    for name in sorted(overlap):
        errors.append(f"skill cannot be both active and disabled: {name}")

    skills_root = plugin_root / "skills"
    if not skills_root.is_dir():
        errors.append("skills directory is missing")
        return errors

    catalog_paths = {entry["path"] for entry in active.values()} | {entry["path"] for entry in disabled.values()}
    actual_paths = {f"skills/{path.name}" for path in skills_root.iterdir() if path.is_dir()}
    for path in sorted(actual_paths - catalog_paths):
        errors.append(f"skill directory missing from catalog: {path}")
    for path in sorted(catalog_paths - actual_paths):
        errors.append(f"catalog skill path missing on disk: {path}")

    for name, entry in sorted(active.items()):
        skill_dir = plugin_root / entry["path"]
        active_file = skill_dir / ACTIVE_FILE
        disabled_file = skill_dir / DISABLED_FILE
        if not active_file.is_file():
            errors.append(f"active skill missing {ACTIVE_FILE}: {entry['path']}")
        elif not _has_frontmatter(active_file):
            errors.append(f"active skill must expose frontmatter: {entry['path']}/{ACTIVE_FILE}")
        elif not _frontmatter_contains_name(active_file, name):
            errors.append(f"active skill frontmatter name mismatch: {entry['path']}/{ACTIVE_FILE}")
        if disabled_file.exists():
            errors.append(f"active skill must not keep disabled doc: {entry['path']}/{DISABLED_FILE}")

    for name, entry in sorted(disabled.items()):
        skill_dir = plugin_root / entry["path"]
        active_file = skill_dir / ACTIVE_FILE
        disabled_file = skill_dir / DISABLED_FILE
        if active_file.exists():
            errors.append(f"disabled skill must not expose {ACTIVE_FILE}: {entry['path']}/{ACTIVE_FILE}")
        if not disabled_file.is_file():
            errors.append(f"disabled skill missing preserved doc: {entry['path']}/{DISABLED_FILE}")
        elif not _has_frontmatter(disabled_file):
            errors.append(f"disabled skill preserved doc must keep frontmatter: {entry['path']}/{DISABLED_FILE}")
        elif not _frontmatter_contains_name(disabled_file, name):
            errors.append(f"disabled skill frontmatter name mismatch: {entry['path']}/{DISABLED_FILE}")

    fragments = catalog.get("generated_fragments")
    if not isinstance(fragments, dict):
        errors.append("generated_fragments must be an object")
    else:
        for key in ("readme", "spec"):
            value = fragments.get(key)
            if not isinstance(value, str) or not value.startswith("docs/generated/"):
                errors.append(f"generated_fragments.{key} must be a docs/generated/ relative path")

    errors.extend(validate_active_skill_route_coverage(catalog, plugin_root))

    return errors


def render_readme_fragment(catalog: dict[str, Any]) -> str:
    """Render the README skill inventory fragment from the catalog."""

    lines = [
        "<!-- generated by scripts/skill_catalog.py; edit assets/catalog/plugin-skill-catalog.v1.json -->",
        "# Generated Bears skill inventory",
        "",
        "Canonical catalog: `assets/catalog/plugin-skill-catalog.v1.json`.",
        "",
        "Active skills expose `SKILL.md` and are discoverable by the plugin loader.",
        "",
        "## Active skills",
        "",
    ]
    for entry in catalog["active_skills"]:
        lines.append(f"- `{entry['path']}` — {entry['description']}")
    if catalog["disabled_skills"]:
        lines.extend(["", "## Disabled preserved skill docs"])
        for entry in catalog["disabled_skills"]:
            lines.append(f"- `{entry['path']}/SKILL.disabled.md` — {entry['reason']}")
    return "\n".join(lines) + "\n"


def render_spec_fragment(catalog: dict[str, Any]) -> str:
    """Render the SPEC skill boundary fragment from the catalog."""

    active_names = ", ".join(f"`{entry['name']}`" for entry in catalog["active_skills"])
    lines = [
        "<!-- generated by scripts/skill_catalog.py; edit assets/catalog/plugin-skill-catalog.v1.json -->",
        "# Generated skill discovery boundary",
        "",
        "`assets/catalog/plugin-skill-catalog.v1.json` is the single source of truth for active Bears plugin skills.",
        "",
        f"Active discoverable skills: {active_names}.",
    ]
    if catalog["disabled_skills"]:
        disabled_names = ", ".join(f"`{entry['name']}`" for entry in catalog["disabled_skills"])
        lines.extend([
            "",
            f"Disabled preserved skill docs: {disabled_names}.",
            "",
            "A disabled skill directory is valid only when `SKILL.md` is absent and `SKILL.disabled.md` is present.",
        ])
    return "\n".join(lines) + "\n"


def generated_paths(catalog: dict[str, Any], plugin_root: Path = PLUGIN_ROOT) -> dict[str, Path]:
    """Resolve generated fragment paths from the catalog."""

    fragments = catalog.get("generated_fragments", {})
    return {
        "readme": plugin_root / fragments.get("readme", "docs/generated/README.skill-inventory.md"),
        "spec": plugin_root / fragments.get("spec", "docs/generated/SPEC.skill-inventory.md"),
    }



def generate(catalog: dict[str, Any], plugin_root: Path = PLUGIN_ROOT, *, check: bool = False) -> list[str]:
    """Write or check generated README and SPEC fragments."""

    outputs = {
        "readme": render_readme_fragment(catalog),
        "spec": render_spec_fragment(catalog),
    }
    paths = generated_paths(catalog, plugin_root)
    errors: list[str] = []

    for key, text in outputs.items():
        path = paths[key]
        if check:
            if not path.is_file():
                errors.append(f"generated fragment missing: {path.relative_to(plugin_root)}")
                continue
            current = path.read_text(encoding="utf-8")
            if current != text:
                errors.append(f"generated fragment drift: {path.relative_to(plugin_root)}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    return errors


def _replace_embedded_block(current: str, fragment: str) -> tuple[str, bool]:
    start = current.find(INVENTORY_START)
    end = current.find(INVENTORY_END)
    if start == -1 or end == -1 or end < start:
        return current, False
    end += len(INVENTORY_END)
    replacement = f"{INVENTORY_START}\n{fragment.rstrip()}\n{INVENTORY_END}"
    return current[:start] + replacement + current[end:], True


def sync_embedded_owner_docs(catalog: dict[str, Any], plugin_root: Path = PLUGIN_ROOT, *, check: bool = False) -> list[str]:
    """Write or check embedded owner-doc inventory blocks against generated fragments."""

    errors: list[str] = []
    fragments = {
        "README.md": render_readme_fragment(catalog),
        "SPEC.md": render_spec_fragment(catalog),
    }
    for rel_path, fragment in fragments.items():
        path = plugin_root / rel_path
        if not path.is_file():
            errors.append(f"owner doc missing: {rel_path}")
            continue
        current = path.read_text(encoding="utf-8")
        updated, found = _replace_embedded_block(current, fragment)
        if not found:
            errors.append(f"owner doc inventory block missing: {rel_path}")
            continue
        if check:
            if current != updated:
                errors.append(f"owner doc inventory drift: {rel_path}")
            continue
        path.write_text(updated, encoding="utf-8")
    return errors


def _cmd_validate(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.catalog))
    errors = validate_catalog(catalog, Path(args.plugin_root))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"skill catalog ok: {args.catalog}")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    catalog = load_catalog(Path(args.catalog))
    errors = validate_catalog(catalog, Path(args.plugin_root))
    errors.extend(generate(catalog, Path(args.plugin_root), check=args.check))
    errors.extend(sync_embedded_owner_docs(catalog, Path(args.plugin_root), check=args.check))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.check:
        print("generated skill fragments ok")
    else:
        print("generated skill fragments updated")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default=str(CATALOG_PATH))
    parser.add_argument("--plugin-root", default=str(PLUGIN_ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate").set_defaults(func=_cmd_validate)
    generate_parser = sub.add_parser("generate")
    generate_parser.add_argument("--check", action="store_true")
    generate_parser.set_defaults(func=_cmd_generate)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the skill catalog CLI."""

    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
