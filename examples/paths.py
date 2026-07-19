"""Resolve example files consistently under `bazel run` and direct execution."""

import os
from pathlib import Path
from typing import Mapping


def workspace_path(path: str, environ: Mapping[str, str] | None = None) -> str:
    """Resolve a relative user path against Bazel's invoking workspace.

    Bazel runs binaries from a runfiles directory but publishes the directory
    from which `bazel run` was invoked in BUILD_WORKSPACE_DIRECTORY. Absolute
    paths and direct Python/binary execution retain their usual behavior.
    """
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    environment = os.environ if environ is None else environ
    workspace = environment.get("BUILD_WORKSPACE_DIRECTORY")
    return str(Path(workspace) / candidate) if workspace else str(candidate)
