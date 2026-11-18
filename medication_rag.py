"""Enrich photographed medication results with sourced RAG evidence."""
import logging
import os
import re
import time
from medication_identity import extract_identity

logger = logging.getLogger(__name__)
SECTION_FIELDS = {
    "臨床用途（藥袋標示）": {"適應症", "臨床用途"},
    "可能副作用": {"副作用", "不良反應"},
    "警語": {"警語／注意事項", "警語", "注意事項", "禁忌"},
    "危險警訊": {"危險警訊", "嚴重警告", "黑框警告"},
}
EMPTY_VALUES = {"", "未標示", "看不清楚", "未提供", "無資料", "-", "—"}

SUPPLEMENT_FIELDS = ("臨床用途（藥袋標示）", "可能副作用", "警語", "危險警訊")


def _fields(text):
    fields = {}
    current = None
    for line in text.splitlines():
        heading = re.match(r"^\s*【([^】]+)】\s*$", line)
        if heading:
            current = heading.group(1).strip()
            if current == "藥名與含量":
                current = "藥名＋含量"
            fields[current] = ""
            continue
        match = re.match(r"^\s*[・•·＊*\-]?\s*([^：:]+)[：:](.*)$", line)
        if match and (line.lstrip().startswith(("・", "•", "·", "*", "-", "＊")) or match.group(1).strip() in ("藥名＋含量", *SUPPLEMENT_FIELDS)):
            current = match.group(1).strip()
            fields[current] = match.group(2).strip()
        elif current and line.strip():
            fields[current] = (fields[current] + "\n" + line.strip()).strip()
    return fields


def enrich_medication_result(result):
    """Preserve OCR text; append verified supplementary fields and a real duration."""
    original = result["display_text"].rstrip()
    started = time.perf_counter()
    metadata = {"status": "skipped", "sources": [], "method": "source_sections"}
    stage = "設定檢查"
    section = ""
    enabled = os.getenv("RAG_MEDICATION_ENABLED", os.getenv("RAG_ENABLED", "false"))
    try:
        if enabled.strip().lower() != "true":
            metadata["status"] = "disabled"
            section = "RAG 補充：未啟用。"
        else:
            fields = _fields(original)
            name = fields.get("藥名＋含量", "")
            missing = [key for key in SUPPLEMENT_FIELDS if fields.get(key, "").strip() in EMPTY_VALUES]
            metadata["missing_fields"] = missing
            if not name or name in ("未標示", "看不清楚"):
                metadata["status"] = "unidentified"
                section = "RAG 補充：無法確認藥品名稱，未補充資料。"
            elif not missing:
                section = "RAG 補充：可補充欄位已有內容，未執行查詢。"
            else:
                from RAG.rag.service import search_medication_sources
                stage = "藥品身分解析"
                observed = extract_identity(name)
                stage = "資料庫檢索"
                lookup = search_medication_sources(observed, top_k=30)
                sources = lookup["sources"]
                metadata["identity_match"] = lookup["identity_match"]
                if lookup["identity_match"]["status"] == "ambiguous":
                    metadata["status"] = "ambiguous"
                    section = "RAG 補充：多筆藥品符合，無法唯一確認，未補充資料。"
                elif not sources:
                    metadata["status"] = "not_found"
                    section = "RAG 補充：查無可確認為同一藥品的仿單資料，未補充資料。"
                else:
                    stage = "來源欄位對應"
                    entries = []
                    used_sources = set()
                    supplemented = []
                    for field in missing:
                        paragraphs = []
                        seen = set()
                        for i, row in enumerate(sources, 1):
                            source_section = (row.get("section") or "").strip()
                            text = (row.get("content") or "").strip()
                            if (source_section not in SECTION_FIELDS[field]
                                    or text in EMPTY_VALUES or text in seen):
                                continue
                            seen.add(text)
                            used_sources.add(i)
                            paragraphs.append(f"〔{source_section}〕{text} [{i}]")
                        if paragraphs:
                            supplemented.append(field)
                            label = "臨床用途" if field == "臨床用途（藥袋標示）" else field
                            entries.append(f"【{label}】\n" + "\n\n".join(paragraphs))
                    metadata["supplemented_fields"] = supplemented
                    metadata["unfilled_fields"] = [f for f in missing if f not in supplemented]
                    metadata["sources"] = sources
                    metadata["status"] = "completed" if entries else "no_supplement"
                    if entries:
                        references = [
                            f"[{i}] {row.get('name_zh') or row.get('name_en')}｜{row.get('section')}｜"
                            f"{row.get('license_number') or '未提供許可證'}｜{row.get('source') or '未提供來源'}"
                            for i, row in enumerate(sources, 1) if i in used_sources
                        ]
                        section = "RAG 資料庫補充（與照片內容分列）：\n" + "\n\n".join(entries)
                        section += "\n\n資料來源：\n" + "\n".join(references)
                    else:
                        section = "RAG 補充：未找到足以補充缺少欄位的證據。"
                    if metadata["unfilled_fields"]:
                        section += "\n\n未補充欄位：" + "、".join(metadata["unfilled_fields"]) + "（本次檢索資料無對應欄位的明確記載）。"
    except Exception as error:
        logger.exception("Medication RAG enrichment failed")
        metadata.update(status="failed", error_type=type(error).__name__, error_stage=stage)
        section = (f"RAG 補充：{stage}失敗（{type(error).__name__}），本次保留照片辨識結果。"
                   "\n詳細原因已記錄於伺服器日誌：Medication RAG enrichment failed。")
    elapsed = time.perf_counter() - started
    metadata["elapsed_seconds"] = elapsed
    result["rag"] = metadata
    result["display_text"] = original + "\n\n" + section
    if os.getenv("RAG_SHOW_TIMING", "true").strip().lower() in ("1", "true", "yes", "on"):
        status = metadata["status"]
        if status == "disabled":
            timing = "RAG 處理耗時：未執行（未啟用）"
        elif status in ("skipped", "unidentified"):
            timing = "RAG 處理耗時：未執行（無可查詢或補充欄位）"
        else:
            timing = f"RAG 處理耗時：{elapsed:.2f} 秒" + ("（失敗）" if status == "failed" else "")
        result["display_text"] += "\n\n" + timing
    return result
