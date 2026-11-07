-- Coursebook schema v6 (cb.db v6, H-01 plan-brief inputs).
-- Additive only: no v5 table, column, index or unique key is dropped or retyped.
--
-- The three plan-brief inputs the capability policy, research depth and planner need are stored
-- once, on the course, so `course.get` and the plan job read the same values. Before this they
-- were reachable only from `locale` (the policy's fallback), which classified a Spanish technical
-- procedure as a language lesson, and `level` was refused by the wire contract.
--
-- They are NOT dials: `dials_json` keeps exactly pace/depth/assessment/autonomy. `scope` is
-- CHECK-constrained so a value `cb.rpc` v10 cannot express is not storable.
-- No backfill: an existing course keeps NULL in all three, which means "the brief did not name
-- it" and leaves the policy's pre-v6 fallback in force.

ALTER TABLE courses ADD COLUMN level TEXT;

ALTER TABLE courses ADD COLUMN subject_domain TEXT;

ALTER TABLE courses ADD COLUMN scope TEXT CHECK (scope IS NULL OR scope IN ('single', 'short', 'full'));
