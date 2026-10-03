"""Shared filesystem paths for JobFinder."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent.parent

# JOBFINDER_DATA_DIR overrides where the DB/snapshot live - e.g. a mounted
# Modal Volume in deployment, instead of the repo-relative default used
# for local runs.
_data_dir_override = os.environ.get("JOBFINDER_DATA_DIR")
DATA_DIR = Path(_data_dir_override) if _data_dir_override else PROJECT_ROOT / "data"

DB_PATH = DATA_DIR / "jobfinder.db"
SPONSORS_SNAPSHOT_PATH = DATA_DIR / "sponsors_latest.json"
CONFIG_PATH = PROJECT_ROOT / "jobfinder.toml"
