"""Tests for jobfinder.config."""

from __future__ import annotations

from pathlib import Path

from jobfinder.config import load


def test_load_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    config = load(path=tmp_path / "missing.toml")
    assert config.match_threshold == 90.0
    assert config.country == "NL"


def test_load_reads_values_from_file(tmp_path: Path) -> None:
    config_path = tmp_path / "jobfinder.toml"
    config_path.write_text('[sponsors]\nmatch_threshold = 85\n\n[app]\ncountry = "NL"\n')

    config = load(path=config_path)

    assert config.match_threshold == 85
    assert config.country == "NL"
