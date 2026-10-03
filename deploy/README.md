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

### What it does

- Wraps the existing FastAPI app (`jobfinder.web.app`) unchanged - same
  code that runs via `jf serve` locally.
- Mounts a Modal Volume at `/data` for the SQLite DB and sponsor snapshot,
  so data survives across deploys and restarts.
- Pinned to a single container (`max_containers=1`). Modal Volumes use
  "last write wins" under concurrent writes from multiple containers,
  which would risk corrupting the SQLite file - one container handling
  several requests at once is the right trade for a personal tool, not a
  limitation to work around.
- A scheduled Modal function re-runs the IND sponsor sync monthly,
  independent of the local systemd timer / GitHub Actions cron - the
  deployed instance has its own volume, so it needs its own refresh.

- Adzuna credentials live in a Modal Secret (`jobfinder-adzuna`, created
  via `modal secret create jobfinder-adzuna --from-dotenv .env`), used by
  the `seed_jobs` function below - the web UI itself still doesn't call
  Adzuna directly, it only ever reads what's already in the volume.

### What it doesn't do

- No custom domain / auth - it's a Modal-provided URL, unauthenticated.
  Fine for a personal tool; revisit if this becomes something other
  people use.

### First run

The volume starts empty. After the first deploy, seed it once:

```bash
uv run modal run deploy/modal_app.py::sync_sponsors
uv run modal run deploy/modal_app.py::seed_jobs
```

(or just wait for the next scheduled sponsor sync - but the web UI will
show "no sponsor data yet" / "0 jobs found" until then.)

`seed_jobs` isn't scheduled - run it again manually with a different
`--query` to top up the live site with more roles:

```bash
uv run modal run deploy/modal_app.py::seed_jobs --query "platform engineer"
```
