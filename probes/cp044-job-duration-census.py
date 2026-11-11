"""CP-044 evidence: worst-case legitimate job duration across the disposable test homes.

Read-only. Prints the top job durations (seconds, created_at -> updated_at) per test home so the
1800 s attempt budget can be justified against measured jobs rather than a single anecdote.
"""

from __future__ import annotations

import glob
import os
import sqlite3
from datetime import datetime


def homes() -> list[str]:
    return sorted(glob.glob(os.path.expanduser("~/.hermes/coursebook-test-*")))


def main() -> int:
    seen: dict[tuple[str, str], tuple[float, str, str, str, str]] = {}
    for home in homes():
        for db in glob.glob(os.path.join(home, "home/plugin-data/coursebook/data*.db")):
            try:
                conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=0.5)
                rows = list(conn.execute("select id, kind, state, created_at, updated_at from jobs"))
                conn.close()
            except Exception:  # noqa: BLE001 - a locked/partial clone is not evidence
                continue
            for job_id, kind, state, created, updated in rows:
                if not created or not updated:
                    continue
                try:
                    start = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                except ValueError:
                    continue
                seconds = (end - start).total_seconds()
                if seconds <= 0:
                    continue
                key = (job_id, created)
                if key not in seen or seen[key][0] < seconds:
                    seen[key] = (seconds, state, kind, created, home)

    ordered = sorted(seen.items(), key=lambda item: item[1][0], reverse=True)
    print(f"distinct job rows: {len(seen)}")
    for (job_id, _created), (seconds, state, kind, created, home) in ordered[:10]:
        print(f"{seconds:8.1f}s  {state:10s} {kind:6s} {job_id}  {created}  {os.path.basename(home)}")

    completed = [v[0] for v in seen.values() if v[1] == "completed"]
    print(f"completed jobs: {len(completed)}  slowest: {max(completed):.1f}s" if completed else "no completed jobs")
    over = [(k, v) for k, v in ordered if v[0] > 1800]
    print(f"rows above the 1800 s attempt budget: {len(over)}")
    for (job_id, _), (seconds, state, kind, created, home) in over[:10]:
        print(f"  {seconds:8.1f}s {state} {kind} {job_id} {created} {os.path.basename(home)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
