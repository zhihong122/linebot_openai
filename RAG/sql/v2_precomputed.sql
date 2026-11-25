BEGIN;
CREATE SCHEMA IF NOT EXISTS rag_v2;

-- Hash the current source identity and ordered leaflet contents. A changed
-- leaflet immediately makes its previous summary ineligible for online use.
CREATE VIEW rag_v2.current_leaflet_versions AS
SELECT d.id AS drug_id, d.license_number AS license_no, d.source_id,
       encode(sha256(convert_to(jsonb_build_array(
           d.source_id, d.source, d.name_zh, d.name_en, d.ingredient,
           jsonb_agg(jsonb_build_array(c.id, c.section, c.content)
                     ORDER BY c.chunk_order, c.id)
       )::text, 'UTF8')), 'hex') AS leaflet_version
FROM public.rag_drugs d
JOIN public.rag_chunks c ON c.drug_id = d.id
WHERE d.is_active AND btrim(d.license_number) <> ''
GROUP BY d.id, d.license_number, d.source_id, d.source, d.name_zh, d.name_en, d.ingredient;

CREATE TABLE rag_v2.drug_summaries (
    license_no text NOT NULL,
    leaflet_version text NOT NULL,
    drug_id bigint NOT NULL,
    clinical_use text,
    side_effects text,
    warnings text,
    contraindications text,
    interactions text,
    red_flags text,
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    verified boolean NOT NULL DEFAULT false,
    active boolean NOT NULL DEFAULT false,
    model_version text NOT NULL,
    prompt_version text NOT NULL,
    reviewed_by text,
    reviewed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (license_no, drug_id, leaflet_version),
    CHECK (NOT active OR verified),
    CHECK (NOT verified OR (reviewed_at IS NOT NULL AND btrim(reviewed_by) <> '' AND reviewed_by IS NOT NULL))
);

CREATE UNIQUE INDEX one_active_summary
    ON rag_v2.drug_summaries (license_no) WHERE active;

CREATE TABLE rag_v2.summary_jobs (
    job_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    license_no text NOT NULL,
    drug_id bigint NOT NULL,
    leaflet_version text NOT NULL,
    generation_ms double precision CHECK (generation_ms >= 0),
    review_ms double precision CHECK (review_ms >= 0),
    status text NOT NULL CHECK (status IN ('draft', 'failed', 'verified')),
    created_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
