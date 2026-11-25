"""Look up manually reviewed medication-bag summaries."""
import os

FIELDS = (
    "clinical_use", "side_effects", "warnings", "contraindications", "interactions", "red_flags",
)


def enabled():
    return os.getenv("RAG_MEDICATION_PRECOMPUTED", "false").strip().lower() == "true"


def lookup(cur, identity):
    cur.execute(
        """
        SELECT s.clinical_use, s.side_effects, s.warnings, s.contraindications,
               s.interactions, s.red_flags, s.evidence, s.leaflet_version, s.model_version
        FROM rag_v2.current_leaflet_versions v
        JOIN rag_v2.drug_summaries s USING (license_no, drug_id, leaflet_version)
        WHERE v.drug_id = %s AND v.license_no = %s AND s.verified AND s.active
        """,
        (identity["drug_id"], identity["license_number"]),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return dict(zip((*FIELDS, "evidence", "leaflet_version", "model_version"), row))
