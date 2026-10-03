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

### What it does

- Wraps the existing FastAPI app (`jobfinder.web.app`) unchanged - same
  code that runs via `jf serve` locally.
- `DATABASE_URL` comes from the `jobfinder-db` Modal Secret, attached to
  `web()`, `sync_sponsors()`, and `seed_jobs()`.
- Mounts a Modal Volume at `/data` too, but only for resume PDF uploads
  and the sponsor snapshot JSON the Chrome extension bundles - plain
  files, not a shared mutable database anymore.
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
