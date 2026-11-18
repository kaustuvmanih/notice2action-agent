"""Generate realistic multi-page Indian academic circular PDF."""

import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def create_sample_pdf(output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0F172A'),
        alignment=1, # Center
        fontName='Helvetica-Bold'
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#334155'),
        alignment=1,
        fontName='Helvetica'
    )
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#1E293B'),
        fontName='Helvetica-Bold',
        spaceBefore=10,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#1E293B'),
        fontName='Helvetica'
    )
    bullet_style = ParagraphStyle(
        'DocBullet',
        parent=styles['Normal'],
        fontSize=9,
        leading=12.5,
        textColor=colors.HexColor('#0F172A'),
        leftIndent=15,
        fontName='Helvetica'
    )

    story = []

    # PAGE 1
    story.append(Paragraph("ALL INDIA COUNCIL FOR TECHNICAL EDUCATION (AICTE)", title_style))
    story.append(Paragraph("Ministry of Education, Government of India<br/>Nelson Mandela Marg, Vasant Kunj, New Delhi - 110070", subtitle_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284C7'), spaceBefore=2, spaceAfter=8))

    meta_table = [
        [
            Paragraph("<b>Notification No:</b> F.No. AICTE/SCH/2024/782", body_style),
            Paragraph("<b>Date of Issue:</b> 15 October 2024", body_style)
        ]
    ]
    t = Table(meta_table, colWidths=[300, 230])
    t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(t)
    story.append(Spacer(1, 8))

    story.append(Paragraph("PUBLIC NOTIFICATION: NATIONAL MERIT-CUM-MEANS TECHNICAL SCHOLARSHIP SCHEME (NMTS) 2024-25", h2_style))
    story.append(Paragraph(
        "AICTE announces the launch of the National Merit-cum-Means Technical Scholarship Scheme (NMTS) for the academic year 2024-25. "
        "The objective of this scheme is to provide financial assistance to meritorious technical students belonging to economically disadvantaged backgrounds to pursue higher technical education without encumbrance.",
        body_style
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("1. ELIGIBILITY CRITERIA", h2_style))
    story.append(Paragraph(
        "• <b>Academic Qualification:</b> Applicants must have secured a minimum CGPA of 7.5 or equivalent percentage in the qualifying examination.<br/>"
        "• <b>Income Ceiling:</b> Total annual family income from all sources must not exceed Rs. 6,00,000/- per annum.<br/>"
        "• <b>Course Enrolment:</b> The scheme is open to eligible full-time B.Tech/B.E. students enrolled in AICTE recognized technical institutions.<br/>"
        "• <b>Category Representation:</b> Applicable to all categories (General, OBC-NCL, SC, ST, and EWS) subject to valid government documentation.",
        bullet_style
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("2. REGISTRATION & APPLICATION FEE", h2_style))
    story.append(Paragraph(
        "No application fee is payable by applicants under this scholarship scheme. All eligible candidates can register and apply free of charge through the official National Scholarship Portal (NSP).",
        body_style
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("3. OFFICIAL APPLICATION PORTAL", h2_style))
    story.append(Paragraph(
        "Applications must be submitted exclusively through the National Scholarship Portal at <u>https://scholarships.gov.in</u>. Offline or physical submissions will not be entertained.",
        body_style
    ))

    from reportlab.platypus import PageBreak
    story.append(PageBreak())

    # PAGE 2
    story.append(Paragraph("ALL INDIA COUNCIL FOR TECHNICAL EDUCATION (AICTE) — Circular Continuation", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#94A3B8'), spaceBefore=2, spaceAfter=8))

    story.append(Paragraph("4. CRITICAL DEADLINES & IMPORTANT TIMELINES", h2_style))
    story.append(Paragraph(
        "• <b>Application Closing Date:</b> The last date for online application submission on the National Scholarship Portal is 30 November 2024.<br/>"
        "• <b>Institutional Verification:</b> Defective applications must be verified by the respective Institute Nodal Officer by 15 December 2024.<br/>"
        "• <b>Correction & Grievance Window:</b> The grievance and correction window will remain operational until 20 December 2024.",
        bullet_style
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("5. MANDATORY DOCUMENTS REQUIRED FOR UPLOAD", h2_style))
    story.append(Paragraph(
        "Candidates must upload clear, legible scanned color copies of the following authentic documents:<br/>"
        "1. <b>Income Certificate:</b> Income certificate issued by a competent authority on or after 01-04-2024 must be uploaded.<br/>"
        "2. <b>Bonafide Student Certificate:</b> Bonafide student certificate in the prescribed Annexure-A signed by the Head of Institution is mandatory.<br/>"
        "3. <b>Category / Caste Certificate:</b> Valid Central Government format certificate for OBC-NCL / SC / ST / EWS candidates issued by Tehsildar or SDM.<br/>"
        "4. <b>Academic Transcripts:</b> Self-attested marksheets of Class 10th, 12th, and all preceding semesters.<br/>"
        "5. <b>Bank Account Passbook:</b> Aadhaar-seeded bank account details with IFSC code.",
        bullet_style
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("6. HELPDESK & GRIEVANCE REDRESSAL", h2_style))
    story.append(Paragraph(
        "For any portal grievances, discrepancies, or technical clarifications, candidates may contact:<br/>"
        "Email: <b>support-scholarships@aicte-india.org</b> | Telephone: <b>011-29581000</b> (Mon-Fri, 09:30 AM to 05:30 PM).",
        body_style
    ))
    story.append(Spacer(1, 15))
    story.append(Paragraph("By Order of Member Secretary, AICTE", body_style))

    doc.build(story)
    print(f"Sample circular successfully created at: {output_path}")

if __name__ == '__main__':
    create_sample_pdf("samples/sample_notice.pdf")
