# Operator Model Default — GL-141

## Summary

`GRANTLAYER_ENABLE_OPERATOR_MODEL` now defaults to `true` when the variable is unset or empty.

Previously the default was `false`, meaning a fresh deployment without an explicit env var
silently ran in deprecated legacy admin-token mode. GL-135 remediation roadmap required this
to be corrected.

## Behavior

| `GRANTLAYER_ENABLE_OPERATOR_MODEL` value | Result |
|---|---|
| Unset or empty | Operator model **enabled** (new default) |
| `1` / `true` / `yes` / `on` (case-insensitive) | Operator model **enabled** |
| `0` / `false` / `no` / `off` (case-insensitive) | Operator model **disabled** (deprecated legacy mode) |
| Any other non-empty value | Operator model **disabled** (fail-closed) |

## Deprecated legacy mode

Setting `GRANTLAYER_ENABLE_OPERATOR_MODEL=false` continues to work as a compatibility
shim. It routes auth through the legacy `GRANTLAYER_ADMIN_TOKEN` path. This mode is
**deprecated** and will be removed in a future release. Deployments should migrate to
operator model authentication.

## What was not changed

- Auth semantics are unchanged — only the unset default changed.
- No API endpoints were added, removed, or modified.
- No OpenAPI spec changes.
- No database migrations.
- No dependency changes.
- ThreadingHTTPServer (GL-140) is preserved.
- Audit hash-chain write lock (GL-139) is preserved.

## Next issue

GL-142 — Remove BytesIO Test Hack From `_read_json`
