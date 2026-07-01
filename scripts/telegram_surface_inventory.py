#!/usr/bin/env python3
"""Detect Telegram-like local code surfaces and verify catalog/backlog coverage."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PLUGIN_ROOT / "assets/catalog/telegram-workflow-catalog.v1.json"
DEFAULT_BACKLOG = PLUGIN_ROOT / "assets/catalog/telegram-aiogram-migration-backlog.v1.json"
DEFAULT_SCAN_ROOTS = ("projects",)
SUPPORTED_EXTENSIONS = {".py", ".js", ".mjs", ".ts", ".tsx"}
PRUNE_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "vendor",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
    "site-packages",
    "target",
    "tmp",
    "temp",
    "docs",
    "doc",
    "tests",
    "test",
    "specs",
    "plans",
    "runtime",
    "backups",
    "scripts",
}
PRUNE_FILE_PREFIXES = ("test_", "test-")
PRUNE_FILE_SUFFIXES = (
    "_test.py",
    ".test.py",
    ".spec.py",
    ".test.js",
    ".spec.js",
    ".test.mjs",
    ".spec.mjs",
    ".test.ts",
    ".spec.ts",
    ".test.tsx",
    ".spec.tsx",
)
MAX_READ_BYTES = 512 * 1024
BOT_API_ACTION_HINTS = {
    "sendmessage",
    "getupdates",
    "editmessagetext",
    "answercallbackquery",
    "sendphoto",
    "senddocument",
}
AIROGRAM_RUNTIME_HINTS = {
    "dispatcher(",
    "router(",
    "start_polling(",
    "setmycommands(",
    "callbackquery",
    "inlinekeyboardbutton",
    "inlinekeyboardmarkup",
    "replykeyboardmarkup",
    "messagehandler",
    "callbackqueryhandler",
    "fsmcontext",
}
TELEGRAF_RUNTIME_HINTS = {"new telegraf(", ".command(", ".start(", ".action(", ".on("}
TELETHON_RUNTIME_HINTS = {"events.newmessage", ".start(", "telegramclient("}
PYROGRAM_RUNTIME_HINTS = {"client(", "@app.on_message", "filters.command"}
PTB_RUNTIME_HINTS = {"application.builder(", "updater(", "commandhandler(", "callbackqueryhandler("}
BRIDGE_NAME_HINTS = {"bridge"}
NOTIFICATION_NAME_HINTS = {"notify", "notifier", "alert", "outbox"}
BOT_NAME_HINTS = {"bot", "telegram_bot", "tg_bot"}
INVENTORY_STATUS_FIELD = "inventory_coverage_status"
INVENTORY_ONLY_PREFIXES = ("deferred", "non-bot", "ignored", "inventory-only")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"json not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"json root must be object: {path}")
    return data


def normalize_relative_path(path: str | Path) -> PurePosixPath:
    if isinstance(path, Path):
        raw = path.as_posix()
    else:
        raw = str(path).replace("\\", "/")
    return PurePosixPath(raw.strip("/"))


def iter_scan_roots(workspace_root: Path) -> list[Path]:
    roots = [workspace_root / rel for rel in DEFAULT_SCAN_ROOTS if (workspace_root / rel).is_dir()]
    return roots or [workspace_root]


def should_prune_dir(name: str) -> bool:
    lowered = name.casefold()
    return lowered in {item.casefold() for item in PRUNE_DIR_NAMES} or lowered.startswith(".")


def should_skip_file(path: Path, workspace_root: Path) -> bool:
    name = path.name.casefold()
    if any(name.startswith(prefix) for prefix in PRUNE_FILE_PREFIXES):
        return True
    if any(name.endswith(suffix) for suffix in PRUNE_FILE_SUFFIXES):
        return True
    relative_parts = path.relative_to(workspace_root).parts
    return any(should_prune_dir(part) for part in relative_parts[:-1])


def iter_candidate_files(workspace_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for root in iter_scan_roots(workspace_root):
        for current_root, dir_names, file_names in os.walk(root):
            dir_names[:] = sorted(d for d in dir_names if not should_prune_dir(d))
            current_path = Path(current_root)
            for file_name in sorted(file_names):
                path = current_path / file_name
                if path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
                    continue
                if should_skip_file(path, workspace_root):
                    continue
                candidates.append(path)
    return candidates


def read_file_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_READ_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def has_any_token(text: str, tokens: set[str]) -> bool:
    return any(token in text for token in tokens)


def classify_file(path: Path) -> str | None:
    text = read_file_text(path)
    if text is None:
        return None

    lower = text.casefold()
    compact = "".join(lower.split())
    path_text = path.as_posix().casefold()
    name = path.name.casefold()
    stem = path.stem.casefold()
    bot_name_hint = any(token in stem for token in BOT_NAME_HINTS) or "/bot/" in path_text
    bridge_name_hint = any(token in stem for token in BRIDGE_NAME_HINTS)
    notification_name_hint = any(token in stem for token in NOTIFICATION_NAME_HINTS)
    runtime_name_hint = bot_name_hint or bridge_name_hint or notification_name_hint or name == "main.py"

    if ("from aiogram" in lower or "import aiogram" in lower) and (
        bot_name_hint or has_any_token(compact, AIROGRAM_RUNTIME_HINTS)
    ):
        return "bot-runtime-aiogram"

    if "telegraf" in lower and (bot_name_hint or has_any_token(compact, TELEGRAF_RUNTIME_HINTS)):
        return "bot-runtime-telegraf"

    if "telethon" in lower and (runtime_name_hint or has_any_token(compact, TELETHON_RUNTIME_HINTS)):
        return "non-bot-telethon-client"

    if "pyrogram" in lower and (runtime_name_hint or has_any_token(compact, PYROGRAM_RUNTIME_HINTS)):
        return "telegram-client-pyrogram"

    if ("telegram.ext" in lower or "python-telegram-bot" in lower) and (
        runtime_name_hint or has_any_token(compact, PTB_RUNTIME_HINTS)
    ):
        return "bot-runtime-python-telegram-bot"

    has_bot_api_endpoint = "api.telegram.org" in lower
    has_bot_api_action = has_any_token(compact, BOT_API_ACTION_HINTS)
    has_bridge_action = any(token in lower for token in ("bind_from_updates", "send_telegram", "append_outbox", "build_outbox_entries"))

    if has_bot_api_endpoint and (has_bot_api_action or has_bridge_action):
        if notification_name_hint or any(token in lower for token in ("append_outbox", "build_outbox_entries")):
            return "non-bot-notification-bridge"
        if bridge_name_hint or "bind_from_updates" in lower:
            return "non-bot-telegram-bridge"
        if bot_name_hint:
            return "telegram-api-bot-like"
        return None

    if runtime_name_hint and "telegram" in lower and ("send_message" in lower or "chat_id" in lower):
        if notification_name_hint:
            return "non-bot-notification-bridge"
        if bot_name_hint:
            return "bot-runtime-custom"
        if bridge_name_hint:
            return "non-bot-telegram-bridge"
        return "telegram-like-unknown"
    return None


def discover_surfaces(workspace_root: Path) -> list[dict[str, str]]:
    discoveries: list[dict[str, str]] = []
    for path in iter_candidate_files(workspace_root):
        classification = classify_file(path)
        if not classification:
            continue
        relative_path = path.relative_to(workspace_root).as_posix()
        discoveries.append({"path": relative_path, "classification": classification})
    discoveries.sort(key=lambda item: item["path"])
    return discoveries


def inventory_status_for_entry(entry: dict[str, Any]) -> str:
    raw = entry.get(INVENTORY_STATUS_FIELD, "core")
    return str(raw) if raw else "core"


def registry_entries(catalog: dict[str, Any], backlog: dict[str, Any]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for item in catalog.get("surfaces", []):
        if isinstance(item, dict) and item.get("path"):
            entries.append(
                {
                    "registry": "workflow-catalog",
                    "surface": str(item.get("name")),
                    "path": str(item.get("path")),
                    "status": str(item.get("migration_status", "unknown")),
                    "inventory_status": inventory_status_for_entry(item),
                }
            )
    for item in backlog.get("items", []):
        if isinstance(item, dict) and item.get("path"):
            entries.append(
                {
                    "registry": "migration-backlog",
                    "surface": str(item.get("surface")),
                    "path": str(item.get("path")),
                    "status": str(item.get("migration_status", "unknown")),
                    "inventory_status": inventory_status_for_entry(item),
                }
            )
    return entries


def count_registry_partition(items: list[dict[str, Any]], *, item_key: str) -> dict[str, int]:
    counts = {"core": 0, "inventory_only": 0}
    for item in items:
        if not isinstance(item, dict) or item_key not in item:
            continue
        status = inventory_status_for_entry(item)
        if any(status.startswith(prefix) for prefix in INVENTORY_ONLY_PREFIXES):
            counts["inventory_only"] += 1
        else:
            counts["core"] += 1
    return counts


def find_matches(discovered_path: str, entries: list[dict[str, str]]) -> list[dict[str, str]]:
    discovered = normalize_relative_path(discovered_path)
    matches: list[dict[str, str]] = []
    for entry in entries:
        candidate = normalize_relative_path(entry["path"])
        if candidate == discovered or candidate in discovered.parents:
            matches.append(entry)
    matches.sort(
        key=lambda item: (len(item["path"]), item["registry"], item["surface"]),
        reverse=True,
    )
    return matches


def evaluate_inventory(
    workspace_root: Path,
    catalog: dict[str, Any],
    backlog: dict[str, Any],
) -> dict[str, Any]:
    discoveries = discover_surfaces(workspace_root)
    entries = registry_entries(catalog, backlog)
    covered: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []
    classification_counts: Counter[str] = Counter()
    for item in discoveries:
        classification_counts[item["classification"]] += 1
        matches = find_matches(item["path"], entries)
        result = {**item, "matches": matches}
        if matches:
            covered.append(result)
        else:
            uncovered.append(result)

    catalog_partition = count_registry_partition(catalog.get("surfaces", []), item_key="name")
    backlog_partition = count_registry_partition(backlog.get("items", []), item_key="surface")

    return {
        "workspace_root": workspace_root.as_posix(),
        "catalog_surface_count": len(catalog.get("surfaces", [])),
        "catalog_core_surface_count": catalog_partition["core"],
        "catalog_inventory_only_surface_count": catalog_partition["inventory_only"],
        "backlog_item_count": len(backlog.get("items", [])),
        "backlog_core_item_count": backlog_partition["core"],
        "backlog_inventory_only_item_count": backlog_partition["inventory_only"],
        "discovered_count": len(discoveries),
        "covered_count": len(covered),
        "uncovered_count": len(uncovered),
        "classification_counts": dict(sorted(classification_counts.items())),
        "covered": covered,
        "uncovered": uncovered,
    }


def render_summary(report: dict[str, Any]) -> str:
    lines = [
        f"workspace_root: {report['workspace_root']}",
        f"catalog_surfaces: {report['catalog_surface_count']}",
        f"catalog_core_surfaces: {report['catalog_core_surface_count']}",
        f"catalog_inventory_only_surfaces: {report['catalog_inventory_only_surface_count']}",
        f"backlog_items: {report['backlog_item_count']}",
        f"backlog_core_items: {report['backlog_core_item_count']}",
        f"backlog_inventory_only_items: {report['backlog_inventory_only_item_count']}",
        f"discovered_paths: {report['discovered_count']}",
        f"covered_paths: {report['covered_count']}",
        f"uncovered_paths: {report['uncovered_count']}",
        "",
        "classification_counts:",
    ]
    for classification, count in report["classification_counts"].items():
        lines.append(f"- {classification}: {count}")
    lines.append("")
    lines.append("discoveries:")
    for collection_name in ("covered", "uncovered"):
        for item in report[collection_name]:
            match_names = ",".join(
                f"{match['registry']}:{match['surface']}[{match['status']};{match['inventory_status']}]"
                for match in item["matches"]
            )
            if not match_names:
                match_names = "none"
            status = "covered" if collection_name == "covered" else "uncovered"
            lines.append(
                f"- {status} | path={item['path']} | classification={item['classification']} | coverage={match_names}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "summary", "json"])
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--backlog", type=Path, default=DEFAULT_BACKLOG)
    args = parser.parse_args(argv)

    try:
        catalog = load_json(args.catalog)
        backlog = load_json(args.backlog)
        report = evaluate_inventory(args.workspace_root, catalog, backlog)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.command == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    summary = render_summary(report)
    if args.command == "summary":
        print(summary)
        return 0

    if report["uncovered"]:
        print(summary, file=sys.stderr)
        return 1

    print(summary)
    print("inventory ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
