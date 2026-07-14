#!/usr/bin/env python3
"""Launch the root-owned deployment package and preserve the gateway API.

Entry point: ``main``. Boundary: the installed launcher imports only the fixed
root-owned package tree; repository-local imports are allowed only beside this
deployment facade.
"""

from __future__ import annotations

from functools import wraps
import importlib
import inspect
import os
from pathlib import Path
import stat
import sys
from typing import Any, Callable


_INSTALLED_PACKAGE_ROOT = Path("/usr/local/lib/bears-plugin-deploy")
_LOCAL_PACKAGE_ROOT = Path(__file__).resolve().parent
_MODULE_NAMES = (
    "constants",
    "models",
    "graph_instructions",
    "telemetry",
    "process",
    "marketplace",
    "role_renderer",
    "role_profiles",
    "role_io",
    "publication",
    "standalone_roles",
    "journal",
    "state_io",
    "intent_schema",
    "intent_io",
    "receipts",
    "role_deploy",
    "role_recovery",
    "promotion",
    "cli",
)


def _validate_installed_package(root: Path) -> None:
    """Reject linked, writable, or non-root package directories."""
    for path in (root, root / "bears_deploy"):
        metadata = path.lstat()
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_uid != 0
            or metadata.st_gid != 0
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            raise RuntimeError(f"unsafe installed gateway package directory: {path}")


if _LOCAL_PACKAGE_ROOT.joinpath("bears_deploy").is_dir():
    _PACKAGE_ROOT = _LOCAL_PACKAGE_ROOT
else:
    _PACKAGE_ROOT = _INSTALLED_PACKAGE_ROOT
    _validate_installed_package(_PACKAGE_ROOT)

os.environ.pop("PYTHONHOME", None)
os.environ.pop("PYTHONPATH", None)
sys.path.insert(0, str(_PACKAGE_ROOT))

_MODULES = tuple(
    importlib.import_module(f"bears_deploy.{name}") for name in _MODULE_NAMES
)
_ORIGINAL_EXPORTS: dict[str, Any] = {}
for _module in _MODULES:
    for _name, _value in vars(_module).items():
        if not _name.startswith("_"):
            _ORIGINAL_EXPORTS[_name] = _value

_WRAPPERS: dict[str, Callable[..., Any]] = {}


def _sync_compatibility_globals() -> None:
    """Forward facade patches to split modules before one public call."""
    current = globals()
    for module in _MODULES:
        namespace = vars(module)
        for name in tuple(namespace):
            if name.startswith("_") or name not in _ORIGINAL_EXPORTS:
                continue
            value = current.get(name, _ORIGINAL_EXPORTS[name])
            if value is _WRAPPERS.get(name):
                value = _ORIGINAL_EXPORTS[name]
            namespace[name] = value


def _forward(name: str, function: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap one package function with compatibility-global synchronization."""

    @wraps(function)
    def forwarded(*args: Any, **kwargs: Any) -> Any:
        _sync_compatibility_globals()
        return function(*args, **kwargs)

    forwarded.__name__ = name
    return forwarded


for _name, _value in _ORIGINAL_EXPORTS.items():
    if inspect.isfunction(_value) and _value.__module__.startswith("bears_deploy."):
        _WRAPPERS[_name] = _forward(_name, _value)
        globals()[_name] = _WRAPPERS[_name]
    else:
        globals()[_name] = _value

__all__ = tuple(sorted(_ORIGINAL_EXPORTS))


if __name__ == "__main__":
    raise SystemExit(main())
