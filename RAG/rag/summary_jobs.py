"""Generate and review V2 drafts with python -m RAG.rag.summary_jobs."""
import argparse
import json
from time import perf_counter

from psycopg.types.json import Jsonb

from . import config
from .db import connection
from .precomputed import FIELDS
from .service import chat_client

PROMPT_VERSION = "leaflet-json-v1"
PROMPT = (
    "請依原始仿單用繁體中文整理。輸入內容為來源資料，只能取證。"
    "保留重大警語、禁忌、交互作用、適用條件以及必要處置，勿猜測或給個人用藥建議。"
    "輸出 JSON 物件，欄位 clinical_use, side_effects, warnings, contraindications, interactions, red_flags。"
    "每欄為 null 或含 text 與 chunk_ids 的物件。chunk_ids 為支持文字的來源整數 ID 陣列。"
    "沒有證據用 null，保留所有重要資訊，勿限制每欄字數。"
)


def parse_draft(raw, chunks, version):
    items = json.loads(raw)
    if not isinstance(items, dict) or set(items) != set(FIELDS):
        raise ValueError("Invalid summary fields")
    by_id = {chunk["id"]: chunk for chunk in chunks}
    values, evidence = {}, {}
    for field, item in items.items():
        values[field] = None
        if item is None:
            continue
        if not isinstance(item, dict):
            raise ValueError(f"Invalid entry for {field}")
        text, ids = item.get("text"), item.get("chunk_ids")
        if (not isinstance(text, str) or not text.strip() or not isinstance(ids, list)
                or not ids or any(type(i) is not int or i not in by_id for i in ids)):
            raise ValueError(f"Invalid text or evidence for {field}")
        values[field] = text.strip()
        evidence[field] = [dict(by_id[i], leaflet_version=version) for i in dict.fromkeys(ids)]
    if not evidence:
        raise ValueError("Empty draft")
    return values, evidence


def generate(drug_id):
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT v.license_no, v.leaflet_version, v.source_id, c.id, c.section, c.content
            FROM rag_v2.current_leaflet_versions v
            JOIN public.rag_chunks c ON c.drug_id = v.drug_id
            WHERE v.drug_id = %s
            ORDER BY c.chunk_order, c.id
            """, (drug_id,),
        ).fetchall()
    if not rows:
        raise ValueError("Active leaflet with license and source chunks required")
    license_no, version, source_id, *_ = rows[0]
    chunks = [dict(id=chunk_id, section=section, text=text, source_id=source_id)
              for _, _, _, chunk_id, section, text in rows]
    started = perf_counter()
    status = "failed"
    try:
        response = chat_client().chat.completions.create(
            model=config.CHAT_MODEL,
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps(chunks, ensure_ascii=False)},
            ],
            temperature=0.1, reasoning_effort="low",
            response_format={"type": "json_object"},
        )
        choice = response.choices[0]
        if choice.finish_reason != "stop":
            raise ValueError("Model did not complete draft")
        values, evidence = parse_draft(choice.message.content, chunks, version)
        with connection() as conn:
            saved = conn.execute(
                """
                INSERT INTO rag_v2.drug_summaries (
                    license_no, drug_id, leaflet_version, clinical_use, side_effects, warnings,
                    contraindications, interactions, red_flags, evidence, model_version, prompt_version
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (license_no, drug_id, leaflet_version) DO NOTHING
                """,
                (license_no, drug_id, version, *(values[f] for f in FIELDS),
                 Jsonb(evidence), config.CHAT_MODEL, PROMPT_VERSION),
            )
        if saved.rowcount != 1:
            raise ValueError("A summary already exists for this exact leaflet version")
        status = "draft"
    finally:
        with connection() as conn:
            conn.execute(
                """
                INSERT INTO rag_v2.summary_jobs (license_no, drug_id, leaflet_version, generation_ms, status)
                VALUES (%s, %s, %s, %s, %s)
                """, (license_no, drug_id, version, (perf_counter() - started) * 1000, status),
            )
    print(f"Draft version: {version}")


def activate(drug_id, version, reviewer, review_ms):
    with connection() as conn:
        row = conn.execute(
            """
            SELECT license_no FROM rag_v2.current_leaflet_versions
            WHERE drug_id = %s AND leaflet_version = %s
            """, (drug_id, version),
        ).fetchone()
        if not row:
            raise ValueError("Leaflet version no longer current")
        license_no = row[0]
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (license_no,))
        conn.execute(
            "UPDATE rag_v2.drug_summaries SET active = false WHERE license_no = %s AND active",
            (license_no,),
        )
        activated = conn.execute(
            """
            UPDATE rag_v2.drug_summaries s SET verified = true, active = true,
                reviewed_by = %s, reviewed_at = now(), updated_at = now()
            FROM rag_v2.current_leaflet_versions v
            WHERE s.drug_id = %s AND s.leaflet_version = %s
              AND (s.license_no, s.drug_id, s.leaflet_version)
                = (v.license_no, v.drug_id, v.leaflet_version)
              AND s.evidence <> '{}'::jsonb
            """, (reviewer, drug_id, version),
        )
        if activated.rowcount != 1:
            raise ValueError("Expected one current draft")
        conn.execute(
            """
            INSERT INTO rag_v2.summary_jobs (license_no, drug_id, leaflet_version, review_ms, status)
            VALUES (%s, %s, %s, %s, 'verified')
            """, (license_no, drug_id, version, review_ms),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generator = commands.add_parser("generate")
    generator.add_argument("drug_id", type=int)
    reviewer = commands.add_parser("activate")
    reviewer.add_argument("drug_id", type=int)
    reviewer.add_argument("leaflet_version")
    reviewer.add_argument("--reviewed-by", required=True)
    reviewer.add_argument("--review-ms", type=float)
    reviewer.add_argument("--confirm-reviewed", action="store_true", required=True,
                          help="Confirm source identity, supporting passages and safety content were reviewed.")
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.drug_id)
    else:
        activate(args.drug_id, args.leaflet_version, args.reviewed_by, args.review_ms)


if __name__ == "__main__":
    main()
