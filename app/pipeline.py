"""Five-Stage Agentic Pipeline for Notice2Action.

Orchestrates:
Step 1: Security & Ingestion Agent (Magic-bytes, sanitization, prompt injection firewall, PDF text indexing)
Step 2: Structured Extractor Agent (XML-sandboxed LLM extraction with verbatim quotes)
Step 3: Deterministic Verifier Agent (Zero-hallucination quote grounding & quarantine audit)
Step 4: Eligibility & Cross-Audit Agent (Student profile conflict detection & rejection risk scoring)
Step 5: Action Executor Agent (Checklists, RFC-5545 .ics, clarification email, bilingual briefing)
"""

from __future__ import annotations
import time
import uuid
from datetime import datetime, timezone
from typing import List, Tuple

import pymupdf as fitz

from app.schemas import (
    SecurityShieldReport,
    PageIndexedText,
    StudentProfile,
    Notice2ActionResponse,
    PipelineTelemetry
)
from app.security import (
    validate_pdf_bytes,
    sanitize_text,
    scan_for_prompt_injection,
    build_xml_sandboxed_document,
    MAX_ALLOWED_PAGES
)
from app.llm_router import run_llm_extraction
from app.verifier import audit_extraction_grounding, audit_student_cross_conflicts
from app.actions import (
    generate_action_items,
    generate_rfc5545_ics,
    generate_clarification_email,
    generate_bilingual_summary
)


class Notice2ActionPipeline:
    """The central orchestrator for the Notice2Action 5-stage agentic workflow."""

    def __init__(self):
        pass

    def run_pipeline(
        self,
        pdf_bytes: bytes,
        student_profile: StudentProfile
    ) -> Notice2ActionResponse:
        total_start = time.perf_counter()
        step_latencies = {}

        # ---------------------------------------------------------
        # STEP 1: Security & Ingestion Agent
        # ---------------------------------------------------------
        s1_start = time.perf_counter()
        is_valid_magic, magic_err = validate_pdf_bytes(pdf_bytes)
        if not is_valid_magic:
            raise ValueError(f"Security Shield Violation: {magic_err}")

        # Parse PDF with PyMuPDF
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(doc)
            if total_pages > MAX_ALLOWED_PAGES:
                raise ValueError(
                    f"Document page count ({total_pages}) exceeds maximum allowed cap of {MAX_ALLOWED_PAGES} pages."
                )

            pages: List[PageIndexedText] = []
            total_sanitized_chars = 0
            full_raw_text = []

            for page_idx in range(total_pages):
                page = doc[page_idx]
                raw_text = page.get_text("text") or ""
                clean_text, san_count = sanitize_text(raw_text)
                total_sanitized_chars += san_count
                pages.append(
                    PageIndexedText(
                        page_number=page_idx + 1,
                        text_content=clean_text,
                        char_count=len(clean_text)
                    )
                )
                full_raw_text.append(clean_text)

            doc.close()
        except Exception as e:
            if "Security Shield" in str(e) or "exceeds maximum" in str(e):
                raise
            raise ValueError(f"PDF extraction error: {e}")

        # Prompt injection scan across document
        combined_text = "\n".join(full_raw_text)
        has_injection, threat_lvl, injection_snippets = scan_for_prompt_injection(combined_text)

        # XML sandboxing
        xml_sandboxed_doc = build_xml_sandboxed_document(pages)

        security_report = SecurityShieldReport(
            magic_bytes_valid=True,
            detected_mime_type="application/pdf",
            file_size_bytes=len(pdf_bytes),
            total_pages=total_pages,
            sanitization_applied=total_sanitized_chars > 0,
            sanitized_chars_count=total_sanitized_chars,
            prompt_injection_detected=has_injection,
            injection_threat_level=threat_lvl,  # type: ignore
            quarantined_snippets=injection_snippets,
            security_verdict="SUSPICIOUS" if has_injection else "CLEAN"
        )
        step_latencies["step_1_ingestion_and_security_ms"] = round((time.perf_counter() - s1_start) * 1000, 2)

        # ---------------------------------------------------------
        # STEP 2: Structured Extractor Agent (XML-Sandboxed LLM)
        # ---------------------------------------------------------
        s2_start = time.perf_counter()
        extraction, llm_engine = run_llm_extraction(xml_sandboxed_doc, pages)
        step_latencies["step_2_structured_extraction_ms"] = round((time.perf_counter() - s2_start) * 1000, 2)

        # ---------------------------------------------------------
        # STEP 3: Deterministic Verifier Agent
        # ---------------------------------------------------------
        s3_start = time.perf_counter()
        grounding_report = audit_extraction_grounding(extraction, pages)
        step_latencies["step_3_grounding_audit_ms"] = round((time.perf_counter() - s3_start) * 1000, 2)

        # ---------------------------------------------------------
        # STEP 4: Eligibility & Cross-Audit Agent
        # ---------------------------------------------------------
        s4_start = time.perf_counter()
        cross_audit = audit_student_cross_conflicts(extraction, student_profile)
        step_latencies["step_4_cross_conflict_audit_ms"] = round((time.perf_counter() - s4_start) * 1000, 2)

        # ---------------------------------------------------------
        # STEP 5: Action Executor Agent
        # ---------------------------------------------------------
        s5_start = time.perf_counter()
        action_items = generate_action_items(extraction, cross_audit, student_profile)
        ics_content = generate_rfc5545_ics(extraction, student_profile.name)
        email_draft = generate_clarification_email(extraction, cross_audit, student_profile)
        bilingual_sum = generate_bilingual_summary(extraction, cross_audit, student_profile)
        step_latencies["step_5_action_executor_ms"] = round((time.perf_counter() - s5_start) * 1000, 2)

        total_latency = round((time.perf_counter() - total_start) * 1000, 2)

        telemetry = PipelineTelemetry(
            step_latencies_ms=step_latencies,
            total_latency_ms=total_latency,
            llm_source=llm_engine,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        notice_id = f"N2A-{uuid.uuid4().hex[:8].upper()}"

        return Notice2ActionResponse(
            success=True,
            notice_id=notice_id,
            telemetry=telemetry,
            security_shield=security_report,
            extraction=extraction,
            grounding_report=grounding_report,
            cross_audit=cross_audit,
            action_items=action_items,
            bilingual_summary=bilingual_sum,
            calendar_ics=ics_content,
            clarification_email_draft=email_draft,
            raw_document_pages=total_pages
        )
