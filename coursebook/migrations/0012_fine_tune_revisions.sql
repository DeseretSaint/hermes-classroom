-- Coursebook schema v12 (cb.db v12, H-194 fine-tuning a generated course).
-- Additive only: no v11 table, column, index or unique key is dropped or retyped.
--
-- H-194: an approved course must be fine-tunable without regenerating it. Two ledgers make the
-- edit itself a durable fact, instead of an overwrite:
--
--   * `plan_revisions` records one structural change to an approved plan (a reorder / objective
--     edit / its undo) as the full objective snapshot before and after. `state` is
--     'needs_review' until `parent.final.approve` covers the exact new bytes; 'approved' then;
--     'reverted' when `plan.undo` restored the previous snapshot. `reverts_revision_id` names the
--     revision an undo reverses, so "undo last structural change" is one reversible row, never a
--     guess about recency.
--   * `lesson_revisions` records one authored edit to a single generated section: the previous
--     and new `gen_lessons` ids (both rows stay, the old one is never deleted), a review diff,
--     the attempt count the author was shown, and the explicit confirmation they gave. Only that
--     section's validation is stale; every other section keeps its state.
--
-- Neither table is read by grading. An attempt keeps pointing at the check id it was answered
-- against; an edit never rewrites an attempt, a transition or evidence. There is no backfill: a
-- pre-v12 course has no fine-tune revision, which is true.

CREATE TABLE plan_revisions (
    id                  TEXT    NOT NULL PRIMARY KEY,
    course_id           TEXT    NOT NULL REFERENCES courses (id),
    plan_id             TEXT    NOT NULL REFERENCES plans (id),
    enrollment_id       TEXT    NOT NULL REFERENCES enrollments (id),
    kind                TEXT    NOT NULL CHECK (kind IN ('reorder', 'objective_edit', 'undo')),
    state               TEXT    NOT NULL DEFAULT 'needs_review'
                                CHECK (state IN ('needs_review', 'approved', 'reverted')),
    before_json         TEXT    NOT NULL DEFAULT '[]',
    after_json          TEXT    NOT NULL DEFAULT '[]',
    plan_hash_before    TEXT    NOT NULL,
    plan_hash_after     TEXT    NOT NULL,
    review_revision     INTEGER NOT NULL,
    approval_id         TEXT    REFERENCES final_approvals (id),
    reverts_revision_id TEXT    REFERENCES plan_revisions (id),
    created_at          TEXT    NOT NULL,
    approved_at         TEXT,
    reverted_at         TEXT
);
CREATE INDEX idx_plan_revisions_plan_id ON plan_revisions (plan_id);
CREATE INDEX idx_plan_revisions_course_state ON plan_revisions (course_id, state);

CREATE TABLE lesson_revisions (
    id                          TEXT    NOT NULL PRIMARY KEY,
    course_id                   TEXT    NOT NULL REFERENCES courses (id),
    plan_id                     TEXT    NOT NULL REFERENCES plans (id),
    section_id                  TEXT    NOT NULL,
    objective_id                TEXT    NOT NULL REFERENCES objectives (id),
    from_lesson_id              TEXT    NOT NULL,
    lesson_id                   TEXT    NOT NULL,
    state                       TEXT    NOT NULL DEFAULT 'needs_review'
                                        CHECK (state IN ('needs_review', 'approved', 'superseded')),
    page_hash_before            TEXT    NOT NULL,
    page_hash_after             TEXT    NOT NULL,
    diff_json                   TEXT    NOT NULL DEFAULT '{}',
    evidence_attempts           INTEGER NOT NULL DEFAULT 0,
    confirmed_evidence_consequence INTEGER NOT NULL DEFAULT 0,
    review_revision             INTEGER NOT NULL,
    approval_id                 TEXT    REFERENCES final_approvals (id),
    created_at                  TEXT    NOT NULL,
    approved_at                 TEXT,
    UNIQUE (lesson_id)
);
CREATE INDEX idx_lesson_revisions_plan_section ON lesson_revisions (plan_id, section_id);
CREATE INDEX idx_lesson_revisions_course_state ON lesson_revisions (course_id, state);
