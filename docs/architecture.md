# JobFinder architecture

## What this is

A personal job-search tool for the Dutch market. The core differentiator:
cross-reference companies and job postings against the IND public register
of recognised sponsors (https://ind.nl/en/public-register-recognised-sponsors/public-register-work),
so it's immediately clear which employers can sponsor a work-permit /
highly-skilled-migrant visa. Secondary features: resume OCR and structured
extraction, keyword/experience/country matching, and tracking companies
that accept open applications.

## Stack

- Python owns everything: IND scraping, fuzzy sponsor matching, resume
  OCR/parsing, job ingestion, scoring, CLI, and the web UI.
- A CLI (`jf`) and a local web UI (`jf serve`, FastAPI + Jinja2 + htmx)
  both sit on the same backend code - neither duplicates the other's
  logic, they're two views onto `sponsors/match.py` etc.
- PostgreSQL (hosted free on [Neon](https://neon.tech), serverless/scale-
  to-zero) for storage - moved off SQLite (2026-10-03) once this stopped
  being strictly single-user-local: Neon gives a real `DATABASE_URL` any
  deployment (Modal or otherwise) can reach, without standing up and
  operating a database server by hand.
- Meilisearch, self-hosted on Modal, for search - a derived, rebuildable
  ranked/typo-tolerant index over the jobs table, never the system of
  record. Not backed by a Modal Volume: a real Meilisearch bug ("failed
  to infer the version of the database") showed up on that filesystem,
  the same category of non-standard-write-durability problem SQLite-on-
  a-Volume had - runs on the container's own local disk instead, which
  is fine since `rescore_jobs()` already reindexes everything as a side
  effect any time it runs.

## Hosting

`jf serve` binds `127.0.0.1` by default for purely local use. Separately,
the app is also deployed on [Modal](https://modal.com) (see `deploy/`),
auto-deploying on every push to `main` via
`.github/workflows/deploy-modal.yml`. The two aren't mutually exclusive:
local-first stays the default for quick local testing, the Modal
deployment is the actually-used, always-reachable instance - see
`deploy/README.md` for the full setup (Postgres via Neon, search via
self-hosted Meilisearch, secrets).

## System architecture

```mermaid
flowchart LR
    subgraph SRC["Sources"]
        direction TB
        IND["IND sponsor register\nmonthly"]
        ATS["Company ATS boards\nGreenhouse / Lever / Ashby\nRecruitee / Workable"]
        JSEARCH["JSearch\nGoogle for Jobs, CLI-only"]
        RESUME["Uploaded resume"]
    end

    subgraph CORE["jobfinder - Python"]
        direction TB
        INGEST["Ingest + normalize"]
        DB[("PostgreSQL\nsystem of record")]
        MATCH["Sponsor match\nrapidfuzz"]
        SCORE["Resume fit score"]
        SEARCH[("Meilisearch\nderived index")]
    end

    subgraph OUT["Interfaces"]
        direction TB
        CLI["CLI - jf"]
        WEB["Web UI\nFastAPI + htmx"]
    end

    IND --> INGEST
    ATS --> INGEST
    JSEARCH --> INGEST
    RESUME --> INGEST
    INGEST --> DB
    DB <--> MATCH
    DB <--> SCORE
    DB -. "reindexed on write" .-> SEARCH

    DB --> CLI
    DB --> WEB
    SEARCH -. "ranked search,\nfalls back to DB" .-> WEB

    classDef source fill:#eceff1,stroke:#607d8b,stroke-width:1.5px,color:#263238
    classDef core fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1
    classDef out fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20

    class IND,ATS,JSEARCH,RESUME source
    class INGEST,DB,MATCH,SCORE,SEARCH core
    class CLI,WEB out
```

Grey = external source, blue = the core pipeline and storage, green = a
user-facing interface. Two optional, opt-in enhancements aren't in the
diagram since they're off by default: Azure AI Document Intelligence and
a generic OpenAI-compatible provider, both only for resume parsing.

## Sponsor registry sync

```mermaid
flowchart LR
    SRC["IND public register page\nind.nl/.../public-register-work"]
    SCRAPE["scrape.py\nhttpx GET, descriptive User-Agent\nBeautifulSoup+lxml row parse"]
    NORM["normalize.py\nlowercase, strip B.V./N.V./punctuation\nstrip stray leading symbols"]
    DB[("PostgreSQL sponsors table\nkvk, name, name_normalized, fetched_at")]
    MATCH["match.py\nrapidfuzz token_set_ratio vs name_normalized\nthreshold 90"]
    CLIOUT["jf match --company 'X'\n/ jf serve search box\nsponsor yes/no + matched name + score"]
    SNAP["export.py\nsponsors_latest.json\ntracked snapshot"]
    SCHED["systemd timer (local, monthly)\n+ GitHub Actions cron (monthly)"]

    SRC -->|"one GET per sync run"| SCRAPE --> NORM --> DB
    DB --> MATCH --> CLIOUT
    DB --> SNAP
    SCHED --> SCRAPE

    classDef source fill:#eceff1,stroke:#607d8b,stroke-width:1.5px,color:#263238
    classDef core fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1
    classDef infra fill:#fff8e1,stroke:#f9a825,stroke-width:1.5px,color:#e65100

    class SRC source
    class SCRAPE,NORM,DB,MATCH,CLIOUT,SNAP core
    class SCHED infra
```

Note: the IND page has been seen listing the same KVK number twice; the
upsert (`ON CONFLICT(kvk) DO UPDATE`) collapses that to one row, so
`jf sync-sponsors`'s reported count is distinct sponsors stored, not raw
rows parsed. Also: an earlier version of this matcher used rapidfuzz's
`WRatio` scorer, which turned out to give a false-positive ~90/100 "match"
to almost any short query against a long, unrelated company name (verified
live - it degrades to `partial_ratio * 0.9`, and a short string is
trivially "contained in" almost anything). Switched to `token_set_ratio`,
which separates real matches (90-100) from unrelated pairs (stayed at or
below 57 across every adversarial case tried). See the docstring on
`match_company` for the full reasoning and numbers.

## Risk / legal posture

| Posture | Risk | Guardrail |
| --- | --- | --- |
| IND register scraping | Low - government register published for exactly this lookup purpose; robots.txt allows it; no reuse restriction found | One GET per monthly sync, descriptive User-Agent, abort loudly if row count craters or parsing yields zero rows |
| LinkedIn/Indeed server-side bulk scraping | High - ToS risk, bot-detection fragility, risk to the account doing it | Avoided entirely - job ingestion uses direct ATS JSON endpoints instead, verified live against a real company's public Greenhouse board |
| Job aggregator APIs | Adzuna's terms (developer.adzuna.com/docs/terms_of_service) require a visible "Jobs by Adzuna" badge - conflicts with a clean, direct-to-employer open-source product, tried then dropped | JSearch (RapidAPI, openwebninja.com/terms) checked instead: commercial API-data use is explicitly licensed, no attribution badge required - but its own `job_apply_is_direct` flag turned out not to mean "employer's own domain" (verified live: every one of 10 real results was `false`, including genuine employer career pages), so results are filtered by apply-link-domain-vs-employer-name match (rapidfuzz) instead, CLI-only given the 200 req/month free tier |
| Resume content (PII) | N/A for local-only parsing | Any third-party parsing tier is opt-in only, never default |
| Web UI reachability | N/A while local-only | Defaults to `127.0.0.1`; opening it up is an explicit `--host` choice, see Hosting above |

## What's built

- **Sponsor registry sync + fuzzy match** - zero external API dependency, the actual differentiator.
- **CLI + local web UI** - `jf` commands and `jf serve` (FastAPI + Jinja2 + htmx), both backed by the same matching code. Local-only by default; see Hosting above for remote-access options.
- **Resume OCR + structured extraction** - `pdfplumber` text layer, per-page `pytesseract`/`pdf2image` OCR fallback (needs the `tesseract` system binary, not just a pip package), heuristic skills/experience/education extraction - no LLM call, no persona-biased keyword list.
- **Job ingestion + open-application tracking + resume-derived scoring** - direct ATS JSON APIs (verified live against Stripe's real Greenhouse board; Greenhouse/Lever/Ashby/Recruitee/Workable) plus JSearch (CLI-only, filtered to direct-domain results), enriched with sponsor status and an open-application flag at ingest time via `matching/score.py`.
- **PostgreSQL storage + Meilisearch search index** - storage migrated from SQLite to PostgreSQL (Neon), with a Meilisearch search index on top for ranked, typo-tolerant search - both designed to run alongside the app on Modal (see `deploy/README.md`).

Explicitly not built, by design: automatic discovery of which sponsor
uses which ATS/slug (a search-engine-based approach was considered and
rejected as too fragile - pass a known `--slug` instead), and direct
LinkedIn/Indeed server-side scraping (considered and rejected as the
same ToS-risk category as Adzuna, worse - see Risk posture above).
