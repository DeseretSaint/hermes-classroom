# D1 — a pack section over 8,000 characters imported, then was unreadable

**Owner:** Cinder (backend pack/lesson path). **Source:** `docs/sentinel-perf/PERF-REPORT.md` §3,
release-gate defect D1. **Status:** fixed on `wt/d1-section-cap`.

## The defect

`coursebook/pack_flow.py::_write_lesson_page` stored a whole section file as **one**
`lesson_segments` row (`kind='teaching'`). `cb.rpc` v6 caps `lesson.page` `segments[].text` at
`maxLength: 8000`, so any section over the cap imported successfully and then returned
`INTERNAL_ERROR` at `segments/0/text` on every read — `retryable: false`, a "Try again" that could
never succeed. `cb.pack` allows a section file of 32 MB, so nothing warned the author.

Reproduced on the pre-fix tree (`t_19da8432`, 55-objective over-cap fixture): objectives 1 and 55
failed, 53 read; the legal 60-objective course read 60/60.

## Decision: split at import (option a), refuse only what cannot fit

The 8,000-character cap and the 500-segment page budget in `cb.rpc` v6 are frozen and unchanged.
`coursebook/segments.py` reconciles them with the pack schema:

* **Long section text is cut into ordered teaching segments at import.** Cut points prefer a blank
  line, then a line end, then a word boundary, then a hard cut. A piece never ends with a dangling
  heading and never ends inside a fenced code block (unless a single fence is itself longer than the
  cap, which cannot be both whole and legal). `"".join(pieces)` is exactly the authored file — no
  character is added, dropped or rewritten, so the learner still reads the pack's own prose.
* **A lesson that could never fit the page is refused before the first database write.** If the
  objective's split pieces plus its check prompts exceed the page's 500-segment budget,
  `pack.preview` and `pack.import` return `PACK_REJECTED` naming the section file, its measured
  character count, the 8,000-character segment cap and the 500-segment page budget. Nothing is
  adopted and no course row exists.
* **The same cap now applies to live teaching snapshots.** `turn.record_assistant_snapshot` used to
  store up to 20,000 characters of assistant prose as one teaching segment; a long turn produced
  the same unreadable page. It is split the same way instead of truncated.

### Data imported before the fix

Existing courses are healed in place, without a re-import and without a schema version change.
`db.ensure_schema` runs a one-time repair (`segments.repair_stored`) guarded by
`PRAGMA user_version = 1` (the schema version still lives in `schema_migrations`; the marker only
makes the repair cost one PRAGMA read per command instead of a full text scan). The repair keeps
row ids and `created_at` for the first piece of each split row, inserts the remaining pieces, and
renumbers the run's ordinals so the page renders in reading order. It is idempotent, runs inside the
kernel's `BEGIN IMMEDIATE` fence, and skips (leaving the marker unset so the next command retries)
if the write lock or a read-only store prevents it — a repair never fails a legitimate command.

## Evidence (run, not asserted)

| check | pre-fix code | this branch |
|---|---|---|
| `make-stress-pack.py` → `seed-packs.py` → `verify-all-lessons.py`, over-cap 55 | 53/55 readable, 2 × `INTERNAL_ERROR` at `segments/0/text` | **55/55 readable**, largest segment 7,939 chars |
| same, legal 60-objective fixture | 60/60 readable | 60/60 readable |
| over-cap course **imported by the pre-fix build**, then served by this build (same DB, same enrollment, no re-import) | — | **55/55 readable**, repaired in place (7 pieces per long section, `PRAGMA user_version = 1`) |
| `python3 -m unittest discover -s tests -t .` | — | 664 tests OK (includes 12 new D1 tests) |

Boundary tests (`tests/test_segment_cap.py`): a 7,999-character section is one segment; an
8,001-character section splits and reads; a section that would need more than 500 segments is
refused with `PACK_REJECTED` naming the file and both caps; a stored over-cap row is cut in place on
the next command and reads.

## Limits worth knowing

* A single fenced code block longer than 8,000 characters is cut mid-block (the page cannot show it
  otherwise); the text is preserved exactly, but the fence renders as two open blocks.
* A repaired legacy lesson keeps all its text in the database; `lesson.page` still returns at most
  500 segments per the frozen contract, so an absurdly large legacy lesson shows its first 500.
  New imports cannot reach that state — they are refused at preview.
* The repair is a data rewrite, so a course read on this build has different `segment_id` values for
  the pieces after the first of each split row. No evidence, attempt or notebook row references a
  segment id.
