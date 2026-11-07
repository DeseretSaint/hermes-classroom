-- Coursebook schema v7 (cb.db v7, H-21 plan units).
-- Additive only: no v6 table, column, index or unique key is dropped or retyped.
--
-- Units are child rows of the one approvable plan (docs/COURSE-BLUEPRINT.md sections 3 and 4).
-- The plan approval covers units, objectives, evidence criteria and the check plan; section
-- detail is authoring output under that contract and is not part of the kernel plan hash.
--
-- No backfill and no row is rewritten. A legacy plan keeps no plan_units row and every objective
-- keeps unit_id NULL; that NULL is the implicit single unit every pre-blueprint plan already is.
-- `parent_authoring.plan_hash` therefore emits exactly the same payload for every stored plan,
-- which is what keeps every H-12 `result_json.plan_content_hash` binding valid after this file.
--
-- `gen_plan_sections` is a generation staging table: the generation module creates it lazily.
-- The migration creates it in its v6 shape when generation has not run yet, then adds the two
-- unit columns, so a fresh database and an upgraded database reach the same shape either way.
-- `section_role` is 'owner' or 'review'. `objective_refs_json` keeps its single-list meaning:
-- an owner section stores exactly one owner ref, a review section one to four earlier refs.

CREATE TABLE IF NOT EXISTS gen_plan_sections (
    id TEXT NOT NULL PRIMARY KEY,
    plan_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    plan_hash TEXT NOT NULL,
    title TEXT NOT NULL,
    lesson_intent TEXT NOT NULL,
    media_need_json TEXT,
    objective_refs_json TEXT NOT NULL DEFAULT '[]',
    context_needs_json TEXT NOT NULL DEFAULT '[]',
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(plan_id, plan_hash, ordinal)
);

ALTER TABLE gen_plan_sections ADD COLUMN unit_id TEXT;

ALTER TABLE gen_plan_sections ADD COLUMN section_role TEXT NOT NULL DEFAULT 'owner';

CREATE TABLE plan_units (
    id                        TEXT    NOT NULL PRIMARY KEY,
    plan_id                   TEXT    NOT NULL REFERENCES plans (id),
    ordinal                   INTEGER NOT NULL,
    title                     TEXT    NOT NULL,
    goal                      TEXT    NOT NULL,
    prereq_unit_ordinals_json TEXT    NOT NULL DEFAULT '[]',
    target_lessons            INTEGER NOT NULL,
    created_at                TEXT    NOT NULL,
    UNIQUE (plan_id, ordinal)
);

CREATE INDEX idx_plan_units_plan_id ON plan_units (plan_id);

ALTER TABLE objectives ADD COLUMN unit_id TEXT;
