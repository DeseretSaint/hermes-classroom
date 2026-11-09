"""Seed one expired-lease job into a home's Coursebook store — H-182/D6 live smoke helper.

Run as ``python3 h182d6_seed_expired_job.py <home>``. It imports the Coursebook package that the
backend in ``<home>`` will load (``<home>/plugins/coursebook``), migrates that home's store through
the real migration runner, and leaves one ``running`` job whose lease is two hours past due. Prints
the store the kernel resolved, the job id and its state.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

home = sys.argv[1]
os.environ["HERMES_HOME"] = home
sys.path.insert(0, os.path.join(home, "plugins", "coursebook"))

from coursebook import db, job_service  # noqa: E402  (after HERMES_HOME and sys.path are set)

db.migrate()
dead = datetime.now(timezone.utc) - timedelta(hours=2)
job = job_service.create("plan", {"goal": "h182-d6 smoke", "brief_version": 1})
job_service.claim(job["job_id"], owner="dead-worker", now=dead)
print(f"store={db.store_root()}")
print(f"job_id={job['job_id']}")
print(f"state={job_service._view(job['job_id'])['state']}")
