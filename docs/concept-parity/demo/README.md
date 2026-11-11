# CP-015 starter-course run record

Two files, both generated from the demo backend's own rows. Neither is typed by hand:

| file | contents |
| --- | --- |
| `cp015-run.json` | the run record: every `jobs` row of the window, every stored `gen_validation_records` row, one `plan_attempts` entry per verdict (plus authored plans the validator never judged), per-course `sources`/`images`/`units`/`pages`, and an outcome sentence whose counts are computed from those rows |
| `cp015-live-evidence.json` | the raw companion: the same job and validation set, the provider `usage_events` behind those jobs, and the record source |

Regenerate (read-only against the backend):

```bash
python3 scripts/cp015_record.py \
  --db ~/.hermes/coursebook-test-cp015/home/plugin-data/coursebook/data.db
```

`scripts/cp015-demo-courses.py --record <path>` writes a **live progress log** while the create
flow runs, from the driver's in-memory flows. That log is not the run record and must not be
committed over it: it contains only the steps that ran in that process, so a re-run can drop
earlier jobs and verdicts. `tests/test_cp015_run_record.py` pins the contract and (when the demo DB
is present) re-derives the committed record from the DB and compares.

Reading rules:

- A `plan_attempts` entry with `validated: false` has no stored verdict. `verdict` stays `null`;
  the plan document's own claimed verdict, if any, is reported separately as `claimed_verdict` and
  `claimed_reasons` and is **not** evidence.
- `counts.host_unavailable` counts job rows whose `error_code` is `HOST_UNAVAILABLE`, split by
  `details.purpose`; it is not a narrative estimate.
- `started_at`/`finished_at` are the earliest and latest stored timestamps of the recorded rows, so
  the window cannot end before the final attempt closes.
