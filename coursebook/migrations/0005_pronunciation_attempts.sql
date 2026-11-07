-- Coursebook schema v5 (cb.db v5, M3-B1 pronunciation backend).
-- Additive only: no v4 table, column, index or unique key is dropped or retyped.
--
-- One new table holds a pronunciation practice attempt. It is deliberately separate from
-- `attempts` (a text/selection answer graded against a check): a pronunciation result never
-- closes a check, advances an objective, bumps an enrollment revision or writes a transition.
-- The table stores the typed assessment (transcript, target, provider, model, accuracies, words,
-- verdict) with `evidence_class = 'model_assessed'`. It stores no audio: the take is a private
-- temporary file that is deleted after scoring. No raw audio can therefore reach a pack or export.
--
-- `disputes_json` is the learner's dispute trail; a dispute never rewrites the verdict.

CREATE TABLE pronunciation_attempts (
    id                TEXT    NOT NULL PRIMARY KEY,
    enrollment_id     TEXT    NOT NULL REFERENCES enrollments (id),
    objective_id      TEXT    NOT NULL REFERENCES objectives (id),
    attempt_nonce     TEXT    NOT NULL,
    target            TEXT    NOT NULL,
    locale            TEXT    NOT NULL,
    transcript        TEXT    NOT NULL,
    provider          TEXT    NOT NULL,
    model             TEXT,
    language          TEXT,
    unit              TEXT    NOT NULL CHECK (unit IN ('word', 'character')),
    word_accuracy     REAL    NOT NULL,
    phoneme_accuracy  REAL,
    confidence        REAL,
    verdict           TEXT    NOT NULL CHECK (verdict IN ('meets_target', 'close', 'needs_practice')),
    evidence_class    TEXT    NOT NULL CHECK (evidence_class IN ('model_assessed')),
    assessment_json   TEXT    NOT NULL DEFAULT '{}',
    disputes_json     TEXT    NOT NULL DEFAULT '[]',
    created_at        TEXT    NOT NULL,
    UNIQUE (enrollment_id, attempt_nonce)
);
CREATE INDEX idx_pronunciation_attempts_enrollment_id
    ON pronunciation_attempts (enrollment_id);
CREATE INDEX idx_pronunciation_attempts_objective_id
    ON pronunciation_attempts (objective_id);
