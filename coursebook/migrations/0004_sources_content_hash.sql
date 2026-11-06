-- Coursebook schema v4 (cb.db v4, CB-015 residual).
-- Additive only: no v3 table, column, index or unique key is dropped or retyped.
--   * sources.content_hash is the revalidation baseline for every source, including pack-imported
--     rows that never had a gen_research_runs snapshot;
--   * NULL means "no baseline yet", not "unchanged": the first successful source.revalidate
--     records the hash and reports changed=false, and only a later differing fetch marks the row
--     stale;
--   * no backfill. Learner evidence, attempts and notebook entries are never rewritten.

ALTER TABLE sources ADD COLUMN content_hash TEXT;
