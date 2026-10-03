"""Tests for jobfinder.paths."""

from __future__ import annotations

import importlib
import subprocess
import sys


def test_data_dir_defaults_to_project_root_data() -> None:
    from jobfinder import paths

    assert paths.DATA_DIR == paths.PROJECT_ROOT / "data"
    assert paths.SPONSORS_SNAPSHOT_PATH == paths.DATA_DIR / "sponsors_latest.json"


def test_jobfinder_data_dir_env_var_overrides_data_dir() -> None:
    # paths.py reads the env var at import time, so this needs a fresh
    # interpreter rather than monkeypatching + reimporting in-process.
    result = subprocess.run(
        [sys.executable, "-c", "from jobfinder import paths; print(paths.DATA_DIR)"],
        env={"JOBFINDER_DATA_DIR": "/tmp/jobfinder-test-data", "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "/tmp/jobfinder-test-data"


def test_module_is_reloadable_without_env_var_leaking_across_tests() -> None:
    # Sanity check that the two tests above aren't order-dependent on each
    # other via module caching.
    from jobfinder import paths

    importlib.reload(paths)
    assert paths.DATA_DIR == paths.PROJECT_ROOT / "data"
