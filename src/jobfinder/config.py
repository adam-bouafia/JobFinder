"""JobFinder configuration loader."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .paths import CONFIG_PATH


@dataclass(frozen=True)
class Config:
    match_threshold: float
    country: str


def load(path: Path = CONFIG_PATH) -> Config:
    data = tomllib.loads(path.read_text()) if path.exists() else {}
    return Config(
        match_threshold=data.get("sponsors", {}).get("match_threshold", 90.0),
        country=data.get("app", {}).get("country", "NL"),
    )
