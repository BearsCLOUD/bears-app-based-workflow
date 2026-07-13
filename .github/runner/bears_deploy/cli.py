"""Gateway CLI entry point; validates identity and SHA before taking the state lock."""

from __future__ import annotations

import fcntl
import json
import os
import pwd
import sys

from .constants import ACTIONABLE_ERROR_CODES, PLUGIN, SHA_RE
from .models import DeployContext, DeployError
from .process import read_github_token
from .promotion import promote
from .state_io import open_lock_file, open_state_directory
from .telemetry import report_sentry


def main() -> int:
    if pwd.getpwuid(os.geteuid()).pw_name != "ai1" or os.geteuid() == 0:
        print("deploy-plugin: gateway must run as non-root ai1", file=sys.stderr)
        return 2
    if len(sys.argv) != 2 or not SHA_RE.fullmatch(sys.argv[1]):
        print("deploy-plugin: expected one exact lowercase 40-character SHA", file=sys.stderr)
        return 2
    context = DeployContext(sys.argv[1])
    state_directory = -1
    descriptor = -1
    try:
        github_token = read_github_token(sys.stdin.buffer)
        state_directory = open_state_directory()
        descriptor = open_lock_file(state_directory)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        status = promote(sys.argv[1], context, state_directory, github_token)
    except (DeployError, OSError) as exc:
        error_code = exc.error_code if isinstance(exc, DeployError) else None
        if error_code is None and context.phase == "mutation":
            error_code = "mutation-failure-after-start"
        elif error_code is None and context.phase == "post-mutation":
            error_code = "post-mutation-failure"
        if error_code in ACTIONABLE_ERROR_CODES:
            report_sentry(error_code, context, exc)
        print(f"deploy-plugin: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        report_sentry("unhandled-exception", context, exc)
        print("deploy-plugin: unhandled gateway failure", file=sys.stderr)
        return 1
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if state_directory >= 0:
            os.close(state_directory)
    print(json.dumps({"plugin": PLUGIN, "sha": sys.argv[1], "status": status}, sort_keys=True))
    return 0
