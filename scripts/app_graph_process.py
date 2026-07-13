"""Append-only process v2 journal writer and exact repo-wave lifecycle validation."""

from __future__ import annotations

import fcntl
import os
import secrets
from typing import Any

from app_graph_store import *


REQUIRED_STRINGS = ("run_ref", "event_ref", "event_kind", "stage", "status", "actor", "origin", "automation_status", "repo_ref", "wave_ref")
REQUIRED_ARRAYS = ("causal_refs", "trace_refs", "artifact_refs", "task_refs")


def _validate_event(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict) or event.get("schema") != "app-process-event.v2":
        raise GraphError("SCHEMA_UNSUPPORTED", "new events must use app-process-event.v2")
    if any(not isinstance(event.get(name), str) or not event[name] for name in REQUIRED_STRINGS):
        raise GraphError("JOURNAL_CORRUPT", "event string fields are incomplete")
    if any(not isinstance(event.get(name), list) or len(event[name]) != len(set(event[name])) or any(not isinstance(x, str) or not x for x in event[name]) for name in REQUIRED_ARRAYS):
        raise GraphError("JOURNAL_CORRUPT", "event reference arrays are invalid")
    if event["origin"] != "native": raise GraphError("SCHEMA_UNSUPPORTED", "v2 events are native-only")
    if event["automation_status"] not in {"not_run", "passed", "failed"}: raise GraphError("JOURNAL_CORRUPT", "automation status is invalid")
    if event["event_kind"] == "run-start" and (not event["task_refs"] or event.get("remediates_run_ref") == event["run_ref"]):
        raise GraphError("RUN_SCOPE_INVALID", "run-start needs an exact non-empty task set")
    if event.get("status") == "audited" and event["automation_status"] == "not_run":
        raise GraphError("ACCEPTANCE_NOT_RUN", "audited cannot be written without acceptance evidence")
    return event


def _existing_run(root: RepoRoot, event_root: str, run_ref: str) -> list[dict[str, Any]]:
    result = []
    for path in event_paths(root, [event_root]):
        if f"/{run_ref}/" in path:
            event, _ = read_json(root, path); result.append(event)
    return result


def _validate_lifecycle(root: RepoRoot, event_root: str, event: dict[str, Any]) -> None:
    prior = _existing_run(root, event_root, event["run_ref"])
    starts = [x for x in prior if x.get("event_kind") == "run-start"]
    if event["event_kind"] == "run-start":
        if prior: raise GraphError("RUN_CONFLICT", "run-start must be the first and only scope declaration")
        return
    if len(starts) != 1: raise GraphError("RUN_SCOPE_INVALID", "run has no exact run-start")
    start = starts[0]
    if any(event[key] != start[key] for key in ("repo_ref", "wave_ref", "task_refs")):
        raise GraphError("RUN_SCOPE_INVALID", "event scope differs from run-start")
    if event["event_kind"] == "task-result" and event.get("task_ref") not in start["task_refs"]:
        raise GraphError("RUN_SCOPE_INVALID", "task result is outside run scope")
    if event["event_kind"] == "review":
        results = {x.get("task_ref") for x in prior if x.get("event_kind") == "task-result" and x.get("terminal_result") in {"done", "failed", "blocked"}}
        if results != set(start["task_refs"]): raise GraphError("REVIEW_INCOMPLETE", "immutable review requires terminal results for the full run")
        if not event.get("commit_range") or set(event.get("reviewed_task_refs", [])) != set(start["task_refs"]): raise GraphError("REVIEW_INCOMPLETE", "review must cover the exact commit range and task set")
    if event["event_kind"] == "remediation-link":
        raise GraphError("REMEDIATION_RUN_REQUIRED", "findings must be linked from a new remediation run-start")


def process_record_event(arguments: dict[str, Any]) -> dict[str, Any]:
    root = safe_root(arguments.get("app_root"))
    try:
        source_manifest = manifest(root, require_maintainer=True); event = _validate_event(arguments.get("event")); event_root = source_manifest["sources"]["event_roots"][-1]
        lock = open_directory(root, ("docs",)); fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            _validate_lifecycle(root, event_root, event)
            ref, run_ref = event["event_ref"], event["run_ref"]
            if any("/" in x or ".." in x for x in (ref, run_ref)): raise GraphError("PATH_ESCAPE", "event and run refs must be safe")
            relative = f"{event_root}/{run_ref}/{ref}.json"; payload = canonical(event); current = read_regular(root, relative, missing=True)
            if current is not None:
                if current == payload: return {"schema":"app-process-event-result.v1","status":"current","event_ref":ref,"no_op":True}
                raise GraphError("EVENT_CONFLICT", "event key already differs", event_ref=ref)
            known = {x["event_ref"] for x in _existing_run(root, event_root, run_ref)}
            if any(cause not in known for cause in event["causal_refs"]): raise GraphError("DANGLING_REF", "event cause is missing")
            names = parts(relative); parent = open_directory(root, names[:-1], create=True); temporary = f".{names[-1]}.{secrets.token_hex(8)}.tmp"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            try: os.write(descriptor, payload); os.fsync(descriptor)
            finally: os.close(descriptor)
            try: os.link(temporary, names[-1], src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            finally:
                try: os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError: pass
                os.fsync(parent); os.close(parent)
            QUERY_CACHE.clear()
            return {"schema":"app-process-event-result.v1","status":"recorded","event_ref":ref,"event_digest":digest_bytes(payload),"no_op":False}
        finally: os.close(lock)
    finally: root.close()
