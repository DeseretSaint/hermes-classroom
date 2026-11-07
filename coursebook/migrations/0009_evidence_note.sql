-- 0009_evidence_note.sql — cb.db v9 (H-53 `observation.record`).
--
-- Additive only: one nullable column on `evidence`. No table, column, index, unique key or CHECK is
-- dropped or retyped, no existing row is rewritten and there is no backfill. A NULL `note` means the
-- row recorded no prose — not that the writer sent an empty string.
--
-- Why it exists: `coursebook.domain.record_observation(..., note=...)` has accepted a note since
-- CB-002 and silently dropped it, because `evidence` had no column to hold one. cb.rpc v14 appends
-- `observation.record`, whose optional `note` (bounded at 1000 characters) has to land somewhere or
-- the wire parameter is a lie.
--
-- What a note is not: it is the learner's or parent's prose about an observation. It never changes
-- the row's `layer` (1), `kind` (`observation`), `evidence_class` (`self_reported` /
-- `parent_reported`) or `attempt_id` (NULL). Recording an observation still writes no attempt, no
-- check state, no objective transition and no verdict, and `note` is read by no grading, projection,
-- pack or export path.

ALTER TABLE evidence ADD COLUMN note TEXT;
