"""FastAPI Production Server for Notice2Action Agent.

Provides RESTful endpoints for document ingestion, agent pipeline execution,
telemetry inspection, .ics calendar downloads, and 1-click sample demo.
"""

from __future__ import annotations
import os
import json
import logging
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.schemas import StudentProfile, Notice2ActionResponse
from app.pipeline import Notice2ActionPipeline

# Load environment variables
load_dotenv()

# Logging configuration
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("notice2action.main")

# Initialize FastAPI application
app = FastAPI(
    title="Notice2Action — Autonomous Document-to-Action & Verification Agent",
    version="1.0.0",
    description="Enterprise-grade agentic workflow automation for academic & government circulars.",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache for generated calendar .ics files
calendar_cache: dict[str, str] = {}

# Initialize pipeline
pipeline = Notice2ActionPipeline()

# Mount static folder
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    """Serve the Command Center Single-Page Application."""
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return HTMLResponse("<h3>Notice2Action UI is initializing...</h3>", status_code=200)


@app.get("/api/health")
def health_check():
    """Health check endpoint providing runtime diagnostics."""
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    has_key = bool(gemini_key and not gemini_key.startswith("your_"))
    
    return {
        "status": "HEALTHY",
        "service": "Notice2Action Agent",
        "version": "1.0.0",
        "gemini_api_configured": has_key,
        "default_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "fallback_engine_ready": True,
        "pdf_parser": "PyMuPDF 2.1 (fitz)"
    }


@app.post("/api/process", response_model=Notice2ActionResponse)
def process_document(
    file: UploadFile = File(...),
    student_profile: Optional[str] = Form(None)
):
    """Execute the full 5-stage Notice2Action agentic pipeline."""
    try:
        raw_bytes = file.file.read()
        if not raw_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Parse student profile if passed as JSON string
        profile_obj = StudentProfile()
        if student_profile:
            try:
                parsed_data = json.loads(student_profile)
                profile_obj = StudentProfile.model_validate(parsed_data)
            except Exception as e:
                logger.warning(f"Could not parse custom student profile JSON ({e}), using default.")

        result = pipeline.run_pipeline(raw_bytes, profile_obj)

        # Cache calendar for download
        calendar_cache[result.notice_id] = result.calendar_ics

        return result

    except ValueError as ve:
        logger.warning(f"Validation or security violation: {ve}")
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected pipeline execution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline execution failure: {str(e)}")


@app.get("/api/demo-conflict", response_model=Notice2ActionResponse)
def run_demo_conflict():
    """1-Click Evaluation Demo: Runs the realistic AICTE circular against a conflicting student profile.
    
    Demonstrates:
    - Magic-byte verification and PDF parsing
    - XML sandboxing and prompt injection shield
    - Programmatic quote verification & grounding audit
    - Real-world conflict detection (CGPA gap, Income ceiling breach, Expired certificate, Missing Bonafide)
    - Action executor: Priorities, RFC-5545 .ics, formal clarification email, and bilingual summary
    """
    sample_pdf_path = os.path.join("samples", "sample_notice.pdf")
    if not os.path.exists(sample_pdf_path):
        from app.generate_sample import create_sample_pdf
        create_sample_pdf(sample_pdf_path)

    with open(sample_pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # Conflicting student profile designed for realistic testing
    conflicting_student = StudentProfile(
        name="Aarav Sharma",
        email="aarav.sharma@engg.edu",
        category="OBC-NCL",
        annual_income_inr=650000.0,  # Conflict: > 6,00,000 ceiling
        cgpa=7.4,                    # Conflict: < 7.5 minimum threshold
        percentage=74.0,
        degree="B.Tech Computer Science",
        year_of_study=3,
        certificate_issue_date="2023-01-15",  # Conflict: Issued before April 1, 2024
        available_documents=[
            "10th Marksheet",
            "12th Marksheet",
            "College ID Card",
            "OBC-NCL Certificate",
            "Income Certificate"
            # Conflict: Missing mandatory "Bonafide Student Certificate"
        ]
    )

    result = pipeline.run_pipeline(pdf_bytes, conflicting_student)
    calendar_cache[result.notice_id] = result.calendar_ics
    return result


@app.get("/api/calendar/ics/{notice_id}")
def download_calendar_ics(notice_id: str):
    """Download RFC-5545 .ics calendar file for import into Google Calendar / Apple Calendar / Outlook."""
    if notice_id not in calendar_cache:
        # Generate default or return error
        raise HTTPException(status_code=404, detail="Calendar file not found or expired.")
    
    ics_text = calendar_cache[notice_id]
    return Response(
        content=ics_text,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f"attachment; filename=Notice2Action_{notice_id}.ics"
        }
    )


@app.get("/api/sample/download-pdf")
def download_sample_pdf():
    """Download the realistic sample Indian circular PDF."""
    sample_path = os.path.join("samples", "sample_notice.pdf")
    if not os.path.exists(sample_path):
        raise HTTPException(status_code=404, detail="Sample PDF not found.")
    return FileResponse(
        sample_path,
        media_type="application/pdf",
        filename="AICTE_NMTS_2024_Notice.pdf"
    )
