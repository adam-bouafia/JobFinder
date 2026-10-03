"""Tests for the ATS fetchers - the one legitimate place to mock an
external API in this codebase, since there's no way to hit a real
company's board deterministically in a test."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from jobfinder.jobs.ats import ashby, greenhouse, lever, recruitee, workable


class FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def test_greenhouse_fetch_parses_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "jobs": [
            {
                "title": "Backend Engineer",
                "location": {"name": "Amsterdam, Netherlands"},
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                "content": "<p>Build <b>backend</b> services.</p>",
            }
        ]
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(200, payload))

    jobs = greenhouse.fetch("acme")

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].location == "Amsterdam, Netherlands"
    assert jobs[0].source == "greenhouse"
    assert jobs[0].description == "Build backend services."


def test_greenhouse_fetch_returns_empty_on_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(404, {}))
    assert greenhouse.fetch("does-not-exist") == []


def test_lever_fetch_parses_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {
            "text": "Staff Engineer",
            "categories": {"location": "Remote"},
            "hostedUrl": "https://jobs.lever.co/acme/1",
            "description": "<p>Lead our platform team.</p>",
        }
    ]
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(200, payload))

    jobs = lever.fetch("acme")

    assert len(jobs) == 1
    assert jobs[0].title == "Staff Engineer"
    assert jobs[0].location == "Remote"
    assert jobs[0].source == "lever"
    assert jobs[0].description == "Lead our platform team."


def test_ashby_fetch_parses_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "jobs": [
            {
                "title": "Platform Engineer",
                "locationName": "Amsterdam",
                "jobUrl": "https://jobs.ashbyhq.com/acme/1",
                "id": "1",
                "descriptionHtml": "<p>Own our platform.</p>",
            }
        ]
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(200, payload))

    jobs = ashby.fetch("acme")

    assert len(jobs) == 1
    assert jobs[0].title == "Platform Engineer"
    assert jobs[0].source == "ashby"
    assert jobs[0].description == "Own our platform."


def test_recruitee_fetch_parses_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "offers": [
            {
                "title": "SRE",
                "location": "Amsterdam",
                "careers_url": "https://acme.recruitee.com/o/sre",
                "description": "<p>Keep things running.</p>",
            }
        ]
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(200, payload))

    jobs = recruitee.fetch("acme")

    assert len(jobs) == 1
    assert jobs[0].title == "SRE"
    assert jobs[0].source == "recruitee"
    assert jobs[0].description == "Keep things running."


def test_workable_fetch_parses_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "jobs": [
            {
                "title": "Data Engineer",
                "city": "Amsterdam",
                "country": "Netherlands",
                "shortcode": "abc123",
            }
        ]
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(200, payload))

    jobs = workable.fetch("acme")

    assert len(jobs) == 1
    assert jobs[0].title == "Data Engineer"
    assert jobs[0].location == "Amsterdam, Netherlands"
    assert jobs[0].source == "workable"
