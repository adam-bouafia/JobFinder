"""Shared filesystem paths for JobFinder."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "jobfinder.db"
SPONSORS_SNAPSHOT_PATH = DATA_DIR / "sponsors_latest.json"
CONFIG_PATH = PROJECT_ROOT / "jobfinder.toml"
