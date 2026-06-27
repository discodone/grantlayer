# Docker secrets for the anchoring worker

The `worker` service in `docker-compose.yml` mounts two files as Docker secrets
at `/run/secrets/<NAME>`, where the `SecretResolver` file source picks them up
(priority: Vault > `/run/secrets` file > env var).

| File (you create it)    | Secret name                        | Contents                                              |
|-------------------------|------------------------------------|-------------------------------------------------------|
| `blockfrost_project_id` | `GRANTLAYER_BLOCKFROST_PROJECT_ID` | Blockfrost preprod/mainnet project id                 |
| `cardano_signing_key`   | `GRANTLAYER_CARDANO_SIGNING_KEY`   | Payment signing key `.skey` JSON envelope (in-memory) |

## These files are deliberately NOT in git

Only this `README.md` and an empty `.gitkeep` are tracked. The two data files
above are git-ignored so real key material can never be pasted into a tracked
path and committed by accident. **You must create them locally before starting
the stack** — Docker validates every `file:` secret for the whole stack at
`docker compose up`, so the stack will not boot until both files exist:

```sh
# from the repo root, before `docker compose up`:
printf '%s' "$BLOCKFROST_PROJECT_ID" > secrets/blockfrost_project_id
printf '%s' "$CARDANO_SIGNING_KEY_JSON" > secrets/cardano_signing_key
```

## Fail-closed

Anchoring is off unless `GRANTLAYER_ENABLE_CARDANO_ANCHORING=true`. Even when
enabled, an empty or missing secret resolves to `None`, so the config is not
fully configured and the daily anchor cron self-skips at entry — nothing is ever
submitted to the chain. Never fail open.

## To enable anchoring

1. Create the two files above with real values.
2. Set `GRANTLAYER_ENABLE_CARDANO_ANCHORING=true` and
   `GRANTLAYER_CARDANO_ANCHOR_WORKSPACE_ID=<ws>` in your `.env`.
3. `docker compose up -d worker`

**Never commit real secret values.** In real production prefer Vault or an
external Docker secret rather than on-disk files.
