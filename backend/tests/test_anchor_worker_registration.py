"""GL-350b PART 2 — RED tests for the anchor cron registration in WorkerSettings.

The daily Cardano anchor job must be wired into the ARQ worker as a *cron* job
(NOT a polling interval), scheduled at the CardanoConfig cron_hour/cron_minute.
The job itself self-gates at entry (Gate 4a/4b in workers/jobs.py), so the cron
is registered unconditionally — registration is safe even when anchoring is off.

Expected RED before PART 2 GREEN: WorkerSettings has no ``cron_jobs`` attribute
and ``anchor_audit_chain`` is not in ``functions``.
"""

from __future__ import annotations

import unittest


class TestAnchorCronRegistration(unittest.TestCase):

    def test_anchor_job_registered_as_function(self):
        from backend.src.workers.jobs import anchor_audit_chain
        from backend.src.workers.worker import WorkerSettings

        assert anchor_audit_chain in WorkerSettings.functions

    def test_anchor_cron_job_scheduled_at_config_time(self):
        from backend.src.anchoring.config import CardanoConfig
        from backend.src.workers.jobs import anchor_audit_chain
        from backend.src.workers.worker import WorkerSettings

        assert hasattr(WorkerSettings, "cron_jobs"), "WorkerSettings must declare cron_jobs"
        cron_jobs = list(WorkerSettings.cron_jobs)
        anchor_crons = [c for c in cron_jobs if c.coroutine is anchor_audit_chain]
        assert len(anchor_crons) == 1, "anchor_audit_chain must be registered exactly once as a cron"

        cj = anchor_crons[0]
        cfg = CardanoConfig.from_env()
        # arq stores a scalar hour/minute as the int itself (or a set of ints).
        hour = cj.hour if isinstance(cj.hour, int) else set(cj.hour)
        minute = cj.minute if isinstance(cj.minute, int) else set(cj.minute)
        assert hour == cfg.cron_hour or (isinstance(hour, set) and cfg.cron_hour in hour)
        assert minute == cfg.cron_minute or (isinstance(minute, set) and cfg.cron_minute in minute)


if __name__ == "__main__":
    unittest.main()
