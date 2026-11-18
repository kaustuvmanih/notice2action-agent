"""Data contracts and Pydantic schemas for the Notice2Action agentic pipeline."""

from __future__ import annotations
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# --- Security & Ingestion Schemas ---

class SecurityShieldReport(BaseModel):
    magic_bytes_valid: bool = Field(..., description="True if valid %PDF- magic bytes detected")
    detected_mime_type: str = Field(default="application/pdf")
    file_size_bytes: int = Field(..., description="Size of file in bytes")
    total_pages: int = Field(..., description="Total pages in the PDF document")
    sanitization_applied: bool = Field(default=False)
    sanitized_chars_count: int = Field(default=0)
    prompt_injection_detected: bool = Field(default=False)
    injection_threat_level: Literal["NONE", "LOW", "MEDIUM", "CRITICAL"] = Field(default="NONE")
    quarantined_snippets: List[str] = Field(default_factory=list)
    security_verdict: Literal["CLEAN", "SUSPICIOUS", "BLOCKED"] = Field(default="CLEAN")


class PageIndexedText(BaseModel):
    page_number: int
    text_content: str
    char_count: int


# --- Step 2: Extraction Schemas ---

class DeadlineItem(BaseModel):
    title: str = Field(..., description="Name/purpose of deadline (e.g. Application Close)")
    date_str: str = Field(..., description="Date text as presented in notice")
    iso_date: Optional[str] = Field(None, description="Normalized ISO 8601 date (YYYY-MM-DD) if parseable")
    verbatim_quote: str = Field(..., description="Exact textual excerpt from document supporting this deadline")
    page_number: int = Field(..., description="1-indexed page number where quote resides")
    urgency: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(default="HIGH")
    action_required: str = Field(..., description="Action to complete before this deadline")


class EligibilityCriteriaItem(BaseModel):
    criterion_name: str = Field(..., description="Criterion name, e.g. CGPA, Income, Category")
    condition: str = Field(..., description="Comparison operator or rule e.g. '>= 8.0', '<= 600000'")
    threshold_value: str = Field(..., description="Raw threshold stated in circular")
    applicable_category: Optional[str] = Field("ALL", description="Target category e.g. GENERAL, OBC, SC, ST, EWS")
    verbatim_quote: str = Field(..., description="Exact textual excerpt from document supporting this rule")
    page_number: int = Field(..., description="1-indexed page number")


class RequiredDocumentItem(BaseModel):
    document_name: str = Field(..., description="Document title e.g. Income Certificate, Marksheet")
    issuing_authority: Optional[str] = Field(None, description="Required issuing body e.g. Tehsildar, Sub-Divisional Magistrate")
    validity_rule: Optional[str] = Field(None, description="Validity constraint e.g. Issued on or after April 1, 2024")
    is_mandatory: bool = Field(default=True)
    verbatim_quote: str = Field(..., description="Exact textual excerpt from document")
    page_number: int = Field(..., description="1-indexed page number")


class FeeDetails(BaseModel):
    amount_inr: Optional[float] = Field(None, description="Application or registration fee")
    payment_mode: Optional[str] = Field(None, description="Online portal, Demand Draft, NEFT")
    exemption_categories: List[str] = Field(default_factory=list)
    verbatim_quote: Optional[str] = Field(None)
    page_number: Optional[int] = Field(None)


class NoticeMetadata(BaseModel):
    title: str = Field(..., description="Title of the notice or circular")
    issuing_organization: str = Field(..., description="Issuing University/Ministry/Authority")
    notice_number: Optional[str] = Field(None, description="Official reference number/memo ID")
    issue_date: Optional[str] = Field(None, description="Notice issue date")
    scheme_category: str = Field(default="Scholarship / Academic Grant")


class StructuredNoticeExtraction(BaseModel):
    metadata: NoticeMetadata
    deadlines: List[DeadlineItem] = Field(default_factory=list)
    eligibility_criteria: List[EligibilityCriteriaItem] = Field(default_factory=list)
    required_documents: List[RequiredDocumentItem] = Field(default_factory=list)
    fee_details: Optional[FeeDetails] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    portal_url: Optional[str] = None
    official_summary: str = Field(..., description="Executive summary of the circular")


# --- Step 3: Grounding & Verification Schemas ---

class GroundingAuditItem(BaseModel):
    item_id: str
    item_type: Literal["DEADLINE", "ELIGIBILITY", "DOCUMENT", "FEE"]
    claim_text: str
    verbatim_quote: str
    page_number: int
    is_verified: bool
    match_score: float = Field(..., description="Match confidence score between 0.0 and 1.0")
    match_type: Literal["EXACT", "FUZZY_HIGH", "FUZZY_PARTIAL", "FAILED"]
    quarantined: bool
    quarantine_reason: Optional[str] = None


class GroundingReport(BaseModel):
    total_claims: int
    verified_claims: int
    quarantined_claims: int
    grounding_accuracy_score: float = Field(..., description="Percentage of verified quotes (0 - 100%)")
    audited_items: List[GroundingAuditItem] = Field(default_factory=list)


# --- Step 4: Student Profile & Cross-Document Audit Schemas ---

class StudentProfile(BaseModel):
    name: str = Field(default="Aarav Sharma")
    email: str = Field(default="aarav.sharma@example.edu")
    category: str = Field(default="OBC-NCL")
    annual_income_inr: float = Field(default=650000.0, description="Annual household income in INR")
    cgpa: float = Field(default=7.4, description="Student's current CGPA (out of 10.0)")
    percentage: Optional[float] = Field(default=74.0, description="Equivalent percentage")
    degree: str = Field(default="B.Tech Computer Science")
    year_of_study: int = Field(default=3)
    certificate_issue_date: Optional[str] = Field(default="2023-01-15", description="Income/Caste Certificate date (YYYY-MM-DD)")
    available_documents: List[str] = Field(
        default_factory=lambda: [
            "10th Marksheet",
            "12th Marksheet",
            "College ID Card",
            "OBC-NCL Certificate",
            "Income Certificate"
        ]
    )


class ConflictAuditItem(BaseModel):
    field: str = Field(..., description="Field inspected e.g. CGPA, Annual Income, Certificate Date")
    rule_text: str = Field(..., description="Verified rule from notice")
    student_value: str = Field(..., description="Student's actual data")
    threshold_value: str = Field(..., description="Threshold requirement")
    has_conflict: bool = Field(..., description="True if requirement is violated")
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "INFO"] = Field(...)
    rejection_risk: str = Field(..., description="Explanation of why application risks rejection")
    evidence_quote: str = Field(..., description="Document quote establishing the rule")
    recommended_remedy: str = Field(..., description="Actionable step to resolve or bypass")


class CrossAuditResult(BaseModel):
    eligibility_status: Literal["ELIGIBLE", "CONDITIONALLY ELIGIBLE", "INELIGIBLE"]
    risk_score: int = Field(..., description="Risk score from 0 (lowest) to 100 (highest risk)")
    summary: str
    conflicts: List[ConflictAuditItem] = Field(default_factory=list)
    eligible_reasons: List[str] = Field(default_factory=list)


# --- Step 5: Action Executor Schemas ---

class ActionItem(BaseModel):
    id: str
    priority: Literal["P1 - IMMEDIATE", "P2 - HIGH", "P3 - NORMAL"]
    action: str
    deadline: str
    assigned_to: str
    category: Literal["DOCUMENT_PROCUREMENT", "CORRECTION", "PORTAL_SUBMISSION", "VERIFICATION"]
    status: Literal["PENDING", "IN_PROGRESS", "READY"] = "PENDING"


class BilingualSummary(BaseModel):
    english: str
    hindi_hinglish: str


class PipelineTelemetry(BaseModel):
    step_latencies_ms: Dict[str, float] = Field(default_factory=dict)
    total_latency_ms: float = 0.0
    llm_source: str = "gemini-2.5-flash"
    timestamp: str = ""


class Notice2ActionResponse(BaseModel):
    success: bool = True
    notice_id: str
    telemetry: PipelineTelemetry
    security_shield: SecurityShieldReport
    extraction: StructuredNoticeExtraction
    grounding_report: GroundingReport
    cross_audit: CrossAuditResult
    action_items: List[ActionItem]
    bilingual_summary: BilingualSummary
    calendar_ics: str
    clarification_email_draft: str
    raw_document_pages: int
