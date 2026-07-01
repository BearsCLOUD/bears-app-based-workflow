# GitHub issue reference contract

This contract defines one repo-qualified GitHub issue identity for the @Bears plugin.

## Canonical packet

A resolved issue reference is stored as `owner/repo#number` and as a packet with schema `bears-github-issue-ref.v1`.

Required identity fields:

- `repo`: explicit `owner/repo`.
- `owner`: owner segment from `repo`.
- `repo_name`: repository segment from `repo`.
- `issue_number`: positive GitHub issue number, or `null` for `proposed` and `unresolved`.
- `canonical_ref`: `owner/repo#number`, or `null` when no issue number exists.
- `github_url`: GitHub issue URL, or `null` when no issue number exists.
- `state`: one of `resolved`, `proposed`, `unresolved`, `blocked`.
- `legacy_local_ref`: original `#number` only when a local ref was normalized with an explicit repo.
- `status`: `pass` or `blocked`.

## States

- `resolved`: repo and issue number are explicit.
- `proposed`: future issue target has an explicit repo and no GitHub issue number yet.
- `unresolved`: the node intentionally has no issue target yet.
- `blocked`: repo or issue identity is missing, invalid, or ambiguous.

## Local refs

`#number` is accepted only when the caller supplies `--repo owner/repo` or an equivalent explicit repo field. A local ref without repo is blocked. A planner must not derive repo from the checkout, chat context, default repo, or issue title.

## Static commands

```bash
python3 scripts/github_issue_ref.py validate
python3 scripts/github_issue_ref.py normalize --ref BearsCLOUD/bears_plugin#424 --json
python3 scripts/github_issue_ref.py normalize --repo BearsCLOUD/bears-platform --issue 66 --json
python3 scripts/github_issue_ref.py compare --left BearsCLOUD/bears-platform#66 --right BearsCLOUD/bears-infra#66 --json
```

The validator is static, local, and read-only. It does not call GitHub.

## Integration rule

Global delivery, seller migration, generated issue lineage, issue delivery identity, metrics, and autostart selection must normalize issue-like fields through this packet shape before comparing identities. `BearsCLOUD/bears-platform#66` and `BearsCLOUD/bears-infra#66` are different identities.
