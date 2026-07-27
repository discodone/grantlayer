# Demo Console (local-only)

A single-page demo console for exercising a locally running GrantLayer API:
create grants, issue challenges, run `/exercise` actions, and walk the
tamper-and-verify flow against the local demo database.

**Local-only by design.** The page calls the API same-origin
(`const API = ''`), so it only works when served from the API's own origin
(or behind a proxy that forwards to it). It deliberately lives outside
`site/` — the GitHub Pages workflow publishes that directory wholesale, and
on the static site these API calls would just 404.

The tamper endpoints it uses are only mounted when the backend runs in demo
mode; they are not available on a production deployment.
