# Claude Code PreToolUse witness hook (log-only)

`pretooluse_witness.py` witnesses every real tool call a Claude Code session
makes by exercising the same `/v1/exercise` decision endpoint the product
hardens. It is **log-only**: the decision (approved / denied / unavailable)
is appended to a local log and the tool call **always proceeds**. The hook
never blocks — not on a denial, not on an error, not on a timeout, not on a
rate limit. Enforcement would be a separate, explicitly gated decision.

**Status: built, NOT installed, NOT activated.** The API key it needs does
not exist yet (deliberately — see the gated step below).

## What is witnessed — and what is not

| Witnessed | Never witnessed |
|---|---|
| Tool name (e.g. `Bash`, `Edit`, `mcp__server__tool`) | Tool **arguments** — not raw, not hashed |
| Decision + audit event id | File paths, file contents, secrets |

Arguments may contain paths, file contents, and secrets; the audit chain is
periodically anchored on-chain, which makes any leak permanent. The hook
parses the stdin event only for `tool_name` and deliberately never touches
`tool_input`.

## Availability constraints

- Every HTTP call has a **1-second timeout** (2 calls per tool call, so a
  dead API costs at most ~2s and only until the next log line; a healthy
  local API answers in ~10 ms).
- **Rate limit:** the free tier allows **100 requests/min per workspace**,
  and the hook spends 2 requests (challenge + exercise) per tool call — a
  busy session (>50 tool calls/min) will hit 429. A 429 means the witness is
  **unavailable for that call** (logged `rate_limited`); it is never treated
  as a denial, and the tool call proceeds. Consequence: under burst load the
  witness log has honest gaps. Raising the workspace tier or an exemption
  for the hook's workspace would close them; that is a product decision.
- Any 400/401/5xx/parse failure is likewise logged `unavailable`, never
  `denied`. Only a real answer from `/v1/exercise` (200 `approved:false` or
  403) is logged as `denied` — and still allows the call.

## Activation requirements (all gated, none done)

1. **Create the subject-bound API key** (gl-393: `/v1/exercise` refuses
   unbound keys, so the binding is mandatory). Regular endpoint, no manual
   DB write — the creation is then chain-witnessed:
   `POST /v1/api-keys` with an operator JWT and `X-Workspace-Id`, body
   `{"name": "claude-code-agent", "scopes": ["read_write"], "subjectId": "claude-code-agent"}`.
   Save the response to `~/grantlayer-ops/claude-hook-agent.key.json`,
   mode 600. **This step needs Anton's explicit go.**
2. **Create a grant** for subject `claude-code-agent` covering the tool
   actions to be approved (`action` = tool name, `resource` =
   `claude-code/tool`). Without one, every call is witnessed as `denied` —
   harmless in log-only mode, but the log then measures grant coverage, not
   activity.
3. **Register the hook** in `~/.claude/settings.json`:

   ```json
   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "*",
           "hooks": [
             {
               "type": "command",
               "command": "python3 /home/adminuser/projects/grantlayer-mvp/integrations/claude-code-hook/pretooluse_witness.py",
               "timeout": 5
             }
           ]
         }
       ]
     }
   }
   ```

4. **Decide the rate-limit posture** (see above) before relying on the log
   for anything, and accept ~2 extra API requests per tool call against the
   live instance.

## Manual smoke test (safe, no key required)

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"secret --not-logged"}}' \
  | python3 integrations/claude-code-hook/pretooluse_witness.py; echo "exit=$?"
tail -1 ~/grantlayer-ops/claude-hook-decisions.log
```

Expected: `exit=0` (always), log line `tool=Bash outcome=unavailable
reason=no_key_file`, and no trace of the `tool_input` content anywhere.
