# Demo Script Guide

> **DEMO ONLY — NOT FOR PRODUCTION**
>
> This script is for local demonstration purposes only. Do not run in production environments.

## What the demo proves

- **Health check**: the backend is running and responsive.
- **Grant creation**: an admin can create a time-limited, signed grant for a technician.
- **Ed25519 signatures**: every grant is automatically signed on creation (`signaturePresent: true`).
- **Challenge/proof flow**: a one-time challenge UUID is required before performing an action (5-minute TTL).
- **Replay protection**: reusing the same challenge ID is blocked (`already_used`).
- **Grant revocation**: revoking a grant immediately blocks all future actions.
- **Permission checks**: wrong role = denied, no matching grant = denied.
- **Tamper detection**: modifying a grant field without re-signing invalidates the signature and blocks the action (`hash_mismatch`).
- **Immutable audit log**: every attempt (approved or denied) is logged with challenge and signature metadata.

## What it does not prove

- No real privileged actions (no filesystem, OS, or network changes).
- No real authentication / JWT / TLS / session management.
- No production key management, HSM, or PKI.
- No blockchain, smart contracts, or testnet.
- No multi-approver (4-eyes) workflow.
- No rate limiting, horizontal scaling, or high availability.
- See [security_boundaries.md](security_boundaries.md) for the full list.

## Prerequisites

- Python 3.10+ (used: 3.13)
- `jq` installed (for JSON formatting in the terminal)
- `curl` installed
- `cryptography` Python package (for Ed25519 signatures)

## Exact commands

```bash
cd /paperclip/grantlayer-mvp
chmod +x scripts/demo.sh
./scripts/demo.sh
```

Optional environment variables:
```bash
GRANTLAYER_PORT=9000 GRANTLAYER_ADMIN_TOKEN=my-token ./scripts/demo.sh
```

## What the script does

1. Deletes `data/grantlayer.db` for a clean start.
2. Starts the backend server in the background.
3. Waits for `/health` to return 200.
4. Runs 10 steps via `curl`:
   1. **Health check** — verify backend is alive.
   2. **Create grant** — admin creates a signed grant.
   3. **List grants** — observe `signaturePresent`, `signingKeyId`, `payloadHash`.
   4. **Create challenge** — technician requests a one-time challenge.
   5a. **Demo action with challenge** — approved (`approved: true`).
   5b. **Replay attack** — same challenge reused → denied (`already_used`).
   6. **Revoke grant** — admin revokes the grant.
   7. **Action after revocation** — denied (`Grant ... has been revoked`).
   8. **Audit log** — shows all decisions with `challenge_result` and `grant_signature_result`.
   9. **Wrong role** — denied (`No matching grant for role='admin'`).
   10. **Tamper & Verify** — grant is tampered, then action is blocked (`hash_mismatch`).
5. Waits for a keypress (only in interactive mode) then shuts down the server.

## Expected output

The script prints JSON responses for each step. Key indicators of success:

| Step | Expected result |
|------|-----------------|
| 1. Health | `{"ok": true, "service": "grantlayer-mvp"}` |
| 2. Create grant | `signaturePresent: true`, `signingKeyId: "demo-ed25519-v1"` |
| 5a. Action with challenge | `approved: true`, `grantSignatureResult: "valid"` |
| 5b. Replay | `approved: false`, `reason: "Challenge invalid: already_used"` |
| 7. After revoke | `approved: false`, `reason: "Grant '...' has been revoked"` |
| 9. Wrong role | `approved: false`, `reason: "No matching grant for role='admin'..."` |
| 10. After tamper | `approved: false`, `reason: "grant_payload_hash_mismatch", signatureValid: false` |

## Troubleshooting

### `jq: command not found`
Install `jq`:
```bash
sudo apt install jq   # Debian/Ubuntu
brew install jq       # macOS
```

### `curl: (7) Failed to connect`
The server did not start or the port is already in use. Check:
```bash
lsof -i :8765
```
If occupied, kill the process or use a different port:
```bash
GRANTLAYER_PORT=9000 ./scripts/demo.sh
```

### Server starts but health check fails
Wait a few seconds and try again. The script has a 6-second retry loop. If it still fails, check for Python import errors:
```bash
python3 -m backend
```

### `POST /demo/tamper-grant/:id` fails with 404
Only signed grants can be tampered. Ensure a grant was created first (Step 2).

### `cryptography` not installed
```bash
pip install cryptography==43.0.0
```

## How to reset demo data

The script automatically resets data on each run by deleting `data/grantlayer.db` at startup.

To reset manually:
```bash
rm -f data/grantlayer.db
```

To also reset the demo Ed25519 keypair (forces regeneration on next start):
```bash
rm -f data/demo_ed25519_*.pem
```

## Warning: demo only, not production

- **Do not use** `demo-admin-2026` or any hardcoded token in production.
- **Do not commit** `data/*.db` or `data/*.pem` files (they are gitignored).
- **Do not expose** this backend to the public internet.
- **Do not rely** on this SQLite setup for production workloads.
- The `POST /demo/tamper-grant/:id` endpoint exists **only** to demonstrate tamper detection and must not exist in any production system.
