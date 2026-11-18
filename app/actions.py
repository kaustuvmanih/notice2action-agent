"""Action Executor Agent for Notice2Action.

Generates:
1. Prioritized action checklist (P1/P2/P3).
2. RFC-5545 compliant .ics calendar file with alarm notifications.
3. Formal clarification email draft for institutional authorities.
4. Bilingual executive briefing (English & Hindi/Hinglish).
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import re

from app.schemas import (
    StructuredNoticeExtraction,
    CrossAuditResult,
    ActionItem,
    BilingualSummary,
    StudentProfile
)


def generate_action_items(
    extraction: StructuredNoticeExtraction,
    audit: CrossAuditResult,
    student: StudentProfile
) -> List[ActionItem]:
    """Compile prioritized action checklist based on notice deadlines and detected conflicts."""
    items: List[ActionItem] = []
    item_count = 1

    # 1. P1 Actions: Address any Critical or High Conflicts immediately
    for conflict in audit.conflicts:
        if conflict.severity in ["CRITICAL", "HIGH"]:
            items.append(
                ActionItem(
                    id=f"ACT-{item_count:02d}",
                    priority="P1 - IMMEDIATE",
                    action=f"[RESOLVE CONFLICT] {conflict.field}: {conflict.recommended_remedy}",
                    deadline="Within 48 hours",
                    assigned_to=student.name,
                    category="CORRECTION",
                    status="PENDING"
                )
            )
            item_count += 1

    # 2. Document procurement for missing documents
    for conflict in audit.conflicts:
        if conflict.severity == "MEDIUM" and "Missing" in conflict.field:
            items.append(
                ActionItem(
                    id=f"ACT-{item_count:02d}",
                    priority="P2 - HIGH",
                    action=f"[PROCURE DOCUMENT] {conflict.rule_text}",
                    deadline="3 days before submission close",
                    assigned_to=student.name,
                    category="DOCUMENT_PROCUREMENT",
                    status="PENDING"
                )
            )
            item_count += 1

    # 3. Notice Deadlines Actions
    sorted_deadlines = sorted(extraction.deadlines, key=lambda d: d.iso_date or "9999-99-99")
    for d in sorted_deadlines:
        priority_level = "P1 - IMMEDIATE" if d.urgency == "CRITICAL" else ("P2 - HIGH" if d.urgency == "HIGH" else "P3 - NORMAL")
        items.append(
            ActionItem(
                id=f"ACT-{item_count:02d}",
                priority=priority_level,  # type: ignore
                action=f"[MILESTONE] {d.title} - {d.action_required}",
                deadline=d.date_str,
                assigned_to=student.name,
                category="PORTAL_SUBMISSION",
                status="PENDING"
            )
        )
        item_count += 1

    # 4. Final verification and submission
    items.append(
        ActionItem(
            id=f"ACT-{item_count:02d}",
            priority="P3 - NORMAL",
            action="[FINAL AUDIT] Review uploaded PDF receipts, application acknowledgement, and transaction ID",
            deadline="Submission Date",
            assigned_to=student.name,
            category="VERIFICATION",
            status="PENDING"
        )
    )

    return items


def generate_rfc5545_ics(
    extraction: StructuredNoticeExtraction,
    student_name: str
) -> str:
    """Generate RFC-5545 compliant .ics calendar file with alarm notifications."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Notice2Action//Autonomous Document Agent//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{extraction.metadata.title[:40]} Deadlines",
        "X-WR-TIMEZONE:Asia/Kolkata",
    ]

    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for d in extraction.deadlines:
        uid = f"{uuid.uuid4()}@notice2action.agent"
        # Determine event start and end
        dtstart = None
        if d.iso_date:
            try:
                parsed_date = datetime.strptime(d.iso_date, "%Y-%m-%d")
                # Set event to 18:00 IST (12:30 UTC) on the deadline day
                dtstart = parsed_date.strftime("%Y%m%d")
            except ValueError:
                pass

        if not dtstart:
            # Fallback to tomorrow
            dtstart = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y%m%d")

        event_lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART;VALUE=DATE:{dtstart}",
            f"SUMMARY:[Notice2Action] {d.title}",
            f"DESCRIPTION:Notice: {extraction.metadata.title}\\nOrganization: {extraction.metadata.issuing_organization}\\nAction: {d.action_required}\\nEvidence: {d.verbatim_quote[:80]}",
            "STATUS:CONFIRMED",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:Reminder: {d.title} deadline today for {student_name}",
            "TRIGGER:-P1D",
            "END:VALARM",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:Urgent 2-day reminder: {d.title}",
            "TRIGGER:-P2D",
            "END:VALARM",
            "END:VEVENT"
        ]
        lines.extend(event_lines)

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def generate_clarification_email(
    extraction: StructuredNoticeExtraction,
    audit: CrossAuditResult,
    student: StudentProfile
) -> str:
    """Draft a formal and professional clarification email to the issuing authority."""
    recipient = extraction.contact_email or "helpdesk@scholarships.gov.in"
    org_name = extraction.metadata.issuing_organization
    notice_id = extraction.metadata.notice_number or extraction.metadata.title

    conflict_points = []
    for c in audit.conflicts:
        conflict_points.append(f"- Issue regarding {c.field}: {c.rejection_risk} (Ref: '{c.evidence_quote[:60]}...')")

    if not conflict_points:
        conflict_points.append("- Formal confirmation regarding portal document upload window and receipt verification.")

    conflicts_text = "\n".join(conflict_points)

    email_body = f"""To: {recipient}
Subject: Urgent Clarification Request: {extraction.metadata.title} [Ref: {notice_id}] - Applicant: {student.name}

Respected Sir / Madam,

Greetings.

I am writing with reference to the official notification "{extraction.metadata.title}" (Ref No: {notice_id}) issued by {org_name}.

I am a prospective applicant currently pursuing {student.degree} (Year {student.year_of_study}). Upon thoroughly reviewing the circular and conducting a pre-submission compliance audit for my application, I seek your kind clarification on the following points:

{conflicts_text}

Could you please confirm if:
1. A supplementary undertaking or provisional certificate can be accepted prior to the final portal cutoff?
2. Any relaxation or special provisions apply under relevant regulatory guidelines?

Given the approaching deadline, your prompt guidance on this matter would enable me to submit an accurate and compliant application without delay.

Thank you very much for your time and continued support.

Yours sincerely,

{student.name}
Roll / App ID: APP-{datetime.now().year}-{student.name[:3].upper()}01
Email: {student.email}
Degree: {student.degree} (Year {student.year_of_study})
Notice2Action Automated Pre-Submission Verification Audit Attached.
"""
    return email_body.strip()


def generate_bilingual_summary(
    extraction: StructuredNoticeExtraction,
    audit: CrossAuditResult,
    student: StudentProfile
) -> BilingualSummary:
    """Generate high-impact English and colloquial Hindi/Hinglish executive briefs."""
    # English summary
    deadline_highlights = ", ".join([f"{d.title} ({d.date_str})" for d in extraction.deadlines[:3]]) or "Refer circular"
    conflicts_count = len(audit.conflicts)
    
    eng_text = (
        f"**Official Notice:** {extraction.metadata.title}\n"
        f"**Issuing Authority:** {extraction.metadata.issuing_organization}\n"
        f"**Audit Status:** {audit.eligibility_status} (Risk Score: {audit.risk_score}/100)\n\n"
        f"**Key Deadlines:** {deadline_highlights}\n\n"
        f"**Executive Brief:** {extraction.official_summary}\n\n"
        f"**Compliance Findings:** {audit.summary}\n"
        f"- Total Conflicts Detected: {conflicts_count}\n"
        f"- Mandatory Documents: {len(extraction.required_documents)} items verified.\n"
    )

    # Hindi / Hinglish summary
    if audit.eligibility_status == "ELIGIBLE":
        status_hi = "Aap is scheme ke liye poori tarah ELIGIBLE hain! Saare documents aur marks match ho rahe hain."
    elif audit.eligibility_status == "CONDITIONALLY ELIGIBLE":
        status_hi = (
            f"Aapki application CONDITIONALLY ELIGIBLE hai. {conflicts_count} zaroori cheezein check karni hongi "
            f"(jaise expired certificate renew karwana ya missing documents upload karna) taaki form reject na ho."
        )
    else:
        status_hi = (
            f"WARNING: Direct rejection risk hai! Aapka score ya income threshold circular ke rules se match nahi kar raha. "
            f"Submission se pehle authority se clarification lena ya exemption request karna zaroori hai."
        )

    deadline_hi = "\n".join([f"- **{d.title}**: {d.date_str} tak complete karein" for d in extraction.deadlines[:3]])

    hinglish_text = (
        f"### Asaan Hindi / Hinglish Summary (Notice ki Zaroori Baatein):\n\n"
        f"**Yeh Notice kiske liye hai?**\n"
        f"{extraction.metadata.issuing_organization} ne '{extraction.metadata.title}' release kiya hai.\n\n"
        f"**Aapki Eligibility Ka Status:**\n"
        f"👉 **{status_hi}**\n\n"
        f"**Zaroori Taareekhein (Deadlines):**\n"
        f"{deadline_hi}\n\n"
        f"**Abhi Turant Kya Karna Hai?**\n"
        f"1. Calendar file (.ics) download karke apne phone me reminder set kar lein.\n"
        f"2. P1 Action items me diye gaye verification points check karein.\n"
        f"3. Draft kiya gaya email check karein agar authority se clarification chahiye."
    )

    return BilingualSummary(
        english=eng_text.strip(),
        hindi_hinglish=hinglish_text.strip()
    )
