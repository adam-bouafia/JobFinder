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

This prints the live URL. `uv run modal serve deploy/modal_app.py` gives a
temporary preview URL with live reload instead, for trying changes before
a real deploy.

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

### What it doesn't do

- No Adzuna credentials are wired up (`jf search-jobs` isn't exposed in
  the web UI today, only the CLI) - if that changes, add them as a Modal
  Secret (`modal secret create`), not hardcoded here.
- No custom domain / auth - it's a Modal-provided URL, unauthenticated.
  Fine for a personal tool; revisit if this becomes something other
  people use.

### First run

The volume starts empty. After the first deploy, seed it once:

```bash
uv run modal run deploy/modal_app.py::sync_sponsors
```

(or just wait for the next scheduled run - but the web UI will show "no
sponsor data yet" until then.)
