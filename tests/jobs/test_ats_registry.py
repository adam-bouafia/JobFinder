"""Tests for jobfinder.jobs.ats registry."""

from __future__ import annotations

import httpx
import pytest

from jobfinder.jobs.ats import fetch


def test_fetch_dispatches_to_the_right_ats(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, list[dict[str, str]]]:
            return {"jobs": [{"title": "X", "absolute_url": "https://x", "location": {}}]}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())

    jobs = fetch("greenhouse", "acme")

    assert jobs[0].source == "greenhouse"


def test_fetch_raises_key_error_for_unknown_source() -> None:
    with pytest.raises(KeyError):
        fetch("not-a-real-ats", "acme")
