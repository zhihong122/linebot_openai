CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE IF NOT EXISTS rag_drugs (
  id BIGSERIAL PRIMARY KEY,
  source_id BIGINT UNIQUE NOT NULL,
  license_number TEXT,
  name_zh TEXT,
  name_en TEXT,
  ingredient TEXT,
  indications TEXT,
  dosage TEXT,
  contraindications TEXT,
  interactions TEXT,
  food_alcohol TEXT,
  side_effects TEXT,
  warnings TEXT,
  source_type TEXT,
  source TEXT,
  local_filename TEXT,
  recognition_method TEXT,
  raw_ocr_text TEXT,
  corrected_full_text TEXT,
  original_review_status TEXT,
  review_notes TEXT,
  original_created_at TEXT,
  original_updated_at TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  content_hash TEXT NOT NULL,
  imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS rag_drugs_name_zh_trgm ON rag_drugs USING gin (name_zh gin_trgm_ops);
CREATE INDEX IF NOT EXISTS rag_drugs_name_en_trgm ON rag_drugs USING gin (name_en gin_trgm_ops);
CREATE INDEX IF NOT EXISTS rag_drugs_ingredient_trgm ON rag_drugs USING gin (ingredient gin_trgm_ops);
CREATE INDEX IF NOT EXISTS rag_drugs_license_idx ON rag_drugs (license_number);
CREATE TABLE IF NOT EXISTS rag_chunks (
  id BIGSERIAL PRIMARY KEY,
  drug_id BIGINT NOT NULL REFERENCES rag_drugs(id) ON DELETE CASCADE,
  section TEXT NOT NULL,
  chunk_order INT NOT NULL,
  content TEXT NOT NULL,
  embedding vector(1536),
  embedding_model TEXT,
  UNIQUE(drug_id, section, chunk_order)
);
CREATE INDEX IF NOT EXISTS rag_chunks_fts_idx ON rag_chunks USING gin (to_tsvector('simple', content));
CREATE INDEX IF NOT EXISTS rag_chunks_drug_idx ON rag_chunks(drug_id);
-- 小規模資料庫先使用 exact vector search，避免 HNSW 建索引耗費資源。
