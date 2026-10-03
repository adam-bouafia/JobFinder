"""Keeps deploy/modal_app.py's RUNTIME_DEPENDENCIES in sync with pyproject.toml.

Why a test and not a runtime pyproject.toml read inside modal_app.py
itself: that was tried first and broke differently in production. Modal
re-imports modal_app.py inside the remote container just to look up the
function objects, and __file__ there resolves to a different relative
depth than at local `modal deploy` time (no local repo checkout exists
remotely) - the same path expression that's correct locally raised
FileNotFoundError remotely. A hardcoded list has no environment-dependent
behaviour; this test is what catches drift instead.
"""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_deploy_runtime_dependencies_match_pyproject() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    expected = set(pyproject["project"]["dependencies"])

    spec = importlib.util.spec_from_file_location(
        "modal_app", PROJECT_ROOT / "deploy" / "modal_app.py"
    )
    assert spec is not None and spec.loader is not None
    modal_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modal_app)

    actual = set(modal_app.RUNTIME_DEPENDENCIES)

    assert actual == expected, (
        "deploy/modal_app.py's RUNTIME_DEPENDENCIES has drifted from "
        "pyproject.toml's [project.dependencies] - update the hardcoded "
        "list in modal_app.py to match."
    )
