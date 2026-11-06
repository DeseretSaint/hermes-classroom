-- Coursebook schema v3 (cb.db v3, CB-011 contract freeze).
-- Additive only: no v2 table, column, index or unique key is dropped or retyped. Impact is the
-- contract's `migration_plan`:
--   * final_approvals records the parent's lesson-set approval as a fact about two hashes
--     (plan_hash + content_hash) and carries the vocabulary value that invalidates it, so
--     "Changes need review" is storage, not a UI guess;
--   * parent_reflections records parent-reported easy/about-right/too-hard + a revisit note
--     outside every exported pack (packs.PRIVATE_FIELDS already excludes `reflection`), with no
--     evidence_class, verdict or objective-state column — a reflection is never evidence.
--
-- No backfill: a plan approved before this migration is not a content approval, and this file
-- does not invent one.

CREATE TABLE final_approvals (
    id                  TEXT    NOT NULL PRIMARY KEY,
    course_id           TEXT    NOT NULL REFERENCES courses (id),
    plan_id             TEXT    NOT NULL REFERENCES plans (id),
    plan_hash           TEXT    NOT NULL,
    content_hash        TEXT    NOT NULL,
    state               TEXT    NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'superseded')),
    invalidation_reason TEXT    CHECK (invalidation_reason IN ('plan_edited', 'content_changed', 'course_edited', 'replaced')),
    approved_at         TEXT    NOT NULL,
    superseded_at       TEXT,
    UNIQUE (course_id, plan_id, content_hash)
);
CREATE INDEX idx_final_approvals_course_id ON final_approvals (course_id);
CREATE INDEX idx_final_approvals_state ON final_approvals (state);

CREATE TABLE parent_reflections (
    id                  TEXT    NOT NULL PRIMARY KEY,
    course_id           TEXT    NOT NULL REFERENCES courses (id),
    enrollment_id       TEXT    REFERENCES enrollments (id),
    plan_id             TEXT    REFERENCES plans (id),
    difficulty          TEXT    NOT NULL CHECK (difficulty IN ('easy', 'about_right', 'too_hard')),
    revisit_note        TEXT,
    apply_to_next_draft INTEGER NOT NULL DEFAULT 1,
    plan_hash           TEXT,
    content_hash        TEXT,
    created_at          TEXT    NOT NULL
);
CREATE INDEX idx_parent_reflections_course_id ON parent_reflections (course_id);
CREATE INDEX idx_parent_reflections_created_at ON parent_reflections (created_at);
