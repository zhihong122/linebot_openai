BEGIN;
CREATE SCHEMA IF NOT EXISTS rag_v2;
CREATE FUNCTION rag_v2.identity_key(raw text) RETURNS text LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
RETURN regexp_replace(lower(normalize(raw, NFKC)), '[[:space:]]+', '', 'g');
CREATE TABLE rag_v2.drug_master (
    license_no text PRIMARY KEY, name_zh text NOT NULL, name_en text, manufacturer text,
    strength text, dosage_form text, package_size text, source_url text NOT NULL,
    source_version text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE rag_v2.leaflet_links (
    drug_id bigint PRIMARY KEY, license_no text REFERENCES rag_v2.drug_master,
    leaflet_version text, verified boolean NOT NULL DEFAULT false, evidence text,
    CHECK (NOT verified OR (license_no IS NOT NULL AND leaflet_version IS NOT NULL AND evidence IS NOT NULL))
);
CREATE TABLE rag_v2.drug_aliases (
    alias_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    license_no text NOT NULL REFERENCES rag_v2.drug_master,
    alias_type text NOT NULL CHECK (alias_type IN ('trade_name', 'name_zh', 'manufacturer')),
    alias_raw text NOT NULL, alias_norm text GENERATED ALWAYS AS (rag_v2.identity_key(alias_raw)) STORED,
    source text NOT NULL, verified boolean NOT NULL DEFAULT false,
    CHECK (alias_norm <> ''), UNIQUE (license_no, alias_type, alias_norm)
);
CREATE INDEX alias_verified_lookup ON rag_v2.drug_aliases (alias_type, alias_norm) WHERE verified;
COMMIT;
