# Git Hook Bootstrap

The shared hook runner gives governed Bears repositories thin local git hook entrypoints that call the plugin-owned `@bears` runner.

## Authority

- `scripts/bears_git_hook.py` owns install, run, verify, write-proof, validate-proof, and validate commands.
- `assets/schemas/effective-hooks-proof.v1.schema.json` defines closeout proof.
- `assets/catalog/git-hook-bootstrap.v1.json` defines hook modes, allowed actions, runtime paths, and the async worker boundary.
- `tests/fixtures/git_hook_bootstrap/` stores good and bad proof packets.

## Hook model

`pre-commit` performs only cheap blocking guards. The current cheap guard is `git diff --cached --check --no-ext-diff`.

`post-commit` resolves the commit SHA, writes a queued validation job through `scripts/validation_queue.py`, writes validation state, updates effective hook proof, and exits. It does not run tests, run long validators, or auto-start a worker. `scripts/validation_worker.py` owns execution outside the hook path.

Generated hook entrypoints include the `@bears` plugin reference and call:

```bash
python3 /srv/bears/plugins/bears/scripts/bears_git_hook.py run --hook <hook> --workspace-root /srv/bears --repo-path <repo>
```

## Command surface

- `python3 scripts/bears_git_hook.py install --workspace-root /srv/bears --scope current`
- `python3 scripts/bears_git_hook.py install --workspace-root /srv/bears --repo-path <path>`
- `python3 scripts/bears_git_hook.py run --hook pre-commit`
- `python3 scripts/bears_git_hook.py run --hook post-commit`
- `python3 scripts/bears_git_hook.py verify --repo-path <path>`
- `python3 scripts/bears_git_hook.py write-proof --repo-path <path>`
- `python3 scripts/bears_git_hook.py validate-proof --proof <path>`
- `python3 scripts/bears_git_hook.py validate`

## Proof paths

- `runtime/effective-hooks/<repo_id>/effective-hooks-proof.v1.json`
- `runtime/validation-jobs/<commit_sha>/<job_id>.json`
- `runtime/validation-state/<commit_sha>/validation-state.v1.json`

## Output policy

Each hook command writes one bounded JSON event to stdout. Detailed state is written to runtime packets. Hook output must not include secrets, credentials, environment values, private chats, unrestricted diagnostics, VPN config, or production data.

## Future integrations

Issue #371 owns the async validation worker. Issue #388 owns `bears_doctor` closeout consumption.
