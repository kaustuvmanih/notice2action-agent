"""Security and Hardening Layer for Notice2Action.

Provides:
1. Magic-byte verification for uploaded PDFs.
2. File size and page cap enforcement.
3. String sanitization (stripping control chars, null bytes, bidirectional overrides).
4. Prompt-Injection Firewall detecting indirect injections & instruction hijacking.
5. XML-sandboxing for untrusted document contents.
"""

from __future__ import annotations
import re
import html
from typing import Tuple, List, Optional
from app.schemas import SecurityShieldReport, PageIndexedText

# Maximum constraints for enterprise security
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_ALLOWED_PAGES = 25
PDF_MAGIC_BYTES = b"%PDF-"

# Known indirect prompt injection heuristics & adversarial strings
PROMPT_INJECTION_PATTERNS = [
    (r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|prompts|rules)", "CRITICAL"),
    (r"(?i)disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|prompts|rules)", "CRITICAL"),
    (r"(?i)system\s+override|admin\s+override|jailbreak|developer\s+mode", "CRITICAL"),
    (r"(?i)you\s+are\s+now\s+(an?\s+)?(unrestricted|evil|dan|new\s+system)", "CRITICAL"),
    (r"(?i)reveal\s+(the\s+)?(system\s+prompt|initial\s+instructions|secret\s+key|api\s+key)", "HIGH"),
    (r"(?i)output\s+only\s+(the\s+following|this\s+phrase|'pwned'|\"pwned\")", "HIGH"),
    (r"(?i)bypass\s+(all\s+)?(safeguards|filters|security|rules)", "CRITICAL"),
    (r"(?i)<\/?(system|instruction|untrusted_document_content|prompt)>", "HIGH"),
    (r"(?i)repeat\s+(everything|the\s+prompt)\s+above", "MEDIUM"),
]

# Control characters to strip (excluding standard whitespace \t, \n, \r)
CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F\u202A-\u202E\u2066-\u2069]")


def validate_pdf_bytes(raw_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """Validate file length and %PDF- magic bytes."""
    if len(raw_bytes) == 0:
        return False, "File is empty (0 bytes)."
    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        return False, f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB."
    if not raw_bytes.startswith(PDF_MAGIC_BYTES):
        return False, "Invalid file signature: Missing %PDF- magic bytes header."
    return True, None


def sanitize_text(text: str) -> Tuple[str, int]:
    """Sanitize text by stripping malicious control characters, null bytes, and directional overrides."""
    sanitized, count = CONTROL_CHAR_REGEX.subn("", text)
    # Neutralize HTML/XML tags that might mimic sandbox tags
    sanitized = sanitized.replace("<untrusted_document_content>", "&lt;untrusted_document_content&gt;")
    sanitized = sanitized.replace("</untrusted_document_content>", "&lt;/untrusted_document_content&gt;")
    return sanitized, count


def scan_for_prompt_injection(text: str) -> Tuple[bool, str, List[str]]:
    """Scan extracted document text for prompt injection and role hijacking attempts.
    
    Returns:
        (detected, highest_threat_level, quarantined_snippets)
    """
    detected = False
    highest_threat = "NONE"
    threat_rank = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    snippets = []

    for pattern, threat in PROMPT_INJECTION_PATTERNS:
        matches = list(re.finditer(pattern, text))
        if matches:
            detected = True
            if threat_rank[threat] > threat_rank[highest_threat]:
                highest_threat = threat
            for m in matches:
                # Capture matched substring with surrounding context (up to 40 chars)
                start = max(0, m.start() - 20)
                end = min(len(text), m.end() + 20)
                snippets.append(text[start:end].strip())

    return detected, highest_threat, snippets[:5]  # limit to top 5 snippets


def build_xml_sandboxed_document(pages: List[PageIndexedText]) -> str:
    """Safely enclose document pages inside XML sandbox tags, escaping breakout sequences."""
    xml_parts = []
    for page in pages:
        clean_content, _ = sanitize_text(page.text_content)
        # Escape raw ampersands/angle brackets to ensure clean XML parsing
        escaped_content = html.escape(clean_content, quote=False)
        xml_parts.append(
            f'<page number="{page.page_number}">\n{escaped_content}\n</page>'
        )
    return "\n".join(xml_parts)
