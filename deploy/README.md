# Deploying JobFinder

Local-first is still the default (see `docs/architecture.md#hosting`).
This covers the Modal path if/when you want the web UI reachable outside
this machine.

## Modal

One-time setup:

```bash
uv run modal setup   # authenticates the CLI with your Modal account
```

Deploy:

```bash
uv run modal deploy deploy/modal_app.py
```

This prints the live URL: `https://adam-bouafia--jobfinder.modal.run`
(the `web()` function uses an explicit `label="jobfinder"`, otherwise
Modal would default to the longer `<app>-<function>` form).
`uv run modal serve deploy/modal_app.py` gives a temporary preview URL
with live reload instead, for trying changes before a real deploy.

### Auto-deploy on push

`.github/workflows/deploy-modal.yml` runs `modal deploy` on every push to
`main`, authenticated via the `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET`
repo secrets (same token this CLI already uses locally - `~/.modal.toml`
after `modal setup`). No manual redeploy needed after merging a change.

### Custom domain

Checked directly against Modal's docs: custom domains need the Team plan
($250/month) - not in scope for a personal tool funded by a one-time
hackathon credit plus the free Starter tier. The `label="jobfinder"`
subdomain customization above is the free alternative and already applied.

### Postgres (Neon)

Storage moved off SQLite to a real Postgres (2026-10-03 - see
docs/architecture.md). One-time setup:

1. Create a free project at [neon.tech](https://neon.tech) and copy its
   connection string.
2. `modal secret create jobfinder-db DATABASE_URL=<neon-connection-string>`
3. Locally, put the same value in `.env` as `DATABASE_URL` (a separate
   local podman Postgres also works for local dev - see `.env`'s comment).

### Search (Meilisearch)

Self-hosted on Modal too, no external account needed - one-time setup:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"  # or any 16+ byte string
modal secret create jobfinder-search MEILI_MASTER_KEY=<the-generated-key>
```

Deploy as usual; `meilisearch_server` comes up at
`https://<workspace>--jobfinder-search.modal.run`. Deliberately **not**
backed by a Modal Volume - hit a real Meilisearch bug live ("failed to
infer the version of the database," its VERSION file not surviving a
write on that filesystem - same class of issue SQLite-on-a-Volume had).
The index runs on the container's own local disk instead: it's lost on
every restart/redeploy, which is fine since Postgres is the system of
record and `rescore_jobs()` already reindexes everything as a side
effect - the next resume upload (or `jf rescore-jobs` / `seed_jobs`
below) naturally rebuilds it. If search is ever down, the CLI/`/export`
still work fully against Postgres, and the web UI falls back to a plain
Postgres query automatically.

### What it does

- Wraps the existing FastAPI app (`jobfinder.web.app`) unchanged - same
  code that runs via `jf serve` locally.
- `DATABASE_URL` comes from the `jobfinder-db` Modal Secret, attached to
  `web()`, `sync_sponsors()`, and `seed_jobs()`. `MEILI_MASTER_KEY` from
  `jobfinder-search` is reused as `MEILISEARCH_KEY` for the same three
  functions (one secret, two env var names - see `_point_at_search()`).
- Mounts a Modal Volume at `/data` too, but only for resume PDF uploads
  and the tracked sponsor snapshot JSON - plain files, not a shared
  mutable database anymore.
- Still pinned to a single container (`max_containers=1`) - that was
  originally required (SQLite-on-a-Volume's "last write wins" risk under
  concurrent writers), Postgres removes that specific constraint, so
  it's now a deliberate simplicity choice rather than a hard requirement.
- A scheduled Modal function re-runs the IND sponsor sync monthly,
  independent of the local systemd timer / GitHub Actions cron - the
  deployed instance has its own database, so it needs its own refresh.

- `seed_jobs` pulls a company's roles directly from its ATS board
  (Greenhouse/Lever/Ashby/Recruitee/Workable) - every link is the
  employer's own posting. No aggregator (Adzuna was tried and dropped:
  its terms require a visible "Jobs by Adzuna" attribution badge, which
  conflicts with a direct-to-employer open-source product - see
  docs/architecture.md). If an old `jobfinder-adzuna` Modal Secret still
  exists from before, it's unused now and safe to delete
  (`modal secret delete jobfinder-adzuna`).

### What it doesn't do

- No custom domain / auth - it's a Modal-provided URL, unauthenticated.
  Fine for a personal tool; revisit if this becomes something other
  people use.

### First run

The database starts empty. After the first deploy, seed it once:

```bash
uv run modal run deploy/modal_app.py::sync_sponsors
uv run modal run deploy/modal_app.py::seed_jobs
```

(or just wait for the next scheduled sponsor sync - but the web UI will
show "no sponsor data yet" / "0 jobs found" until then.)

`seed_jobs` isn't scheduled - run it again with a different company to
add more roles to the live site:

```bash
uv run modal run deploy/modal_app.py::seed_jobs --source lever --slug some-company
```

### JSearch (CLI-only, not deployed)

`jf search-jobs --query "..."` (see `jobs/jsearch.py`) runs locally
only, against the local `DATABASE_URL`/`.env` - deliberately not wired
into Modal at all. Its free tier is 200 requests/month, far too scarce
to call from the live web app's search; results write to whatever
Postgres `DATABASE_URL` points at, so pointing `.env` at the Neon URL
before running it adds results to the live site the same way `seed_jobs`
does.
