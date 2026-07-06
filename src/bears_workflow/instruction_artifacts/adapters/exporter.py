#!/usr/bin/env python3
"""Export current local Codex/AGENTS instruction inheritance graphs as JSONL.

Each JSONL line is one complete inheritance graph for one discovered AGENTS.md
under the selected workspace root.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = "instruction-graph.v1"
DEFAULT_ROOT = Path("/srv/bears")
DEFAULT_CODEX_CONFIG = Path("/home/ai1/.codex/config.toml")
DEFAULT_PERSONAL_AGENTS = Path("/home/ai1/.codex/AGENTS.md")
AGENTS_NAME = "AGENTS.md"
LEVEL4_EXCEPTION_PARENT_NAMES = {"dev"}
MARKDOWN_REFERENCE_RE = re.compile(
    r"(?P<ref>(?:\$codex|\$workspace|/|\.{1,2}/)?"
    r"[A-Za-z0-9_@.+~*{}$/-]*"
    r"[A-Za-z0-9_@.+~*{}-]+\.m[dD]"
    r"(?:#[A-Za-z0-9_.:/%?=&-]+)?)"
)
GLOB_CHARS = set("*?[]{}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export one JSON instruction graph per discovered AGENTS.md. "
            "The graph preserves inheritance from personal instructions, "
            "developer instructions, root AGENTS.md, and path-local AGENTS.md files."
        )
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Workspace root to scan.")
    parser.add_argument(
        "--codex-config",
        type=Path,
        default=DEFAULT_CODEX_CONFIG,
        help="Codex config containing model_instructions_file.",
    )
    parser.add_argument(
        "--personal-agents",
        type=Path,
        default=DEFAULT_PERSONAL_AGENTS,
        help="Personal AGENTS.md file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSONL to this path instead of stdout.",
    )
    parser.add_argument(
        "--paths-only-output",
        type=Path,
        default=None,
        help="Also write lightweight JSONL containing only target and inherited paths.",
    )
    parser.add_argument(
        "--normalized-output",
        type=Path,
        default=None,
        help=(
            "Also write one normalized compact JSON object with unique parsed "
            "instruction docs and graph chains referencing integer doc ids."
        ),
    )
    parser.add_argument(
        "--include-untracked-level4",
        action="store_true",
        help=(
            "Include direct child Git repositories whose root AGENTS.md is not tracked. "
            "By default untracked root AGENTS.md files are skipped at level 4."
        ),
    )
    return parser.parse_args()


def read_text(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8", errors="replace"), "decoded_with_replacement"
        except OSError as exc:
            return None, f"read_failed:{exc.__class__.__name__}:{exc}"
    except OSError as exc:
        return None, f"read_failed:{exc.__class__.__name__}:{exc}"


def parse_model_instructions_file(config_path: Path) -> tuple[Path | None, list[str]]:
    warnings: list[str] = []
    text, warning = read_text(config_path)
    if warning:
        warnings.append(f"codex_config:{config_path}:{warning}")
    if text is None:
        return None, warnings

    match = re.search(r'(?m)^\s*model_instructions_file\s*=\s*["\']([^"\']+)["\']\s*$', text)
    if not match:
        warnings.append(f"codex_config:{config_path}:model_instructions_file_not_found")
        return None, warnings
    return Path(match.group(1)).expanduser(), warnings


def file_metadata(path: Path, node_id: str, layer: str) -> dict[str, object]:
    resolved_path = str(path)
    text, warning = read_text(path)
    exists = path.exists()

    stat = None
    if exists:
        try:
            stat = path.stat()
        except OSError as exc:
            warning = warning or f"stat_failed:{exc.__class__.__name__}:{exc}"

    if text is None:
        digest = None
        size = stat.st_size if stat else None
    else:
        encoded = text.encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        size = len(encoded)

    return {
        "id": node_id,
        "layer": layer,
        "path": resolved_path,
        "exists": exists,
        "sha256": digest,
        "mtime": dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat() if stat else None,
        "bytes": size,
        "text": text,
        "warning": warning,
    }


def count_lines(text: str | None) -> int:
    if text is None:
        return 0
    if text == "":
        return 0
    return len(text.splitlines())


def add_cumulative_metrics(nodes: list[dict[str, object]]) -> None:
    cumulative_lines = 0
    cumulative_chars = 0

    for level, node in enumerate(nodes, start=1):
        text = node.get("text")
        node_lines = count_lines(text if isinstance(text, str) else None)
        node_chars = len(text) if isinstance(text, str) else 0

        cumulative_lines += node_lines
        cumulative_chars += node_chars

        node["level"] = level
        node["line_count"] = node_lines
        node["char_count"] = node_chars
        node["cumulative_line_count"] = cumulative_lines
        node["cumulative_char_count"] = cumulative_chars


def git_repo_root(start: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def is_direct_git_repo(path: Path) -> bool:
    try:
        absolute_path = path.resolve()
    except OSError:
        return False
    repo_root = git_repo_root(absolute_path)
    return repo_root == absolute_path


def discover_direct_child_git_agents(
    parent: Path,
    *,
    level_name: str,
    include_untracked: bool,
) -> tuple[list[Path], list[Path], list[str]]:
    agents_paths: list[Path] = []
    repo_roots: list[Path] = []
    warnings: list[str] = []
    skipped_untracked = 0

    for child in sorted(parent.iterdir(), key=lambda item: str(item)):
        if not child.is_dir() or child.name == ".git":
            continue
        if not is_direct_git_repo(child):
            continue

        candidate = child / AGENTS_NAME
        if not candidate.exists():
            warnings.append(f"{level_name}_git_repo:{child}:agents_missing")
            continue
        if not include_untracked and not is_git_tracked(candidate):
            skipped_untracked += 1
            continue
        agents_paths.append(candidate)
        repo_roots.append(child.resolve())

    if skipped_untracked:
        warnings.append(f"{level_name}_git_repo_filter:skipped_untracked_agents:{skipped_untracked}")

    return agents_paths, repo_roots, warnings


def discover_repo_visible_agents(repo_root: Path) -> tuple[list[Path], list[str]]:
    warnings: list[str] = []
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            AGENTS_NAME,
            f"*/{AGENTS_NAME}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        warnings.append(f"repo_scan:{repo_root}:git_ls_files_failed:{result.stderr.strip()}")
        return [], warnings

    agents_paths = [
        (repo_root / relative_path).resolve()
        for relative_path in result.stdout.splitlines()
        if relative_path.endswith(f"/{AGENTS_NAME}") or relative_path == AGENTS_NAME
    ]
    agents_paths.sort(key=lambda item: str(item))
    return agents_paths, warnings


def discover_agents(root: Path, *, include_untracked_level4: bool) -> tuple[list[Path], list[str]]:
    warnings: list[str] = []
    root = root.resolve()
    found: list[Path] = []

    root_agents = root / AGENTS_NAME
    if root_agents.exists():
        found.append(root_agents)
    else:
        warnings.append(f"workspace_root:{root_agents}:missing")

    level4_agents, level4_repos, level4_warnings = discover_direct_child_git_agents(
        root,
        level_name="level4",
        include_untracked=include_untracked_level4,
    )
    found.extend(level4_agents)
    warnings.extend(level4_warnings)

    for exception_name in sorted(LEVEL4_EXCEPTION_PARENT_NAMES):
        exception_parent = root / exception_name
        if not exception_parent.is_dir():
            continue
        exception_agents, exception_repos, exception_warnings = discover_direct_child_git_agents(
            exception_parent,
            level_name=f"level4_exception_{exception_name}",
            include_untracked=include_untracked_level4,
        )
        found.extend(exception_agents)
        level4_repos.extend(exception_repos)
        warnings.extend(exception_warnings)

    for level4_repo in level4_repos:
        repo_agents, repo_warnings = discover_repo_visible_agents(level4_repo)
        found.extend(repo_agents)
        warnings.extend(repo_warnings)

    found = ordered_unique(found)
    found.sort(key=lambda item: str(item))
    return found, warnings


def exception_level4_root(root: Path, target: Path) -> Path | None:
    try:
        relative_parts = target.parent.relative_to(root).parts
    except ValueError:
        return None

    if len(relative_parts) < 2 or relative_parts[0] not in LEVEL4_EXCEPTION_PARENT_NAMES:
        return None

    candidate = root / relative_parts[0] / relative_parts[1]
    if is_direct_git_repo(candidate):
        return candidate.resolve()
    return None


def ancestor_agents(root: Path, target: Path) -> list[Path]:
    root = root.resolve()
    target = target.resolve()
    root_agents = root / AGENTS_NAME
    exception_root = exception_level4_root(root, target)

    ancestors: list[Path] = []
    target_dir = target.parent
    try:
        relative_dir = target_dir.relative_to(root)
    except ValueError:
        relative_dir = Path()

    current = root
    if root_agents.exists():
        ancestors.append(root_agents)

    for part in relative_dir.parts:
        current = current / part
        if exception_root is not None and current.resolve() == exception_root.parent:
            continue
        candidate = current / AGENTS_NAME
        if candidate.exists() and candidate != root_agents:
            ancestors.append(candidate)

    if target.name == AGENTS_NAME and target not in ancestors:
        ancestors.append(target)

    return ancestors


def ordered_unique(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def is_git_tracked(path: Path) -> bool:
    try:
        absolute_path = path.resolve()
    except OSError:
        absolute_path = path.absolute()

    repo_root = git_repo_root(absolute_path.parent)
    if repo_root is None:
        return False

    try:
        relative_path = absolute_path.relative_to(repo_root)
    except ValueError:
        return False

    tracked_result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", "--", str(relative_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return tracked_result.returncode == 0


def build_graph(
    *,
    root: Path,
    target: Path,
    personal_agents: Path,
    developer_instructions: Path | None,
    generated_at: str,
    scan_warnings: list[str],
    config_warnings: list[str],
) -> dict[str, object]:
    path_layers = build_path_layers(
        root=root,
        target=target,
        personal_agents=personal_agents,
        developer_instructions=developer_instructions,
    )

    nodes = [file_metadata(path, node_id, layer) for node_id, layer, path in path_layers]
    add_cumulative_metrics(nodes)
    effective_order = [str(node["id"]) for node in nodes]
    edges = [
        {
            "from": effective_order[index],
            "to": effective_order[index + 1],
            "type": "inherits",
        }
        for index in range(len(effective_order) - 1)
    ]

    node_warnings = [
        f"node:{node['id']}:{node['path']}:{node['warning']}"
        for node in nodes
        if node.get("warning")
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "root": str(root),
        "target": str(target),
        "target_level": nodes[-1]["level"] if nodes else 0,
        "target_cumulative_line_count": nodes[-1]["cumulative_line_count"] if nodes else 0,
        "target_cumulative_char_count": nodes[-1]["cumulative_char_count"] if nodes else 0,
        "nodes": nodes,
        "edges": edges,
        "effective_order": effective_order,
        "scan_warnings": config_warnings + scan_warnings + node_warnings,
    }


def build_path_layers(
    *,
    root: Path,
    target: Path,
    personal_agents: Path,
    developer_instructions: Path | None,
) -> list[tuple[str, str, Path]]:
    path_layers: list[tuple[str, str, Path]] = [
        ("personal", "personal", personal_agents),
    ]
    if developer_instructions is not None:
        path_layers.append(("developer", "developer", developer_instructions))

    local_paths = ancestor_agents(root, target)
    unique_local_paths = ordered_unique(local_paths)
    for index, path in enumerate(unique_local_paths):
        layer = "workspace_root" if path.resolve() == (root.resolve() / AGENTS_NAME) else "agents"
        path_layers.append((f"agents:{index}", layer, path))

    return path_layers


def build_paths_only_graph(
    *,
    root: Path,
    target: Path,
    personal_agents: Path,
    developer_instructions: Path | None,
) -> dict[str, object]:
    path_layers = build_path_layers(
        root=root,
        target=target,
        personal_agents=personal_agents,
        developer_instructions=developer_instructions,
    )
    return {
        "target": str(target),
        "paths": [
            {
                "level": level,
                "path": str(path),
            }
            for level, (_, _, path) in enumerate(path_layers, start=1)
        ],
    }


def alias_path(path: Path, *, root: Path, codex_root: Path) -> str:
    path = path.expanduser()
    replacements = (
        ("$codex", codex_root.expanduser().resolve()),
        ("$workspace", root.resolve()),
    )
    for alias, prefix in replacements:
        try:
            resolved_path = path.resolve()
        except OSError:
            resolved_path = path.absolute()
        try:
            relative_path = resolved_path.relative_to(prefix)
        except ValueError:
            continue
        if str(relative_path) == ".":
            return alias
        return f"{alias}/{relative_path.as_posix()}"
    return str(path)


def new_normalized_section(heading_level: int, heading: str) -> dict[str, object]:
    return {
        "heading_level": heading_level,
        "heading": heading,
        "blocks": [],
    }


def new_normalized_block() -> dict[str, list[str]]:
    return {"rules": [], "lines": []}


def append_normalized_block(section: dict[str, object], block: dict[str, list[str]]) -> None:
    if block["rules"] or block["lines"]:
        blocks = section["blocks"]
        assert isinstance(blocks, list)
        blocks.append(block)


def parse_instruction_sections(text: str) -> tuple[str | None, list[dict[str, object]]]:
    title: str | None = None
    sections: list[dict[str, object]] = []
    current_section: dict[str, object] | None = None
    current_block = new_normalized_block()

    def ensure_section() -> dict[str, object]:
        nonlocal current_section
        if current_section is None:
            current_section = new_normalized_section(0, "_preamble")
            sections.append(current_section)
        return current_section

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        heading_match = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        if heading_match:
            if current_section is not None:
                append_normalized_block(current_section, current_block)
                current_block = new_normalized_block()

            heading_level = len(heading_match.group(1))
            heading = heading_match.group(2).strip()
            if heading_level == 1:
                title = heading
                current_section = None
                continue

            current_section = new_normalized_section(heading_level, heading)
            sections.append(current_section)
            continue

        if line.strip() == "":
            if current_section is not None:
                append_normalized_block(current_section, current_block)
                current_block = new_normalized_block()
            continue

        section = ensure_section()
        if line.startswith("- "):
            current_block["rules"].append(line[2:].strip())
        else:
            current_block["lines"].append(line)

    if current_section is not None:
        append_normalized_block(current_section, current_block)

    return title, sections


def normalized_doc(
    path: Path,
    doc_id: int,
    *,
    root: Path,
    codex_root: Path,
    kind: str,
) -> dict[str, object]:
    text, _warning = read_text(path)
    title, sections = parse_instruction_sections(text or "")
    return {
        "id": doc_id,
        "kind": kind,
        "path": alias_path(path, root=root, codex_root=codex_root),
        "title": title,
        "sections": sections,
    }


def strip_markdown_anchor(reference: str) -> str:
    return reference.split("#", 1)[0]


def resolve_markdown_reference(
    reference: str,
    *,
    source_path: Path,
    root: Path,
    codex_root: Path,
) -> Path | None:
    if "://" in reference:
        return None

    path_text = strip_markdown_anchor(reference).strip()
    if not path_text or any(char in path_text for char in GLOB_CHARS):
        return None

    if path_text.startswith("$codex/"):
        candidate = codex_root / path_text.removeprefix("$codex/")
    elif path_text == "$codex":
        candidate = codex_root
    elif path_text.startswith("$workspace/"):
        candidate = root / path_text.removeprefix("$workspace/")
    elif path_text == "$workspace":
        candidate = root
    elif path_text.startswith(("/home/", "/srv/")):
        candidate = Path(path_text)
    elif path_text.startswith("/"):
        candidate = root / path_text.lstrip("/")
    else:
        candidate = source_path.parent / path_text

    try:
        return candidate.resolve()
    except OSError:
        return candidate.absolute()


def extract_markdown_reference_paths(
    *,
    source_path: Path,
    root: Path,
    codex_root: Path,
) -> list[Path]:
    text, _warning = read_text(source_path)
    if text is None:
        return []

    references: list[Path] = []
    seen: set[str] = set()
    for match in MARKDOWN_REFERENCE_RE.finditer(text):
        resolved_path = resolve_markdown_reference(
            match.group("ref"),
            source_path=source_path,
            root=root,
            codex_root=codex_root,
        )
        if resolved_path is None or not resolved_path.is_file():
            continue

        key = str(resolved_path)
        if key in seen:
            continue
        seen.add(key)
        references.append(resolved_path)
    return references


def build_normalized_export(
    *,
    root: Path,
    targets: Iterable[Path],
    personal_agents: Path,
    developer_instructions: Path | None,
    codex_root: Path,
) -> dict[str, object]:
    doc_ids: dict[str, int] = {}
    doc_paths: list[Path] = []
    doc_kinds: list[str] = []
    normalized_graphs: list[dict[str, object]] = []

    def doc_id_for(path: Path, *, kind: str) -> int:
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path.absolute())
        existing = doc_ids.get(key)
        if existing is not None:
            if kind == "instruction":
                doc_kinds[existing] = "instruction"
            return existing
        new_id = len(doc_paths)
        doc_ids[key] = new_id
        doc_paths.append(path)
        doc_kinds.append(kind)
        return new_id

    for target in targets:
        path_layers = build_path_layers(
            root=root,
            target=target,
            personal_agents=personal_agents,
            developer_instructions=developer_instructions,
        )
        chain = [doc_id_for(path, kind="instruction") for _, _, path in path_layers]
        dependencies: list[dict[str, int | str]] = []
        seen_dependencies: set[tuple[int, int]] = set()

        for source_id, (_, _, source_path) in zip(chain, path_layers):
            for reference_path in extract_markdown_reference_paths(
                source_path=source_path,
                root=root,
                codex_root=codex_root,
            ):
                target_id = doc_id_for(reference_path, kind="markdown_reference")
                if target_id == source_id:
                    continue
                dependency_key = (source_id, target_id)
                if dependency_key in seen_dependencies:
                    continue
                seen_dependencies.add(dependency_key)
                dependencies.append(
                    {
                        "from": source_id,
                        "to": target_id,
                        "type": "markdown_reference",
                    }
                )

        normalized_graphs.append(
            {
                "target": chain[-1],
                "chain": chain,
                "dependencies": dependencies,
            }
        )

    return {
        "roots": {
            "codex": str(codex_root),
            "workspace": str(root),
        },
        "docs": [
            normalized_doc(path, doc_id, root=root, codex_root=codex_root, kind=doc_kinds[doc_id])
            for doc_id, path in enumerate(doc_paths)
        ],
        "graphs": normalized_graphs,
    }


def emit_graphs(graphs: Iterable[dict[str, object]], output: Path | None) -> None:
    if output is None:
        for graph in graphs:
            print(json.dumps(graph, ensure_ascii=False, separators=(",", ":")))
        return

    with output.open("w", encoding="utf-8") as handle:
        for graph in graphs:
            handle.write(json.dumps(graph, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def emit_normalized_export(normalized_export: dict[str, object], output: Path) -> None:
    output.write_text(
        json.dumps(normalized_export, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    personal_agents = args.personal_agents.expanduser()
    codex_config = args.codex_config.expanduser()
    developer_instructions, config_warnings = parse_model_instructions_file(codex_config)
    targets, scan_warnings = discover_agents(root, include_untracked_level4=args.include_untracked_level4)
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat()

    graphs = (
        build_graph(
            root=root,
            target=target,
            personal_agents=personal_agents,
            developer_instructions=developer_instructions,
            generated_at=generated_at,
            scan_warnings=scan_warnings,
            config_warnings=config_warnings,
        )
        for target in targets
    )
    emit_graphs(graphs, args.output)
    if args.paths_only_output is not None:
        paths_only_graphs = (
            build_paths_only_graph(
                root=root,
                target=target,
                personal_agents=personal_agents,
                developer_instructions=developer_instructions,
            )
            for target in targets
        )
        emit_graphs(paths_only_graphs, args.paths_only_output)
    if args.normalized_output is not None:
        normalized_export = build_normalized_export(
            root=root,
            targets=targets,
            personal_agents=personal_agents,
            developer_instructions=developer_instructions,
            codex_root=DEFAULT_CODEX_CONFIG.parent.resolve(),
        )
        emit_normalized_export(normalized_export, args.normalized_output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
