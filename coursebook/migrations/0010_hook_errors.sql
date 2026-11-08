-- Coursebook schema v10 (cb.db v10).
-- Additive only: no v9 table or column is dropped or retyped.
--
-- `hook_errors` is the durable record of a chat-lifecycle observer that could not complete its
-- write. Before v10, `hooks.post_llm_call` wrapped `turn.record_assistant_snapshot` in
-- `except Exception: return None`; that snapshot is the only writer of `lesson_segments`
-- (kind='teaching'), so a failed write removed a teaching turn from the Textbook/Guided page with
-- no marker and no error anywhere. The hook still never gates the turn: it retries once and then
-- records the loss here, and `binding.get` reports the per-run count to the pane.
--
-- This table is diagnostics only. Nothing renders it as lesson text, evidence or a grade.

CREATE TABLE hook_errors (
    id            TEXT    NOT NULL PRIMARY KEY,
    kind          TEXT    NOT NULL CHECK (kind IN ('snapshot_write_failed')),
    session_id    TEXT,
    lesson_run_id TEXT    REFERENCES lesson_runs (id),
    nonce         TEXT,
    detail        TEXT    NOT NULL,
    attempts      INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL
);
CREATE INDEX idx_hook_errors_lesson_run_id ON hook_errors (lesson_run_id);
CREATE INDEX idx_hook_errors_created_at ON hook_errors (created_at);
