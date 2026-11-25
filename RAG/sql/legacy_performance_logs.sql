BEGIN;
CREATE SCHEMA IF NOT EXISTS rag_v2;
CREATE TABLE IF NOT EXISTS rag_v2.performance_logs (
    request_id uuid PRIMARY KEY,
    tested_at timestamptz NOT NULL DEFAULT now(),
    system_version text NOT NULL,
    vision_model text,
    rag_model text,
    drug_count integer CHECK (drug_count >= 0),
    vision_ms double precision CHECK (vision_ms >= 0),
    matching_ms double precision CHECK (matching_ms >= 0),
    completion_ms double precision CHECK (completion_ms >= 0),
    rag_total_ms double precision CHECK (rag_total_ms >= 0),
    total_ms double precision CHECK (total_ms >= 0),
    summary_used boolean,
    fuzzy_match_used boolean,
    model_warm boolean,
    status text NOT NULL,
    error_stage text
);
ALTER TABLE rag_v2.performance_logs
    ADD COLUMN IF NOT EXISTS sample_id text,
    ADD COLUMN IF NOT EXISTS run_no integer,
    ADD COLUMN IF NOT EXISTS dataset_version text,
    ADD COLUMN IF NOT EXISTS config_version text,
    ADD COLUMN IF NOT EXISTS reply_ms double precision CHECK (reply_ms >= 0);
CREATE INDEX IF NOT EXISTS perf_version_time_idx
    ON rag_v2.performance_logs (system_version, tested_at);
COMMIT;
