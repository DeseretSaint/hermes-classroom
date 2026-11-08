-- Coursebook schema v11 (cb.db v11).
-- Additive only: no v10 table, column, index or unique key is dropped or retyped.
--
-- Conversation practice (docs/CONVERSATION-PRACTICE.md §10). Two tables:
--
--   practice_sessions  one row per attempt at a practice, inside one lesson run. State is
--                      active|graded|cancelled|abandoned; "turn limit reached" is derived from the
--                      learner turns and never stored. `attempt_id` is set only by practice.end,
--                      through the same domain._commit_attempt path attempt.submit uses.
--   practice_turns     append-only learner and tutor turns. The grader reads the learner rows
--                      only, so nothing the tutor says can produce a pass.
--
-- No backfill: a pre-v11 database had no practice, which is true. `lesson_segments` is not a
-- writer of this data; practice dialogue is not teaching prose and must not appear in the
-- Textbook page as a second copy of the conversation.

CREATE TABLE practice_sessions (
    id            TEXT    NOT NULL PRIMARY KEY,
    enrollment_id TEXT    NOT NULL REFERENCES enrollments (id),
    objective_id  TEXT    NOT NULL REFERENCES objectives (id),
    check_id      TEXT    NOT NULL REFERENCES checks (id),
    check_version INTEGER NOT NULL,
    lesson_run_id TEXT    NOT NULL REFERENCES lesson_runs (id),
    state         TEXT    NOT NULL CHECK (state IN ('active', 'graded', 'cancelled', 'abandoned')),
    attempt_id    TEXT    REFERENCES attempts (id),
    revision      INTEGER NOT NULL DEFAULT 0,
    started_at    TEXT    NOT NULL,
    ended_at      TEXT,
    end_reason    TEXT    CHECK (end_reason IS NULL OR end_reason IN ('learner_cancelled', 'binding_detached', 'run_paused'))
);
CREATE INDEX idx_practice_sessions_run_check ON practice_sessions (lesson_run_id, check_id);
CREATE INDEX idx_practice_sessions_enrollment ON practice_sessions (enrollment_id);
CREATE INDEX idx_practice_sessions_state ON practice_sessions (state);

CREATE TABLE practice_turns (
    id         TEXT    NOT NULL PRIMARY KEY,
    session_id TEXT    NOT NULL REFERENCES practice_sessions (id),
    ordinal    INTEGER NOT NULL,
    speaker    TEXT    NOT NULL CHECK (speaker IN ('learner', 'tutor')),
    text       TEXT    NOT NULL,
    nonce      TEXT,
    created_at TEXT    NOT NULL
);
CREATE UNIQUE INDEX idx_practice_turns_session_ordinal ON practice_turns (session_id, ordinal);
CREATE UNIQUE INDEX idx_practice_turns_session_nonce ON practice_turns (session_id, nonce);
CREATE INDEX idx_practice_turns_session ON practice_turns (session_id);
