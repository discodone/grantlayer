#!/usr/bin/env bash
# GrantLayer MVP — One-Command Demo Flow
# Usage: chmod +x scripts/demo.sh && ./scripts/demo.sh
# Or:    GRANTLAYER_PORT=8765 ./scripts/demo.sh
set -u
cd "$(dirname "$0")/.."

HOST="${GRANTLAYER_HOST:-127.0.0.1}"
PORT="${GRANTLAYER_PORT:-8765}"
API="http://$HOST:$PORT"
TOKEN="${GRANTLAYER_ADMIN_TOKEN:-demo-admin-2026}"

echo "========================================"
echo " GrantLayer MVP — Demo Flow"
echo "========================================"
echo
echo " Using API:  $API"
echo " Using token: $TOKEN"
echo
echo " Clean any existing demo data (start fresh) …"
rm -f data/grantlayer.db

# Trap to kill background server on exit
trap 'echo; echo "[Demo] Stopping server …"; kill $SERVER_PID 2>/dev/null; wait $SERVER_PID 2>/dev/null; echo "[Demo] Done."' EXIT

echo
echo " Starting server in background …"
GRANTLAYER_ADMIN_TOKEN="$TOKEN" python3 -m backend &
SERVER_PID=$!

# Wait for server to be ready
for i in {1..30}; do
  if curl -s "$API/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

echo " Server ready."
echo
echo "========================================"
echo " STEP 1 — Environment overview"
echo "========================================"
echo
echo "--- Health check -------------------------------------------------------"
curl -s "$API/health" | jq .

echo
echo "========================================"
echo " STEP 2 — Create a grant"
echo "========================================"
echo
echo " Admin creates a signed grant for tech-01 ('modify-config' on 'customer-a/server-1')."
echo
echo "--- POST /grants -------------------------------------------------------"
curl -s -X POST "$API/grants" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
      "subjectId": "tech-01",
      "role": "technician",
      "action": "modify-config",
      "resource": "customer-a/server-1",
      "validFrom": "'"$(date -u -Iseconds | cut -d+ -f1)"'",
      "validUntil": "'"$(date -u -d '+1 hour' -Iseconds | cut -d+ -f1)"'",
      "createdBy": "admin",
      "reason": "Scheduled maintenance"
    }' | jq .

echo
echo "========================================"
echo " STEP 3 — List grants and observe signature"
echo "========================================"
echo
echo " Each grant is automatically signed with Ed25519. Notice signaturePresent=true."
echo
echo "--- GET /grants --------------------------------------------------------"
curl -s "$API/grants" | jq '.[] | {id: .id[0:8], subject_id, role, action, resource, signaturePresent, signingKeyId, payloadHash: .payloadHash[0:16]}'

echo
echo "========================================"
echo " STEP 4 — Request a challenge"
echo "========================================"
echo
echo " The technician requests a one-time challenge before performing an action."
echo
echo "--- POST /challenges ---------------------------------------------------"
CHALLENGE_RESPONSE=$(curl -s -X POST "$API/challenges" \
  -H "Content-Type: application/json" \
  -d '{
      "subjectId": "tech-01",
      "action": "modify-config",
      "resource": "customer-a/server-1"
    }')
echo "$CHALLENGE_RESPONSE" | jq .
CHALLENGE_ID=$(echo "$CHALLENGE_RESPONSE" | jq -r '.challengeId')

echo
echo "========================================"
echo " STEP 5a — Execute protected action WITH challenge"
echo "========================================"
echo
echo " The technician sends the challengeId along with the action."
echo " Result: approved with replay-protected challenge."
echo
echo "--- POST /demo-action (with challenge) -----------------------------"
curl -s -X POST "$API/demo-action" \
  -H "Content-Type: application/json" \
  -d '{
      "subjectId": "tech-01",
      "role": "technician",
      "action": "modify-config",
      "resource": "customer-a/server-1",
      "challengeId": "'"$CHALLENGE_ID"'"
    }' | jq .

echo
echo "========================================"
echo " STEP 5b — Replay attack: reuse the same challenge"
echo "========================================"
echo
echo " Reusing the challengeId again should fail with 'already_used'."
echo
echo "--- POST /demo-action (replay) --------------------------------------"
curl -s -X POST "$API/demo-action" \
  -H "Content-Type: application/json" \
  -d '{
      "subjectId": "tech-01",
      "role": "technician",
      "action": "modify-config",
      "resource": "customer-a/server-1",
      "challengeId": "'"$CHALLENGE_ID"'"
    }' | jq .

echo
echo "========================================"
echo " STEP 6 — Revoke the grant"
echo "========================================"
echo
echo " Admin revokes the grant. All future actions for this grant will be denied."
echo
echo "--- POST /grants/:id/revoke ------------------------------------------"
GRANT_ID=$(curl -s "$API/grants" | jq -r '.[0].id')
curl -s -X POST "$API/grants/$GRANT_ID/revoke" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
      "revokedBy": "admin",
      "reason": "Emergency — abort maintenance"
    }' | jq .

echo
echo "========================================"
echo " STEP 7 — Execute action after revocation"
echo "========================================"
echo
echo " Same action, same challenge, no replay — but grant is revoked."
echo
echo "--- POST /demo-action (after revoke) --------------------------------"
curl -s -X POST "$API/demo-action" \
  -H "Content-Type: application/json" \
  -d '{
      "subjectId": "tech-01",
      "role": "technician",
      "action": "modify-config",
      "resource": "customer-a/server-1"
    }' | jq .

echo
echo "========================================"
echo " STEP 8 — View audit log"
echo "========================================"
echo
echo " Every decision, every challenge, every signature check is logged."
echo
echo "--- GET /audit-events (last 10) -------------------------------------"
curl -s "$API/audit-events?limit=10" | jq '.[] | {timestamp, subject_id: .subject_id, approved, reason: .reason[0:40], challenge_result, grant_signature_result}'

echo
echo "========================================"
echo " STEP 9 — Permission denied: wrong role"
echo "========================================"
echo
echo " A user with the wrong role tries to perform a protected action."
echo
echo "--- POST /demo-action (wrong role) ----------------------------------"
curl -s -X POST "$API/demo-action" \
  -H "Content-Type: application/json" \
  -d '{
      "subjectId": "tech-01",
      "role": "admin",
      "action": "modify-config",
      "resource": "customer-a/server-1"
    }' | jq .

echo
echo "========================================"
echo " STEP 10 — Tamper & Verify"
echo "========================================"
echo
echo " Re-create a fresh grant for the tamper demo …"
TAMPER_GRANT_RESPONSE=$(curl -s -X POST "$API/grants" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
      "subjectId": "tech-01",
      "role": "technician",
      "action": "modify-config",
      "resource": "customer-a/server-1",
      "validFrom": "'"$(date -u -Iseconds | cut -d+ -f1)"'",
      "validUntil": "'"$(date -u -d '+1 hour' -Iseconds | cut -d+ -f1)"'",
      "createdBy": "admin",
      "reason": "Tamper demo grant"
    }')
echo "$TAMPER_GRANT_RESPONSE" | jq .
TAMPER_GRANT_ID=$(echo "$TAMPER_GRANT_RESPONSE" | jq -r '.id')

echo
echo " First, action succeeds with the original (signed) grant."
curl -s -X POST "$API/demo-action" \
  -H "Content-Type: application/json" \
  -d '{
      "subjectId": "tech-01",
      "role": "technician",
      "action": "modify-config",
      "resource": "customer-a/server-1"
    }' | jq '{approved, grantSignatureResult}'

echo
echo " Now, tamper the grant (admin-only endpoint)."
curl -s -X POST "$API/demo/tamper-grant/$TAMPER_GRANT_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '{ok, tamperedField, oldValue, newValue}'

echo
echo " The backend detects the tamper: payloadHash no longer matches."
echo
echo "--- Tampered grant check ---------------------------------------------"
curl -s "$API/grants/$TAMPER_GRANT_ID" | jq '{id: .id[0:8], role, signaturePresent, payloadHash: .payloadHash[0:16], signatureValid}'

echo
echo "--- POST /demo-action (after tamper) --------------------------------"
curl -s -X POST "$API/demo-action" \
  -H "Content-Type: application/json" \
  -d '{
      "subjectId": "tech-01",
      "role": "tampered-role",
      "action": "modify-config",
      "resource": "customer-a/server-1"
    }' | jq .

echo
echo "========================================"
echo " Demo complete."
echo "========================================"
echo
echo " Open http://$HOST:$PORT in a browser to interact with the dashboard."
echo
echo " Press any key or Ctrl+C to stop the server …"
# Wait for user input so the dashboard stays available (only if stdin is a tty)
if [ -t 0 ]; then
  read -rs -n 1
fi
