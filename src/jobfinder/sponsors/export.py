"""Export the synced sponsor register as a JSON snapshot for the extension/API."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ..db import cursor
from ..paths import DB_PATH, SPONSORS_SNAPSHOT_PATH

IND_SOURCE_URL = "https://ind.nl/en/public-register-recognised-sponsors/public-register-work"


def export_snapshot(path: Path = SPONSORS_SNAPSHOT_PATH, db_path: Path = DB_PATH) -> int:
    with cursor(db_path) as conn:
        rows = conn.execute(
            "SELECT kvk, name, name_normalized FROM sponsors ORDER BY name"
        ).fetchall()

    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": IND_SOURCE_URL,
        "count": len(rows),
        "sponsors": [
            {"kvk": r["kvk"], "name": r["name"], "name_normalized": r["name_normalized"]}
            for r in rows
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return len(rows)
