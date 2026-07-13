"""Promotion convergence and recovery orchestration for one exact main SHA."""

from __future__ import annotations

from typing import Any

from .constants import (
    CODEX,
    DEPLOY_RECEIPT_SCHEMA,
    MARKETPLACE,
    MARKETPLACE_ROOT,
    MIRROR,
    PAYLOAD_PATHS,
    PLUGIN,
    RECEIPT_MAX_BYTES,
    ROLE_RECEIPT_MAX_BYTES,
    ROLE_RECEIPT_SCHEMA,
    SEMVER_RE,
    VERSION_RE,
)
from .intent_io import clear_intent, load_intent, save_intent
from .intent_schema import validate_intent
from .journal import decode_journal_bytes
from .marketplace import (
    manifest,
    marketplace_row,
    payload_fingerprint,
    semver_tuple,
    validate_marketplace,
    verify_disabled,
)
from .models import DeployContext, DeployError, begin_activation_mutation
from .graph_instructions import (
    reconcile_graph_instructions,
    remove_graph_instructions,
    restore_graph_preimage,
)
from .process import (
    exact_remote,
    git,
    git_text,
    github_authenticated_env,
    is_ancestor,
    prepare_mirror,
    run_json,
)
from .receipts import clear_state, save_state, verify_receipted_install
from .role_deploy import reconcile_roles
from .role_recovery import clear_owned_roles, rollback_journaled_roles
from .role_profiles import strict_json_loads
from .state_io import (
    load_migration_tombstone,
    load_state,
    parse_migration_tombstone,
)
from .telemetry import normalized_diagnostic


def reconcile_receipted_roles(
    state_directory: int,
    state: dict[str, Any],
    intent: dict[str, Any],
) -> dict[str, Any]:
    role_record = reconcile_roles(
        str(state["sha"]),
        str(state["version"]),
        state_directory,
        intent,
    )
    if role_record["payload_fingerprint"] != state["payload_fingerprint"]:
        raise DeployError(
            "live roles disagree with the exact deployment receipt",
            error_code="receipt-corruption",
        )
    if state.get("schema") == DEPLOY_RECEIPT_SCHEMA:
        for field, value in role_record.items():
            if state.get(field) != value:
                raise DeployError(
                    "deployment role receipt disagrees with the exact cached generation",
                    error_code="receipt-corruption",
                )
    return role_record


def restore_receipted_install(
    state_directory: int,
    state: dict[str, Any],
) -> None:
    sha = str(state["sha"])
    version = str(state["version"])
    fingerprint = str(state["payload_fingerprint"])
    restore_intent = save_intent(state_directory, sha, state)
    marketplace_row(create=False)
    exact_remote(MARKETPLACE_ROOT)
    git(MARKETPLACE_ROOT, "reset", "--hard", sha)
    git(MARKETPLACE_ROOT, "clean", "-ffdx", "--", *PAYLOAD_PATHS)
    if git_text(MARKETPLACE_ROOT, "rev-parse", "HEAD") != sha:
        raise DeployError("recovery marketplace checkout is not the receipted SHA")
    dirty_payload = git(
        MARKETPLACE_ROOT, "status", "--porcelain=v1", "--untracked-files=all", "--", *PAYLOAD_PATHS
    ).stdout
    if dirty_payload or manifest(MARKETPLACE_ROOT, sha).get("version") != version:
        raise DeployError("recovery marketplace checkout is inconsistent")
    if payload_fingerprint(MARKETPLACE_ROOT, sha) != fingerprint:
        raise DeployError("recovery marketplace payload disagrees with its receipt")
    run_json([CODEX, "plugin", "add", f"{PLUGIN}@{MARKETPLACE}", "--json"])
    verify_receipted_install(state)
    role_record = reconcile_receipted_roles(state_directory, state, restore_intent)
    graph_record = reconcile_graph_instructions(state_directory, state)
    save_state(state_directory, sha, version, role_record, graph_record)
    durable = load_state(state_directory)
    if (
        durable is None
        or durable.get("schema") != DEPLOY_RECEIPT_SCHEMA
        or durable.get("sha") != sha
        or durable.get("version") != version
        or any(durable.get(field) != value for field, value in role_record.items())
        or any(durable.get(field) != value for field, value in graph_record.items())
    ):
        raise DeployError("recovered deployment receipt is not durably role-complete")
    verify_receipted_install(durable)


def disable_and_verify(state_directory: int, intent: dict[str, Any]) -> None:
    state = load_state(state_directory)
    try:
        run_json([CODEX, "plugin", "disable", f"{PLUGIN}@{MARKETPLACE}", "--json"])
    except Exception:
        pass
    verify_disabled()
    clear_owned_roles(state_directory, load_intent(state_directory) or intent)
    restore_graph_preimage(load_intent(state_directory) or intent)
    remove_graph_instructions(state)
    clear_state(state_directory)


def converge_registration_migration(
    state_directory: int,
    intent: dict[str, Any],
) -> str:
    """Recover the one-shot registration migration only by converging forward."""
    validate_intent(intent)
    transaction = intent.get("role_transaction")
    if not isinstance(transaction, dict) or transaction.get("operation") != "migrate-v1-registration":
        raise DeployError("registration migration recovery journal is absent")
    desired_receipt = decode_journal_bytes(
        transaction["role_receipt_b64"],
        ROLE_RECEIPT_MAX_BYTES,
        "desired role receipt",
    )
    receipt_value = strict_json_loads(desired_receipt, "desired v2 role receipt")
    version = receipt_value.get("version") if isinstance(receipt_value, dict) else None
    if (
        not isinstance(version, str)
        or not VERSION_RE.fullmatch(version)
        or receipt_value.get("schema") != ROLE_RECEIPT_SCHEMA
        or receipt_value.get("plugin") != PLUGIN
        or receipt_value.get("status") != "installed"
    ):
        raise DeployError("registration migration desired receipt is invalid")
    requested = str(intent["requested_sha"])
    role_record = reconcile_roles(requested, version, state_directory, intent)
    graph_record = reconcile_graph_instructions(state_directory, load_state(state_directory))
    save_state(state_directory, requested, version, role_record, graph_record)
    durable = load_state(state_directory)
    if (
        durable is None
        or durable.get("schema") != DEPLOY_RECEIPT_SCHEMA
        or durable.get("sha") != requested
        or durable.get("version") != version
        or any(durable.get(field) != value for field, value in role_record.items())
        or any(durable.get(field) != value for field, value in graph_record.items())
    ):
        raise DeployError("registration migration deployment receipt is not durable")
    expected_tombstone = parse_migration_tombstone(
        decode_journal_bytes(
            transaction["tombstone_b64"],
            RECEIPT_MAX_BYTES,
            "migration tombstone",
        )
    )
    if load_migration_tombstone(state_directory) != expected_tombstone:
        raise DeployError("registration migration tombstone disappeared before receipt")
    verify_receipted_install(durable)
    clear_intent(state_directory)
    return "requested"


def converge_promotion_intent(
    state_directory: int,
    intent: dict[str, Any],
) -> str:
    """Converge one catchable or crash-recovered promotion to a verified state."""
    durable_intent = load_intent(state_directory)
    if durable_intent is not None:
        intent = durable_intent
    transaction = intent.get("role_transaction")
    if transaction is not None and transaction.get("operation") == "migrate-v1-registration":
        return converge_registration_migration(state_directory, intent)
    if transaction is not None and transaction.get("operation") == "remove":
        disable_and_verify(state_directory, intent)
        clear_intent(state_directory)
        return "disabled"
    requested = str(intent["requested_sha"])
    state: dict[str, Any] | None
    try:
        state = load_state(state_directory)
    except DeployError as exc:
        if exc.error_code != "receipt-corruption":
            raise
        state = None
    if state is not None and state["sha"] == requested:
        try:
            verify_receipted_install(state)
            role_record = reconcile_receipted_roles(state_directory, state, intent)
            graph_record = reconcile_graph_instructions(state_directory, state)
            save_state(
                state_directory,
                str(state["sha"]),
                str(state["version"]),
                role_record,
                graph_record,
            )
            durable = load_state(state_directory)
            if (
                durable is None
                or durable.get("schema") != DEPLOY_RECEIPT_SCHEMA
                or any(durable.get(field) != value for field, value in role_record.items())
                or any(durable.get(field) != value for field, value in graph_record.items())
            ):
                raise DeployError("recovered requested receipt is not durably role-complete")
            verify_receipted_install(durable)
        except Exception:
            pass
        else:
            clear_intent(state_directory)
            return "requested"

    previous = intent["previous_receipt"]
    if previous is not None:
        try:
            rollback_journaled_roles(load_intent(state_directory) or intent)
            restore_graph_preimage(load_intent(state_directory) or intent)
            restore_receipted_install(state_directory, previous)
        except Exception:
            pass
        else:
            clear_intent(state_directory)
            return "previous"

    active_intent = load_intent(state_directory) or intent
    rollback_journaled_roles(active_intent)
    disable_and_verify(state_directory, active_intent)
    clear_intent(state_directory)
    return "disabled"


def recover_promotion_intent(state_directory: int) -> None:
    """Recover an unfinished durable intent before ordinary receipt handling."""
    intent = load_intent(state_directory)
    if intent is None:
        return
    try:
        converge_promotion_intent(state_directory, intent)
    except Exception as exc:
        raise DeployError(
            "unfinished promotion recovery convergence is unproven",
            error_code="recovery-failure",
        ) from exc


def fail_after_recovery(
    state_directory: int,
    intent: dict[str, Any],
    failure: Exception,
) -> None:
    try:
        outcome = converge_promotion_intent(state_directory, intent)
    except Exception as recovery_failure:
        raise DeployError(
            "promotion failed after activation and recovery convergence is unproven",
            error_code="recovery-failure",
        ) from recovery_failure
    if outcome == "requested":
        message = "promotion failed after activation; requested revision is durably receipted and active"
    elif outcome == "previous":
        message = "promotion failed after activation; previous receipted revision was restored"
    else:
        message = "promotion failed after activation; plugin was disabled"
    message = f"{message}; cause: {normalized_diagnostic(str(failure))}"
    raise DeployError(
        message,
        error_code="recovery-activated",
    ) from failure


def promote(
    requested: str,
    context: DeployContext,
    state_directory: int,
    github_token: str,
) -> str:
    recover_promotion_intent(state_directory)
    main_sha = prepare_mirror(requested, github_token)
    requested_manifest = manifest(MIRROR, requested)
    context.version = str(requested_manifest["version"])
    validate_marketplace(MIRROR, requested)
    state = load_state(state_directory)
    previous: dict[str, Any] | None = None
    if state is not None:
        current = str(state["sha"])
        current_version = str(state["version"])
        requested_version = str(requested_manifest["version"])
        if not is_ancestor(MIRROR, current, main_sha):
            raise DeployError("receipted SHA is not on fixed main", error_code="receipt-corruption")
        verify_receipted_install(state)
        if requested != current and SEMVER_RE.fullmatch(current_version):
            if not SEMVER_RE.fullmatch(requested_version):
                raise DeployError("plain SemVer deployments cannot return to legacy timestamp versions")
            if semver_tuple(requested_version) <= semver_tuple(current_version):
                raise DeployError("every new deployment must increase the plain SemVer version")
        early_status: str | None = None
        if requested == current:
            early_status = "already-deployed"
        elif is_ancestor(MIRROR, requested, current):
            early_status = "skipped-older-ancestor"
        if early_status is not None:
            repair_intent = save_intent(state_directory, current, state)
            try:
                role_record = reconcile_receipted_roles(
                    state_directory,
                    state,
                    repair_intent,
                )
                graph_record = reconcile_graph_instructions(state_directory, state)
                save_state(
                    state_directory,
                    current,
                    str(state["version"]),
                    role_record,
                    graph_record,
                )
                repaired = load_state(state_directory)
                if repaired is None or repaired.get("schema") != DEPLOY_RECEIPT_SCHEMA:
                    raise DeployError("repaired deployment receipt is not durable")
                verify_receipted_install(repaired)
                clear_intent(state_directory)
            except Exception as exc:
                fail_after_recovery(state_directory, repair_intent, exc)
            return early_status
        if not is_ancestor(MIRROR, current, requested):
            raise DeployError("non-fast-forward promotion requires a separate rollback authorization")
        previous = state
    else:
        verify_disabled()

    intent = save_intent(state_directory, requested, previous)
    authenticated_env = github_authenticated_env(github_token)
    try:
        marketplace_row(create=True, context=context, env=authenticated_env)
        begin_activation_mutation(context)
        run_json(
            [CODEX, "plugin", "marketplace", "upgrade", MARKETPLACE, "--json"],
            env=authenticated_env,
        )
        context.phase = "post-mutation"
        marketplace_row(create=False)
        exact_remote(MARKETPLACE_ROOT)
        snapshot_sha = git_text(MARKETPLACE_ROOT, "rev-parse", "HEAD")
        if snapshot_sha != requested:
            raise DeployError("marketplace snapshot is not the exact requested GitHub SHA")
        begin_activation_mutation(context)
        run_json(
            [CODEX, "plugin", "add", f"{PLUGIN}@{MARKETPLACE}", "--json"],
            env=authenticated_env,
        )
        context.phase = "post-mutation"
        version = str(requested_manifest["version"])
        role_record = reconcile_roles(requested, version, state_directory, intent)
        graph_record = reconcile_graph_instructions(state_directory, state)
        save_state(state_directory, requested, version, role_record, graph_record)
        durable_state = load_state(state_directory)
        if (
            durable_state is None
            or durable_state["sha"] != requested
            or durable_state["version"] != version
            or any(durable_state.get(field) != value for field, value in role_record.items())
            or any(durable_state.get(field) != value for field, value in graph_record.items())
        ):
            raise DeployError("durable deployment receipt disagrees with the verified promotion")
        verify_receipted_install(durable_state)
        clear_intent(state_directory)
    except Exception as exc:
        fail_after_recovery(state_directory, intent, exc)
    context.phase = "complete"
    return "deployed"
