# JobFinder

Personal NL job-search tool. Working name, will be renamed later.

## What this is

Cross-references job postings and companies against the IND public register
of recognised sponsors (NL visa sponsors), parses resumes (OCR), and matches
jobs by keyword/experience/country. Currently NL-only.

See `docs/architecture.md` for the full design and roadmap, and
`~/.claude/plans/zippy-pondering-scroll.md` for the original planning
session this was built from.

## Status

Phases 1-2 of the roadmap: IND sponsor registry sync + fuzzy company
matching, plus a CLI and a local web UI (`jf serve`, FastAPI + Jinja2 +
htmx) on top of it. No resume parsing or Chrome extension yet (see
docs/architecture.md for what's next). Hosting is local-first by design
(`127.0.0.1` by default) - see docs/architecture.md#hosting before adding
any deployment.

## Related, separate tool

`~/Documents/job-research/` is an older, adjacent personal tool (never
version-controlled) that finds junior/IT roles at IND sponsors using a
hardcoded CV-fit profile. It is intentionally NOT merged into this repo -
kept as a separate tool. Some of its scraping/ATS-detection logic informed
this codebase's design but was rewritten, not copied.

## Commands

```bash
uv sync                      # install deps into .venv
uv run jf sync-sponsors      # fetch + store the IND register, write snapshot
uv run jf match --company "Booking.com"
uv run jf serve               # web UI at http://127.0.0.1:8000
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy src
```

## Conventions

- Tests mirror `src/jobfinder/` under `tests/`.
- Every DB-touching function takes an explicit `db_path` parameter
  (defaulting to `paths.DB_PATH`) so tests can pass `tmp_path` without
  monkeypatching globals.
- `data/jobfinder.db` and resume uploads are gitignored (personal data).
  `data/sponsors_latest.json` is tracked (small, meaningful diffs, and
  will be consumed by the planned Chrome extension).
