# GrantLayer Full Backend Suite Runner

## Why this exists

The GrantLayer backend test suite has grown significantly through GL-116 to GL-120. The full suite now takes longer than many agent shell tool limits. Several Agent / OpenCode / Claude shell calls are killed at **120000 ms** (120 seconds) even when prompt comments claim 6-minute or 10-minute timeouts. This caused repeated false timeouts and repeated full-suite reruns.

## Workflow rules

### Coding agents

- Run **targeted tests** and **relevant regressions** for the ticket you are working on.
- Do **not** repeatedly run the full backend suite through a 120-second-limited agent shell.
- If the full suite cannot run because of tool timeout, report exactly:

  ```
  full backend suite: not_run_due_tool_timeout_limit
  ```

### Fast-Merge agents

- After merging a feature branch to `main`, run the full backend suite with a **real >= 900-second timeout** or an **interactive terminal**.
- Use the standard runner:

  ```bash
  scripts/run-full-backend-suite.sh
  ```

- Do **not** use `tail`, `grep`, or `head` as the only validation — the runner must surface real `unittest` output and exit codes.

### Post-merge main gate

- `main` must have **0 failures** and **0 errors** before push.
- Feature branches may show known review-only branch-scope false positives; `main` must be clean.

## Script behavior

- **Default timeout:** 900 seconds (15 minutes)
- **Override:** set `FULL_SUITE_TIMEOUT_SECONDS` (values below 900 are rejected unless `FULL_SUITE_ALLOW_SHORT_TIMEOUT=true`)
- **Command:** `python3 -m unittest discover backend.tests -v`
- **Exit code:** preserved from `unittest`
- **No file modifications**
- **No external service requirements**

## Agent timeout problem

Agent shell wrappers often enforce a hard 120000 ms limit regardless of prompt-level timeout comments. The full backend suite can exceed this. The runner uses the system `timeout` command (or `gtimeout` on macOS) with a safe default, but the agent wrapper itself may still kill the process. When that happens, report `not_run_due_tool_timeout_limit` and let a Fast-Merge agent with a real long-timeout environment finish the validation.
