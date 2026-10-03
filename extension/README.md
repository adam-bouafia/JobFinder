# JobFinder browser extension

Shows an "IND recognised sponsor" badge next to the company name on
LinkedIn and Indeed job pages. Runs entirely client-side - no network
calls at browse time, matches against a bundled snapshot of the IND
register.

## Load it (unpacked, for personal use)

```bash
cd extension
npm install
npm run build
```

Then in Chrome: `chrome://extensions` -> enable Developer mode -> Load
unpacked -> select `extension/dist`.

## Refreshing the sponsor data

The bundled snapshot is a copy of the repo root's `data/sponsors_latest.json`,
taken at build time. After running `jf sync-sponsors` in the repo root,
rebuild the extension (`npm run build`) and reload it in Chrome to pick up
the refresh.

## Known limitation

The LinkedIn/Indeed CSS selectors in `src/content/site-adapters/` are
best-effort - not verified against a live session (see
`../docs/architecture.md` for why). If the badge doesn't show up on a real
job page, open DevTools, inspect the actual company-name element, and
update the relevant adapter file.

## Development

```bash
npm test          # vitest
npm run typecheck
npm run dev        # HMR dev build
```
