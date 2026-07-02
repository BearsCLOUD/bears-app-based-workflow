---
name: development-workflow-orchestration
description: Coordinate broad Bears development work through user agreement, workspace bootstrap, architecture, task graph, domain orchestration, worker execution, read-only review, merge decision, and stage-boundary audit packets.
---

# Development Workflow Orchestration

Use this skill for broad Bears development work. The parent agent routes here and does not implement.

## Required flow

1. Capture `user-agreement` before implementation.
2. Validate one `workspace-bootstrap` packet per repo or domain.
3. Build `architecture-packet` and `task-graph` before worker waves.
4. Delegate domain slices to domain orchestrators.
5. Require smart reusable worker selection before worker spawn.
6. Collect worker closeout packets.
   Keep exactly one persistent `gitflow` closeout subagent for the parent work: `bears-git-workflow-helper`, model `gpt-5.4-mini`, reasoning `high`, `/goal` prompt, no parent/start context. It receives only explicit commit/push/local-validation closeout packets and is not a read-only audit lane.
7. Request read-only review.
8. Record merge decision only after `REVIEW_PASS` and unchanged head.
9. Emit stage-boundary audit.

## Local-commit-owned validation commands

- Local commit validation owns `python3 scripts/development_workflow_validate.py validate`; manual execution requires operator approval.
- Local commit validation owns `python3 scripts/development_workflow_validate.py validate-user-agreement <file>`; manual execution requires operator approval.
- Local commit validation owns `python3 scripts/development_workflow_validate.py validate-bootstrap <file>`; manual execution requires operator approval.
- Local commit validation owns `python3 scripts/development_workflow_validate.py validate-task-graph <file>`; manual execution requires operator approval.
- Local commit validation owns `python3 scripts/development_workflow_validate.py validate-stage-audit <file>`; manual execution requires operator approval.

## Small-task exception

A small exact-file bugfix may bypass this workflow only when all are true: one repo, one exact owner role, no public interface change, no runtime/provider/secret impact, no new repository boundary, no subagent needed, and validation command known before edit. Report `small_task_exception` with the reason.
