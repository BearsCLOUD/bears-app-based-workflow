"""Command-line interface for Bears instruction graph exports."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from bears_workflow.instruction_artifacts.adapters import exporter
from bears_workflow.instruction_artifacts.application.zones import build_zones
from bears_workflow.instruction_artifacts.domain.constants import (
    default_codex_config,
    default_personal_agents,
    default_root,
)


def parse_args() -> argparse.Namespace:
    """Parse compatibility flags for the instruction graph exporter."""
    parser = argparse.ArgumentParser(
        description=(
            "Export Bears instruction graphs and normalized instruction zones."
        )
    )
    parser.add_argument("--root", type=Path, default=default_root(), help="Workspace root to scan.")
    parser.add_argument(
        "--codex-config",
        type=Path,
        default=default_codex_config(),
        help="Codex config containing model_instructions_file.",
    )
    parser.add_argument(
        "--personal-agents",
        type=Path,
        default=default_personal_agents(),
        help="Personal AGENTS.md file.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Write JSONL to this path.")
    parser.add_argument(
        "--paths-only-output",
        type=Path,
        default=None,
        help="Also write lightweight JSONL containing only targets and inherited paths.",
    )
    parser.add_argument(
        "--normalized-output",
        type=Path,
        default=None,
        help="Also write normalized zones JSON without top-level metadata.",
    )
    parser.add_argument(
        "--include-untracked-level4",
        action="store_true",
        help="Include direct child Git repositories whose root AGENTS.md is not tracked.",
    )
    return parser.parse_args()


def emit_json_object(payload: dict[str, object], output: Path) -> None:
    """Write one compact JSON object to an output file."""
    output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """Run the compatibility instruction graph export command."""
    args = parse_args()
    root = args.root.resolve()
    personal_agents = args.personal_agents.expanduser()
    codex_config = args.codex_config.expanduser()
    developer_instructions, config_warnings = exporter.parse_model_instructions_file(codex_config)
    targets, discovery_warnings = exporter.discover_agents(
        root,
        include_untracked_level4=args.include_untracked_level4,
    )
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat()

    graphs = [
        exporter.build_graph(
            root=root,
            target=target,
            personal_agents=personal_agents,
            developer_instructions=developer_instructions,
            generated_at=generated_at,
            scan_warnings=discovery_warnings,
            config_warnings=config_warnings,
        )
        for target in targets
    ]
    exporter.emit_graphs(graphs, args.output)

    if args.paths_only_output is not None:
        path_graphs = [
            exporter.build_paths_only_graph(
                root=root,
                target=target,
                personal_agents=personal_agents,
                developer_instructions=developer_instructions,
            )
            for target in targets
        ]
        exporter.emit_graphs(path_graphs, args.paths_only_output)

    if args.normalized_output is not None:
        emit_json_object(
            build_zones(
                root=root,
                codex_config=codex_config,
                personal_agents=personal_agents,
                include_untracked_level4=args.include_untracked_level4,
            ),
            args.normalized_output,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
