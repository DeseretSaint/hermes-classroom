# CP-015 starter-course run record

Two files, both generated from the demo backend's own rows. Neither is typed by hand:

| file | contents |
| --- | --- |
| `cp015-run.json` | the run record: every `jobs` row of the window, every stored `gen_validation_records` row, one `plan_attempts` entry per verdict (plus authored plans the validator never judged), per-course `sources`/`images`/`units`/`pages`, and an outcome sentence whose counts are computed from those rows |
| `cp015-live-evidence.json` | the raw companion: the same job and validation set, the provider `usage_events` behind those jobs, and the record source |
| `cp015c-lessons-pass.json` | the CP-015c Japanese Cafe lessons pass: the three `lesson.regenerate` jobs, the unit lessons job, every section's stored state and verbatim rejection reasons, and the `course.export.read` refusal |

Regenerate (read-only against the backend):

```bash
python3 scripts/cp015_record.py \
  --db ~/.hermes/coursebook-test-cp015c/home/plugin-data/coursebook/data.db
```

`[CP-015c]` repointed the record at the Japanese Cafe Basics run's own backend
(`coursebook-test-cp015c`, `127.0.0.1:44601`, wire v26) and made the `validator` line derive from
the stored `gen_validation_records` rows instead of a constant: this run's plan verdict is an
independent pass (`z-ai/glm-5.3-flash` judging `deepseek/deepseek-v4.1-flash-1017`), and a record
that still called it `model_assessed` would be false.

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
- `counts.rejections_by_criterion` is the histogram of the criteria named in the stored
  `gen_validation_records` rejections; the outcome sentence repeats it verbatim. Neither is an
  interpretation of *why* a plan was rejected — read the `rejections[]` entries for that.
- `started_at`/`finished_at` are the earliest and latest stored timestamps of the recorded rows, so
  the window cannot end before the final attempt closes.

`[CP-015b]` replaced the outcome sentence's closing paragraph, which asserted a diagnosis ("every
plan was rejected on the same structural conflict") that outlived the rule change it described. The
sentence is now counts only: approved courses, jobs, `HOST_UNAVAILABLE` split, verdicts, the
criterion histogram and the latest stored verdict.
