# JobFinder

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Typer](https://img.shields.io/badge/CLI-Typer-000000?logo=python&logoColor=white)
![htmx](https://img.shields.io/badge/htmx-3D72D7?logo=htmx&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white)
![Meilisearch](https://img.shields.io/badge/Meilisearch-FF5CAA?logo=meilisearch&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![Chrome Extension](https://img.shields.io/badge/Chrome%20Extension-MV3-4285F4?logo=googlechrome&logoColor=white)
![Modal](https://img.shields.io/badge/Hosting-Modal-000000?logo=modal&logoColor=white)

[![GitHub](https://img.shields.io/badge/GitHub-adam--bouafia-181717?logo=github&logoColor=white)](https://github.com/adam-bouafia)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Adam%20Bouafia-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/adam-bouafia)
[![Portfolio](https://img.shields.io/badge/Portfolio-adam--bouafia.github.io-111111?logo=googlechrome&logoColor=white)](https://adam-bouafia.github.io)

Personal job-search tool for the Dutch market. Working name - will be
renamed later.

Cross-references companies and job postings against the IND public
register of recognised sponsors, so it's immediately clear which employers
can sponsor a work-permit / highly-skilled-migrant visa. Also parses resumes
and matches jobs by keyword, experience level, and country. NL-only for now.

## Architecture

Python owns scraping, matching, resume parsing, and both the CLI and the
local web UI - they're two views over the same backend code, not separate
stacks. TypeScript owns the Chrome extension (Manifest V3), the only other
language in the project. PostgreSQL (Neon, free serverless tier) is the
system of record; Meilisearch (self-hosted on Modal) is a derived,
rebuildable search index on top of it, never the source of truth.

```mermaid
flowchart TB
    subgraph EXT_SRC["External sources, read-only"]
        IND["IND public register\nHTML table, updates monthly"]
        ATSSRC["Company ATS JSON endpoints\nGreenhouse / Lever / Ashby / Recruitee / Workable\n(the job's own direct link, no aggregator)"]
        JSEARCH["JSearch (RapidAPI)\nGoogle for Jobs aggregation\nkept only if the apply link's domain\nmatches the employer - CLI-only, jf search-jobs"]
        PAGE["LinkedIn / Indeed page\nrendered in your own logged-in browser"]
    end

    subgraph CORE["jobfinder Python package"]
        SCRAPE["sponsors/scrape.py"]
        NORM["sponsors/normalize.py"]
        MATCH["sponsors/match.py\nrapidfuzz token_set_ratio"]
        EXPORT["sponsors/export.py"]
        DB[("PostgreSQL (Neon)\nsystem of record")]
        SEARCH[("Meilisearch\nderived, rebuildable index")]
        RESUME["resume/extract.py, ocr.py, fields.py"]
        JOBS["jobs/ats/*, jobs/jsearch.py, jobs/ingest.py"]
        SCORE["matching/score.py"]
        CLI["cli.py - Typer app: jf"]
        WEBAPP["web/app.py - FastAPI"]
    end

    subgraph ENH["Optional, opt-in enhancement"]
        DI["Azure AI Document Intelligence"]
        LLM["Generic OpenAI-compatible provider\n(only if a credit pool is confirmed alive)"]
    end

    subgraph EXT["Chrome extension, TypeScript MV3"]
        BUNDLE[("sponsors.json\nbundled, refreshed monthly")]
        CONTENT["content script\nsite adapters"]
        MATCHERTS["matcher.ts\nin-browser fuzzy match"]
        OVERLAY["overlay.ts\nIND Recognised Sponsor badge"]
    end

    subgraph WEB["Web UI, jf serve\n127.0.0.1 locally, also deployed on Modal"]
        TEMPLATES["Jinja2 templates + htmx\nsearch, filters, company lookup"]
    end

    IND -->|"polite monthly GET"| SCRAPE
    SCRAPE --> NORM --> DB
    DB --> MATCH --> SCORE
    DB --> EXPORT --> BUNDLE

    RESUME --> DB
    RESUME -. optional .-> DI
    RESUME -. "optional, gated" .-> LLM

    ATSSRC --> JOBS
    JSEARCH --> JOBS
    JOBS --> DB --> SCORE --> DB
    DB -. "reindexed on ingest/rescore" .-> SEARCH

    CLI --> SCRAPE
    CLI --> RESUME
    CLI --> JOBS
    CLI --> SCORE
    SEARCH -->|"ranked, typo-tolerant"| WEBAPP
    DB -.->|"fallback if search is down"| WEBAPP
    WEBAPP --> TEMPLATES

    PAGE --> CONTENT --> MATCHERTS
    BUNDLE --> MATCHERTS
    MATCHERTS --> OVERLAY -->|renders on| PAGE

    classDef source fill:#eceff1,stroke:#607d8b,stroke-width:1.5px,color:#263238
    classDef core fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1
    classDef webui fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20
    classDef extension fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c
    classDef enhancement fill:#fff8e1,stroke:#f9a825,stroke-width:1.5px,stroke-dasharray:3 3,color:#e65100

    class IND,PAGE,ATSSRC,JSEARCH source
    class SCRAPE,NORM,MATCH,EXPORT,DB,SEARCH,CLI,WEBAPP,RESUME,JOBS,SCORE core
    class DI,LLM enhancement
    class BUNDLE,CONTENT,MATCHERTS,OVERLAY extension
    class TEMPLATES webui
```

Blue = built (the whole core package, every phase), purple = the Chrome
extension (built), green = the web UI (built), gray = an external source
JobFinder reads from, amber dashed = optional opt-in enhancement (the only
pieces still off by default).

### Sponsor registry sync

The core differentiator's data pipeline - scrape, normalize, store, and
fan out to every consumer (CLI, web UI, extension):

```mermaid
flowchart LR
    SRC["IND public register page\nind.nl/.../public-register-work"]
    SCRAPE["scrape.py\nhttpx GET, descriptive User-Agent\nBeautifulSoup+lxml row parse"]
    NORM["normalize.py\nlowercase, strip B.V./N.V./punctuation\nstrip stray leading symbols"]
    DB[("PostgreSQL sponsors table\nkvk, name, name_normalized, fetched_at")]
    MATCH["match.py\nrapidfuzz token_set_ratio vs name_normalized\nthreshold 90"]
    CLIOUT["jf match --company 'X'\n/ jf serve search box\nsponsor yes/no + matched name + score"]
    SNAP["export.py\nsponsors_latest.json"]
    EXTBUNDLE["extension/src/data/sponsors.json\ncopied at extension build time"]
    SCHED["systemd timer (local, monthly)\n+ GitHub Actions cron (monthly)"]

    SRC -->|"one GET per sync run"| SCRAPE --> NORM --> DB
    DB --> MATCH --> CLIOUT
    DB --> SNAP --> EXTBUNDLE
    SCHED --> SCRAPE

    classDef source fill:#eceff1,stroke:#607d8b,stroke-width:1.5px,color:#263238
    classDef core fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1
    classDef extension fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c
    classDef infra fill:#fff8e1,stroke:#f9a825,stroke-width:1.5px,color:#e65100

    class SRC source
    class SCRAPE,NORM,DB,MATCH,CLIOUT,SNAP core
    class EXTBUNDLE extension
    class SCHED infra
```

The IND page has been seen listing the same KVK number twice; the upsert
(`ON CONFLICT(kvk) DO UPDATE`) collapses that to one row, so the reported
sync count is distinct sponsors stored, not raw rows parsed. The matcher
also used to use rapidfuzz's `WRatio` scorer, which turned out to give a
false-positive ~90/100 "match" to almost any short query against a long,
unrelated company name (verified live - it degrades to
`partial_ratio * 0.9`). Switched to `token_set_ratio`, which separates
real matches (90-100) from unrelated pairs (stayed at or below 57 across
every adversarial case tried, both in the Python matcher and its
TypeScript port in the extension).

### Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Backend / scraping / matching | Python (`httpx`, `beautifulsoup4`, `rapidfuzz`) | Mature ecosystem for all of it; one language for the whole backend |
| Resume parsing | `pdfplumber` (text layer), `pytesseract` + `pdf2image` (OCR fallback) | Local-first; OCR needs the `tesseract` system binary, not just a pip package |
| Job ingestion | Direct ATS JSON APIs (Greenhouse/Lever/Ashby/Recruitee/Workable), plus JSearch (RapidAPI, CLI-only) | ATS APIs need no auth and are always direct; JSearch aggregates Google for Jobs but is filtered to keep only results whose apply link's domain actually matches the employer - never bulk LinkedIn/Indeed scraping |
| CLI | Typer | Fast to build, matches other personal tools in this setup |
| Web UI | FastAPI + Jinja2 + htmx | Same language as the backend, no second frontend toolchain for a single-user tool; htmx gives live search without hand-written JS |
| Browser extension | TypeScript, Vite + CRXJS, Manifest V3 | Only option for a Chrome extension; bundled sponsor snapshot + in-browser matching, no runtime network calls |
| Storage | PostgreSQL (Neon, free serverless tier) | A real `DATABASE_URL` any deployment can reach, without hand-running a database server |
| Search | Meilisearch, self-hosted on Modal | Typo-tolerant, ranked search over the jobs table - derived/rebuildable from Postgres, never the source of truth; falls back to a plain Postgres query if it's ever down |
| Hosting | Local-first by default, also deployed on Modal | See Hosting below |

### Hosting

`jf serve` binds `127.0.0.1` by default for purely local use - nothing
about that has changed. The app can also run on [Modal](https://modal.com)
(see `deploy/`) - Postgres via Neon, search via self-hosted Meilisearch,
full setup in `deploy/README.md`. **Currently paused**: the deployed
instance is stopped and `deploy-modal.yml`'s auto-deploy-on-push is
disabled (both to stop billing while the repo sits idle) - redeploy with
`uv run modal deploy deploy/modal_app.py` or by re-enabling the workflow's
push trigger.

### Risk / legal posture

| Posture | Risk | Guardrail |
| --- | --- | --- |
| IND register scraping | Low - government register published for exactly this lookup purpose; robots.txt allows it; no reuse restriction found | One GET per monthly sync, descriptive User-Agent, abort loudly if row count craters or parsing yields zero rows |
| LinkedIn/Indeed server-side bulk scraping | High - ToS risk, bot-detection fragility, risk to the account doing it | Avoided entirely - job ingestion uses direct ATS JSON endpoints instead, verified live against a real company's public Greenhouse board |
| Job aggregator APIs | Adzuna's terms require a visible "Jobs by Adzuna" badge, which conflicts with a clean, direct-to-employer open-source product - tried, then dropped | JSearch (RapidAPI) checked instead: no attribution-badge requirement, commercial use explicitly licensed - but its own "is this link direct" flag turned out not to mean "employer's own domain" (verified live), so results are filtered by apply-link-domain-vs-employer-name match instead, CLI-only given its 200 req/month free tier |
| Chrome extension badge overlay | Materially lower - reads only the page already rendered in an authenticated session, same category as an ad blocker | Stays client-side only, no server-side fetch of LinkedIn/Indeed pages. The LinkedIn/Indeed CSS selectors are therefore best-effort, never checked against a live session - see `extension/README.md` |
| Resume content (PII) | N/A for local-only parsing | Any third-party parsing tier is opt-in only, never default |
| Web UI reachability | N/A while local-only | Defaults to `127.0.0.1`; opening it up is an explicit `--host` choice |

### Roadmap

All five phases from the original plan are built:

1. **Sponsor registry sync + fuzzy match** - zero external API dependency, the actual differentiator.
2. **CLI + local web UI** - `jf` commands and `jf serve` (FastAPI + Jinja2 + htmx), both backed by the same matching code.
3. **Chrome extension badge overlay** - Vite + CRXJS + TypeScript MV3, bundled sponsor snapshot, in-browser `token_set_ratio` port. Verified end-to-end in real Chrome against a simulated LinkedIn navigation.
4. **Resume OCR + structured extraction** - `pdfplumber` text layer with a per-page `pytesseract`/`pdf2image` OCR fallback, heuristic skills/experience/education extraction, no LLM call. OCR needs the `tesseract` system binary installed separately.
5. **Job ingestion + open-application tracking + resume-derived scoring** - direct ATS JSON APIs (Greenhouse/Lever/Ashby/Recruitee/Workable) plus JSearch (CLI-only, filtered to direct-domain results), enriched with sponsor status and an open-application flag at ingest time, scored against the loaded resume's skills.

Past the original five, two more have landed: **storage migrated from
SQLite to PostgreSQL** (Neon), and a **Meilisearch search index** was
added on top of it for ranked, typo-tolerant search - both deployed
alongside the app on Modal (see `deploy/README.md`).

What's explicitly NOT built, by design: automatic discovery of which
sponsor uses which ATS/slug (job-research's DuckDuckGo-based approach was
deliberately not repeated here - pass a known `--slug` instead), direct
LinkedIn/Indeed server-side scraping (considered and rejected as the same
ToS-risk category as Adzuna, worse), and any LinkedIn/Indeed-selector
verification beyond best-effort (see `extension/README.md`).

Deeper reasoning and the hackathon-credential/job-research research behind
these decisions: `~/.claude/plans/zippy-pondering-scroll.md` (local
planning notes, not in the repo).

## Quick start

```bash
uv sync
uv run jf sync-sponsors
uv run jf match --company "Booking.com"
uv run jf serve                                 # web UI at http://127.0.0.1:8000
uv run jf parse-resume path/to/resume.pdf        # OCR fallback needs tesseract installed
uv run jf fetch-jobs --source greenhouse --slug stripe
uv run jf search-jobs --query "platform engineer"   # needs a RapidAPI key, see .env
uv run jf rescore-jobs
uv run jf list-jobs --sponsors-only
```

Chrome extension: see [extension/README.md](extension/README.md).

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy src
```

## Status

All five original roadmap phases are working: sponsor registry sync,
fuzzy company matching, the CLI, the web UI, the Chrome extension, resume
parsing (OCR fallback needs `tesseract` installed separately), and job
ingestion with resume-derived scoring (direct ATS APIs need a known
company slug; JSearch adds free-text search, CLI-only, filtered to
direct-domain results). Storage is PostgreSQL (Neon), with a Meilisearch
search index on top for ranked, typo-tolerant results - both designed to
run alongside the app on Modal (see Hosting above for the current paused
state).
