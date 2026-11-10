-- 0014 — a take-home pack's revision belongs to the pack, not to its source slot (GM-005).
--
-- 0013 gave takehome_packs UNIQUE (source_course_id, source_objective_id,
-- source_lesson_version, audience, kind, revision). `revision` is the per-pack
-- compare-and-swap counter: `takehome.create` always starts a new pack at revision 0 and
-- `approve` / `export` increment that same row. Under the 0013 key the counter was also a
-- per-source-slot namespace, so a second pack for the same lesson could never progress:
-- re-opening a lesson whose pack was approved (revision 1) or exported (revision 2) minted a
-- legal draft at revision 0, then failed its first approve/export with IntegrityError because
-- the predecessor row already held the number the new pack was moving to.
--
-- Rebuild takehome_packs without that key. Duplicate *drafts* are still prevented in
-- `takehome.create` (a second create returns the existing draft row instead of inserting
-- another), and `id` remains the pack's identity. No column, type, nullability, default,
-- CHECK, foreign key or index changes, and no row is rewritten: the same rows are copied
-- with the same values.

CREATE TABLE takehome_packs_v14 (
    id                     TEXT    NOT NULL PRIMARY KEY,
    source_course_id       TEXT    NOT NULL REFERENCES courses (id),
    source_objective_id    TEXT    NOT NULL REFERENCES objectives (id),
    source_lesson_version  TEXT    NOT NULL,
    content_hash           TEXT    NOT NULL,
    audience               TEXT    NOT NULL CHECK (audience IN ('learner', 'parent')),
    kind                   TEXT    NOT NULL
                                   CHECK (kind IN ('print_pack', 'activity_plan', 'homework_sheet')),
    state                  TEXT    NOT NULL DEFAULT 'draft'
                                   CHECK (state IN ('draft', 'previewed', 'approved',
                                                    'exported', 'superseded')),
    revision               INTEGER NOT NULL DEFAULT 0,
    title                  TEXT    NOT NULL,
    content_json           TEXT    NOT NULL DEFAULT '{}',
    preview_hash           TEXT,
    approval_hash          TEXT,
    approved_at            TEXT,
    artifact_id            TEXT    REFERENCES artifacts (id),
    exported_at            TEXT,
    created_at             TEXT    NOT NULL,
    updated_at             TEXT    NOT NULL
);

INSERT INTO takehome_packs_v14 (
    id, source_course_id, source_objective_id, source_lesson_version, content_hash,
    audience, kind, state, revision, title, content_json, preview_hash, approval_hash,
    approved_at, artifact_id, exported_at, created_at, updated_at
)
SELECT id, source_course_id, source_objective_id, source_lesson_version, content_hash,
       audience, kind, state, revision, title, content_json, preview_hash, approval_hash,
       approved_at, artifact_id, exported_at, created_at, updated_at
FROM takehome_packs;

DROP TABLE takehome_packs;

ALTER TABLE takehome_packs_v14 RENAME TO takehome_packs;

CREATE INDEX idx_takehome_packs_source ON takehome_packs (source_course_id);
CREATE INDEX idx_takehome_packs_state ON takehome_packs (state);
