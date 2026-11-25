"""Privacy-safe measurements for the existing medication scan flow."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import time
from uuid import uuid4

from RAG.rag.precomputed import enabled as precomputed_enabled


class MedicationPerformance:
    def __init__(self, received_at=None):
        use_precomputed = precomputed_enabled()
        self.data = {
            "request_id": str(uuid4()),
            "tested_at": datetime.now(timezone.utc).isoformat(),
            "system_version": "V2" if use_precomputed else "legacy",
            "vision_model": os.getenv("MEDICATION_VISION_MODEL", "gpt-4.1"),
            "rag_model": None if use_precomputed else os.getenv("RAG_CHAT_MODEL", "gpt-oss:20b"),
            "drug_count": None,
            "vision_ms": None,
            "matching_ms": None,
            "completion_ms": None,
            "rag_total_ms": None,
            "reply_ms": None,
            "total_ms": None,
            "summary_used": None,
            "fuzzy_match_used": None,
            "model_warm": None,
            "status": "failed",
            "error_stage": None,
        }
        self.started = {"total": time.perf_counter() if received_at is None else received_at}

    def start(self, name):
        self.started[name] = time.perf_counter()

    def end(self, name):
        started_at = self.started.pop(name, None)
        if started_at is not None:
            self.data[f"{name}_ms"] = (time.perf_counter() - started_at) * 1000

    @contextmanager
    def phase(self, name):
        self.start(name)
        try:
            yield
        except Exception:
            self.started.pop(name)
            self.data["error_stage"] = name
            raise
        else:
            self.end(name)

    def fail_open_phase(self):
        for name in ("completion", "matching"):
            if name in self.started:
                self.data["error_stage"] = name
                break

    def finish(self, logger, error_stage=None):
        if error_stage:
            self.data["status"] = "failed"
            # Keep a specific vision or push failure over a generic caller stage.
            if error_stage == "reply" or self.data["error_stage"] is None:
                self.data["error_stage"] = error_stage

        print("medication_performance=" + json.dumps(self.data, separators=(",", ":")), flush=True)
        if os.getenv("RAG_PERFORMANCE_DB_ENABLED", "false").strip().lower() != "true":
            return

        try:
            import psycopg
            from RAG.rag.config import DATABASE_URL

            if not DATABASE_URL:
                raise ValueError("Missing RAG database configuration")
            with psycopg.connect(
                DATABASE_URL, connect_timeout=3, options="-c statement_timeout=3000"
            ) as conn:
                conn.execute(
                    """
                    INSERT INTO rag_v2.performance_logs (
                        request_id, tested_at, system_version, vision_model, rag_model, drug_count,
                        vision_ms, matching_ms, completion_ms, rag_total_ms, reply_ms,
                        total_ms, summary_used, fuzzy_match_used, model_warm, status, error_stage
                    ) VALUES (
                        %(request_id)s, %(tested_at)s, %(system_version)s, %(vision_model)s, %(rag_model)s,
                        %(drug_count)s, %(vision_ms)s, %(matching_ms)s, %(completion_ms)s,
                        %(rag_total_ms)s, %(reply_ms)s, %(total_ms)s, %(summary_used)s,
                        %(fuzzy_match_used)s, %(model_warm)s, %(status)s, %(error_stage)s
                    ) ON CONFLICT (request_id) DO NOTHING
                    """,
                    self.data,
                )
        except Exception as error:
            logger.warning(
                "medication_performance_db_failed request_id=%s error_type=%s",
                self.data["request_id"], type(error).__name__,
            )
