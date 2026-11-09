-- Coursebook schema v13 (cb.db v13, GM-001 contract freeze).
-- Additive only: no v12 table, column, index or unique key is dropped or retyped, and no lesson,
-- attempt, transition or evidence row is read, rewritten or backfilled.
--
-- The Game Mode program (docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md, docs/GM-CONTRACT.md) adds six
-- product surfaces. None of them is a second evidence store:
--
--   * `courses.presentation_mode` is the durable course mode. It is NULL for every existing
--     course and NULL reads as 'textbook'. There is deliberately no backfill: an old course has
--     no approved world, so claiming it is 'game' would be a fabricated fact.
--   * `course_worlds` / `world_assets` are the course-level visual kit: one governed row per
--     world revision, one artifact row per hero/cover/section/scene role. World art is
--     orientation only; it carries no evidence and is never exported in a pack.
--   * `takehome_packs` bind a rendered print artifact to `source_course_id`,
--     `source_objective_id`, `source_lesson_version` and `content_hash`. They never mutate,
--     clone or re-approve the source course.
--   * `homework_tasks` / `homework_events` are one-task objects with an append-only event trail.
--     Completion is self-reported or parent-reported; it is not a pass and not mastery.
--   * `game_engagement` is the play layer, keyed by a real action id. It is separate from
--     attempts and evidence and is excluded from parent, pack and export reads.
--   * `tutor_threads` / `tutor_turns` persist a lesson-bound tutor conversation. A turn is never
--     an attempt, a transition or evidence, and tutor text is never graded or exported.
--
-- No CHECK constraint here is derived from a value the wire contract cannot express; a new state
-- needs a new migration, not a handler that writes a string nobody validated.

ALTER TABLE courses ADD COLUMN presentation_mode TEXT
    CHECK (presentation_mode IS NULL OR presentation_mode IN ('game', 'textbook'));

CREATE TABLE course_worlds (
    id                  TEXT    NOT NULL PRIMARY KEY,
    course_id           TEXT    NOT NULL REFERENCES courses (id),
    revision            INTEGER NOT NULL DEFAULT 0,
    state               TEXT    NOT NULL DEFAULT 'not_requested'
                                CHECK (state IN ('not_requested', 'concepts_generating',
                                                 'concepts_ready', 'style_selected',
                                                 'kit_generating', 'kit_ready', 'approved',
                                                 'failed', 'stale', 'unavailable')),
    brief_json          TEXT    NOT NULL DEFAULT '{}',
    concepts_json       TEXT    NOT NULL DEFAULT '[]',
    selected_concept_id TEXT,
    style_hash          TEXT,
    kit_hash            TEXT,
    approved_hash       TEXT,
    approved_at         TEXT,
    error_json          TEXT,
    created_at          TEXT    NOT NULL,
    updated_at          TEXT    NOT NULL,
    UNIQUE (course_id, revision)
);
CREATE INDEX idx_course_worlds_course_state ON course_worlds (course_id, state);

CREATE TABLE world_assets (
    id          TEXT    NOT NULL PRIMARY KEY,
    world_id    TEXT    NOT NULL REFERENCES course_worlds (id),
    role        TEXT    NOT NULL CHECK (role IN ('hero', 'cover', 'section', 'lesson_scene')),
    section_id  TEXT,
    -- '' for course-level roles (hero, cover) and the lesson id for a lesson_scene. SQLite treats
    -- NULLs as distinct in a UNIQUE key, so the non-null key is what makes "one hero per world"
    -- an enforced fact instead of a handler convention.
    section_key TEXT    NOT NULL DEFAULT '',
    artifact_id TEXT    NOT NULL REFERENCES artifacts (id),
    style_hash  TEXT    NOT NULL,
    prompt_hash TEXT    NOT NULL,
    textless    INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL,
    UNIQUE (world_id, role, section_key)
);
CREATE INDEX idx_world_assets_world ON world_assets (world_id);
CREATE INDEX idx_world_assets_artifact ON world_assets (artifact_id);

CREATE TABLE takehome_packs (
    id                     TEXT    NOT NULL PRIMARY KEY,
    source_course_id       TEXT    NOT NULL REFERENCES courses (id),
    source_objective_id    TEXT    NOT NULL REFERENCES objectives (id),
    -- The validated lesson document the pack was built from (its version id, not a timestamp).
    source_lesson_version  TEXT    NOT NULL,
    -- Hash of the exact source lesson content the pack renders. Approval is fenced on it.
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
    updated_at             TEXT    NOT NULL,
    UNIQUE (source_course_id, source_objective_id, source_lesson_version,
            audience, kind, revision)
);
CREATE INDEX idx_takehome_packs_source ON takehome_packs (source_course_id);
CREATE INDEX idx_takehome_packs_state ON takehome_packs (state);

CREATE TABLE homework_tasks (
    id                    TEXT    NOT NULL PRIMARY KEY,
    course_id             TEXT    NOT NULL REFERENCES courses (id),
    enrollment_id         TEXT    NOT NULL REFERENCES enrollments (id),
    objective_id          TEXT    NOT NULL REFERENCES objectives (id),
    source_lesson_version TEXT    NOT NULL,
    audience              TEXT    NOT NULL CHECK (audience IN ('learner', 'parent')),
    task_kind             TEXT    NOT NULL
                                  CHECK (task_kind IN ('real_world_use', 'observe', 'label',
                                                       'practice', 'make', 'teach_back')),
    state                 TEXT    NOT NULL DEFAULT 'proposed'
                                  CHECK (state IN ('proposed', 'assigned', 'self_reported_done',
                                                   'parent_reported_done', 'skipped', 'expired')),
    revision              INTEGER NOT NULL DEFAULT 0,
    title                 TEXT    NOT NULL,
    target                TEXT    NOT NULL,
    context               TEXT    NOT NULL,
    steps_json            TEXT    NOT NULL DEFAULT '[]',
    success_criterion     TEXT    NOT NULL,
    estimated_minutes     INTEGER NOT NULL CHECK (estimated_minutes BETWEEN 3 AND 10),
    created_at            TEXT    NOT NULL,
    completed_at          TEXT
);
CREATE INDEX idx_homework_tasks_enrollment_state ON homework_tasks (enrollment_id, state);
CREATE INDEX idx_homework_tasks_course ON homework_tasks (course_id);

CREATE TABLE homework_events (
    id         TEXT    NOT NULL PRIMARY KEY,
    task_id    TEXT    NOT NULL REFERENCES homework_tasks (id),
    ordinal    INTEGER NOT NULL,
    kind       TEXT    NOT NULL
                       CHECK (kind IN ('proposed', 'assigned', 'edited', 'self_reported',
                                       'parent_reported', 'skipped', 'expired')),
    actor      TEXT    NOT NULL CHECK (actor IN ('learner', 'parent')),
    note       TEXT,
    created_at TEXT    NOT NULL,
    UNIQUE (task_id, ordinal)
);
CREATE INDEX idx_homework_events_task ON homework_events (task_id);

-- The play layer. `action_id` is an opaque id of a real recorded action (a lesson step, a
-- submitted check, a completed homework task); it is not a foreign key and this table is never
-- joined by a parent, pack, export or evidence read.
CREATE TABLE game_engagement (
    id            TEXT    NOT NULL PRIMARY KEY,
    course_id     TEXT    NOT NULL REFERENCES courses (id),
    enrollment_id TEXT    NOT NULL REFERENCES enrollments (id),
    action_kind   TEXT    NOT NULL
                          CHECK (action_kind IN ('lesson_step', 'check_submitted', 'review',
                                                 'homework_completed', 'returned')),
    action_id     TEXT    NOT NULL,
    points        INTEGER NOT NULL,
    level_after   INTEGER,
    created_at    TEXT    NOT NULL,
    UNIQUE (enrollment_id, action_kind, action_id)
);
CREATE INDEX idx_game_engagement_enrollment ON game_engagement (enrollment_id);
CREATE INDEX idx_game_engagement_course_enrollment ON game_engagement (course_id, enrollment_id);

CREATE TABLE tutor_threads (
    id            TEXT    NOT NULL PRIMARY KEY,
    course_id     TEXT    NOT NULL REFERENCES courses (id),
    enrollment_id TEXT    NOT NULL REFERENCES enrollments (id),
    objective_id  TEXT    NOT NULL REFERENCES objectives (id),
    lesson_run_id TEXT    NOT NULL REFERENCES lesson_runs (id),
    revision      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL,
    UNIQUE (lesson_run_id)
);
CREATE INDEX idx_tutor_threads_course_enrollment ON tutor_threads (course_id, enrollment_id);

CREATE TABLE tutor_turns (
    id                TEXT    NOT NULL PRIMARY KEY,
    thread_id         TEXT    NOT NULL REFERENCES tutor_threads (id),
    ordinal           INTEGER NOT NULL,
    role              TEXT    NOT NULL CHECK (role IN ('learner', 'tutor')),
    text              TEXT    NOT NULL,
    block_id          TEXT,
    selected_text     TEXT,
    source_refs_json  TEXT,
    created_at        TEXT    NOT NULL,
    UNIQUE (thread_id, ordinal)
);
CREATE INDEX idx_tutor_turns_thread ON tutor_turns (thread_id);
