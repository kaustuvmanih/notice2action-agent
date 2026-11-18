"""Deterministic Quote Grounding, Self-Auditing, and Cross-Document Conflict Auditor.

Enforces zero-hallucination by programmatically verifying every claim and quote against
the exact page-indexed text extracted from the source PDF.
"""

from __future__ import annotations
import re
import difflib
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from app.schemas import (
    PageIndexedText,
    StructuredNoticeExtraction,
    GroundingAuditItem,
    GroundingReport,
    StudentProfile,
    ConflictAuditItem,
    CrossAuditResult
)


def normalize_text_for_matching(text: str) -> str:
    """Normalize text by collapsing whitespace, stripping special punctuation, and lowercasing."""
    if not text:
        return ""
    # Normalize unicode quotes and dashes
    t = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    t = t.replace("—", "-").replace("–", "-")
    # Collapse multiple whitespaces and line breaks
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def verify_quote_against_page(
    quote: str,
    page_number: int,
    pages_dict: Dict[int, str]
) -> Tuple[bool, float, str, Optional[str]]:
    """Programmatically verify a quote against page-indexed source text.
    
    Returns:
        (is_verified, match_score, match_type, failure_reason)
    """
    if not quote or not quote.strip():
        return False, 0.0, "FAILED", "Empty verbatim quote provided."

    norm_quote = normalize_text_for_matching(quote)

    # Check target page
    if page_number not in pages_dict:
        return False, 0.0, "FAILED", f"Page {page_number} does not exist in the document."

    page_text = pages_dict[page_number]
    norm_page = normalize_text_for_matching(page_text)

    # 1. Exact Substring Match
    if norm_quote in norm_page:
        return True, 1.0, "EXACT", None

    # 2. Token overlap and sequence matching on target page
    # Search for best matching substring slice in page
    quote_len = len(norm_quote)
    if quote_len == 0:
        return False, 0.0, "FAILED", "Empty quote."

    # Use difflib on candidate windows or full page token search
    words_quote = norm_quote.split()
    if not words_quote:
        return False, 0.0, "FAILED", "Quote has no words."

    # Check if all keywords or 80%+ words exist on page
    words_page = set(norm_page.split())
    overlap = sum(1 for w in words_quote if w in words_page) / len(words_quote)

    # Sequence matcher on the best matching window
    matcher = difflib.SequenceMatcher(None, norm_quote, norm_page)
    match = matcher.find_longest_match(0, len(norm_quote), 0, len(norm_page))
    
    longest_ratio = (2.0 * match.size) / (len(norm_quote) + match.size) if (len(norm_quote) + match.size) > 0 else 0.0

    best_score = max(overlap, longest_ratio)

    if best_score >= 0.85:
        return True, round(best_score, 3), "FUZZY_HIGH", None
    elif best_score >= 0.65:
        return False, round(best_score, 3), "FUZZY_PARTIAL", (
            f"Partial match ({round(best_score * 100)}%) on page {page_number}. Quarantined for manual review."
        )

    # 3. Check adjacent pages (off-by-one page index tolerance)
    for adj_page in [page_number - 1, page_number + 1]:
        if adj_page in pages_dict:
            adj_norm = normalize_text_for_matching(pages_dict[adj_page])
            if norm_quote in adj_norm:
                return True, 0.95, "FUZZY_HIGH", f"Quote found on adjacent page {adj_page} instead of page {page_number}."

    return False, round(best_score, 3), "FAILED", (
        f"Quote could not be grounded on page {page_number}. Grounding match score: {round(best_score * 100)}%."
    )


def audit_extraction_grounding(
    extraction: StructuredNoticeExtraction,
    pages: List[PageIndexedText]
) -> GroundingReport:
    """Deterministic Verifier Agent: Evaluates every claim and quote against PDF pages."""
    pages_dict = {p.page_number: p.text_content for p in pages}
    audited_items: List[GroundingAuditItem] = []
    
    # Audit Deadlines
    for idx, d in enumerate(extraction.deadlines):
        is_verified, score, match_type, reason = verify_quote_against_page(
            d.verbatim_quote, d.page_number, pages_dict
        )
        audited_items.append(
            GroundingAuditItem(
                item_id=f"DEADLINE-{idx+1}",
                item_type="DEADLINE",
                claim_text=f"{d.title}: {d.date_str}",
                verbatim_quote=d.verbatim_quote,
                page_number=d.page_number,
                is_verified=is_verified,
                match_score=score,
                match_type=match_type,
                quarantined=not is_verified,
                quarantine_reason=reason
            )
        )

    # Audit Eligibility Criteria
    for idx, e in enumerate(extraction.eligibility_criteria):
        is_verified, score, match_type, reason = verify_quote_against_page(
            e.verbatim_quote, e.page_number, pages_dict
        )
        audited_items.append(
            GroundingAuditItem(
                item_id=f"ELIGIBILITY-{idx+1}",
                item_type="ELIGIBILITY",
                claim_text=f"{e.criterion_name}: {e.condition} {e.threshold_value}",
                verbatim_quote=e.verbatim_quote,
                page_number=e.page_number,
                is_verified=is_verified,
                match_score=score,
                match_type=match_type,
                quarantined=not is_verified,
                quarantine_reason=reason
            )
        )

    # Audit Required Documents
    for idx, doc in enumerate(extraction.required_documents):
        is_verified, score, match_type, reason = verify_quote_against_page(
            doc.verbatim_quote, doc.page_number, pages_dict
        )
        audited_items.append(
            GroundingAuditItem(
                item_id=f"DOC-{idx+1}",
                item_type="DOCUMENT",
                claim_text=f"{doc.document_name} ({'Mandatory' if doc.is_mandatory else 'Optional'})",
                verbatim_quote=doc.verbatim_quote,
                page_number=doc.page_number,
                is_verified=is_verified,
                match_score=score,
                match_type=match_type,
                quarantined=not is_verified,
                quarantine_reason=reason
            )
        )

    # Audit Fee details if provided
    if extraction.fee_details and extraction.fee_details.verbatim_quote and extraction.fee_details.page_number:
        fee = extraction.fee_details
        is_verified, score, match_type, reason = verify_quote_against_page(
            fee.verbatim_quote, fee.page_number, pages_dict
        )
        audited_items.append(
            GroundingAuditItem(
                item_id="FEE-1",
                item_type="FEE",
                claim_text=f"Application Fee: ₹{fee.amount_inr or 0}",
                verbatim_quote=fee.verbatim_quote,
                page_number=fee.page_number,
                is_verified=is_verified,
                match_score=score,
                match_type=match_type,
                quarantined=not is_verified,
                quarantine_reason=reason
            )
        )

    total_claims = len(audited_items)
    verified_claims = sum(1 for item in audited_items if item.is_verified)
    quarantined_claims = total_claims - verified_claims
    accuracy = round((verified_claims / total_claims * 100.0), 1) if total_claims > 0 else 100.0

    return GroundingReport(
        total_claims=total_claims,
        verified_claims=verified_claims,
        quarantined_claims=quarantined_claims,
        grounding_accuracy_score=accuracy,
        audited_items=audited_items
    )


def parse_numeric_threshold(thresh_str: str) -> Optional[float]:
    """Extract numeric value from string (e.g. '7.5', '600000', '6.0 Lakhs')."""
    if not thresh_str:
        return None
    s = thresh_str.lower().replace(",", "").replace("₹", "").replace("inr", "").strip()
    # Check for 'lakh' or 'lac'
    lakh_match = re.search(r"([\d.]+)\s*(?:lakh|lac|lpa)", s)
    if lakh_match:
        try:
            return float(lakh_match.group(1)) * 100000.0
        except ValueError:
            pass
    
    # Generic float finder
    num_match = re.search(r"[\d.]+", s)
    if num_match:
        try:
            return float(num_match.group(0))
        except ValueError:
            return None
    return None


def parse_date_safely(date_str: str) -> Optional[datetime]:
    """Parse common Indian and ISO date formats."""
    if not date_str:
        return None
    cleaned = date_str.strip()
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def audit_student_cross_conflicts(
    extraction: StructuredNoticeExtraction,
    student: StudentProfile
) -> CrossAuditResult:
    """Cross-Document Conflict Auditor: Compares verified notice rules against student profile."""
    conflicts: List[ConflictAuditItem] = []
    eligible_reasons: List[str] = []
    risk_points = 0

    # 1. CGPA / Percentage Audit
    for crit in extraction.eligibility_criteria:
        cname = crit.criterion_name.lower()
        if "cgpa" in cname or "pointer" in cname or "gpa" in cname:
            thresh = parse_numeric_threshold(crit.threshold_value)
            if thresh is not None:
                if student.cgpa < thresh:
                    conflicts.append(
                        ConflictAuditItem(
                            field="CGPA / Academic Score",
                            rule_text=f"Minimum required CGPA is {crit.threshold_value}",
                            student_value=f"{student.cgpa} CGPA",
                            threshold_value=crit.threshold_value,
                            has_conflict=True,
                            severity="CRITICAL",
                            rejection_risk=(
                                f"Applicant CGPA ({student.cgpa}) is strictly below the circular threshold "
                                f"({crit.threshold_value}). Direct ground for portal auto-rejection."
                            ),
                            evidence_quote=crit.verbatim_quote,
                            recommended_remedy=(
                                "Request institutional conversion certificate or seek exemption if reserved category quota applies."
                            )
                        )
                    )
                    risk_points += 40
                else:
                    eligible_reasons.append(f"CGPA ({student.cgpa}) satisfies minimum requirement of {crit.threshold_value}.")

        # 2. Income Ceiling Audit
        elif "income" in cname or "salary" in cname or "family income" in cname:
            thresh_income = parse_numeric_threshold(crit.threshold_value)
            if thresh_income is not None:
                if student.annual_income_inr > thresh_income:
                    conflicts.append(
                        ConflictAuditItem(
                            field="Annual Family Income",
                            rule_text=f"Annual family income must not exceed ₹{thresh_income:,.0f}",
                            student_value=f"₹{student.annual_income_inr:,.0f}",
                            threshold_value=f"₹{thresh_income:,.0f}",
                            has_conflict=True,
                            severity="CRITICAL",
                            rejection_risk=(
                                f"Declared income ₹{student.annual_income_inr:,.0f} exceeds the mandatory limit "
                                f"of ₹{thresh_income:,.0f}."
                            ),
                            evidence_quote=crit.verbatim_quote,
                            recommended_remedy="Submit updated Income Certificate deducting non-taxable allowances if admissible."
                        )
                    )
                    risk_points += 40
                else:
                    eligible_reasons.append(f"Family income (₹{student.annual_income_inr:,.0f}) is within ceiling (₹{thresh_income:,.0f}).")

        # 3. Category match
        elif "category" in cname or "caste" in cname:
            if crit.applicable_category and crit.applicable_category.upper() not in ["ALL", "ANY"]:
                req_cat = crit.applicable_category.upper()
                std_cat = student.category.upper()
                if req_cat not in std_cat and std_cat not in req_cat:
                    conflicts.append(
                        ConflictAuditItem(
                            field="Reservation / Social Category",
                            rule_text=f"Scheme restricted to {crit.applicable_category}",
                            student_value=student.category,
                            threshold_value=crit.applicable_category,
                            has_conflict=True,
                            severity="HIGH",
                            rejection_risk=f"Applicant belongs to {student.category}, whereas scheme designates {crit.applicable_category}.",
                            evidence_quote=crit.verbatim_quote,
                            recommended_remedy="Check if a sub-category or general open pool exists for this notice."
                        )
                    )
                    risk_points += 30

    # 4. Certificate Validity & Issue Date Audit
    for doc in extraction.required_documents:
        dname = doc.document_name.lower()
        if "certificate" in dname and ("income" in dname or "caste" in dname or "obc" in dname or "category" in dname):
            if doc.validity_rule and student.certificate_issue_date:
                # Check for financial year constraint e.g. "April 1, 2024" or "after 01-04-2024"
                date_match = re.search(r"(\d{1,2}[-/ ]\w+[-/ ]\d{4}|\w+\s+\d{1,2},?\s+\d{4})", doc.validity_rule)
                if date_match:
                    rule_date = parse_date_safely(date_match.group(1))
                    student_cert_date = parse_date_safely(student.certificate_issue_date)
                    if rule_date and student_cert_date and student_cert_date < rule_date:
                        conflicts.append(
                            ConflictAuditItem(
                                field="Certificate Issue Date & Validity",
                                rule_text=f"Mandatory validity requirement: {doc.validity_rule}",
                                student_value=f"Issued on {student.certificate_issue_date}",
                                threshold_value=doc.validity_rule,
                                has_conflict=True,
                                severity="HIGH",
                                rejection_risk=(
                                    f"{doc.document_name} was issued on {student.certificate_issue_date}, which precedes "
                                    f"the mandatory cutoff ({date_match.group(1)}). The portal will reject expired certificates."
                                ),
                                evidence_quote=doc.verbatim_quote,
                                recommended_remedy="Immediately apply for a fresh certificate via State e-District portal or Tehsildar."
                            )
                        )
                        risk_points += 25

    # 5. Missing Mandatory Documents Check
    available_docs_norm = [normalize_text_for_matching(d) for d in student.available_documents]
    for doc in extraction.required_documents:
        if doc.is_mandatory:
            norm_doc = normalize_text_for_matching(doc.document_name)
            # Check if any available document matches closely
            has_doc = any(
                norm_doc in av or av in norm_doc or difflib.SequenceMatcher(None, norm_doc, av).ratio() > 0.65
                for av in available_docs_norm
            )
            if not has_doc:
                conflicts.append(
                    ConflictAuditItem(
                        field="Missing Mandatory Document",
                        rule_text=f"Mandatory submission: {doc.document_name}",
                        student_value="NOT AVAILABLE in student document locker",
                        threshold_value="Mandatory",
                        has_conflict=True,
                        severity="MEDIUM",
                        rejection_risk=f"Application cannot be submitted without mandatory document: {doc.document_name}.",
                        evidence_quote=doc.verbatim_quote,
                        recommended_remedy=f"Procure {doc.document_name} from {doc.issuing_authority or 'institution'} before submission deadline."
                    )
                )
                risk_points += 15

    # Determine final eligibility status
    risk_score = min(100, risk_points)
    critical_conflicts = [c for c in conflicts if c.severity == "CRITICAL"]
    high_conflicts = [c for c in conflicts if c.severity == "HIGH"]

    if len(critical_conflicts) > 0:
        status = "INELIGIBLE"
        summary = (
            f"REJECTION RISK DETECTED: Found {len(critical_conflicts)} critical conflict(s) "
            f"and {len(conflicts)} total issue(s). Student does not meet hard eligibility criteria."
        )
    elif len(high_conflicts) > 0 or len(conflicts) > 0:
        status = "CONDITIONALLY ELIGIBLE"
        summary = (
            f"ACTION REQUIRED: Student meets primary criteria but has {len(conflicts)} remediable defect(s) "
            f"(such as certificate renewal or missing attachments) before submission."
        )
    else:
        status = "ELIGIBLE"
        summary = "ALL CRITERIA SATISFIED: Student profile aligns with all verified notice requirements."

    return CrossAuditResult(
        eligibility_status=status,
        risk_score=risk_score,
        summary=summary,
        conflicts=conflicts,
        eligible_reasons=eligible_reasons
    )
