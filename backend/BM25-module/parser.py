# parser.py  (v2 — robust multi-strategy PDF extraction)
"""
Text extraction utilities for resume files.

ROOT CAUSE FIX:
  The original parser used pdfplumber only. Many resume PDFs (including the
  DevOps resume template used in this project) store skill/body text in a
  Unicode/UTF-16 encoded font. pdfplumber silently skips these characters,
  returning only section headers like "TECHNICAL SKILLS" with no content.

  Result: extract_skills() received a skeleton text → found 0 matched skills.

SOLUTION:
  1. Try pdfplumber (good layout handling for most PDFs)
  2. ALWAYS also try pypdf (handles UTF-16 encoded fonts)
  3. Use whichever gives MORE text content
  4. Clean null bytes and split-word artifacts from pypdf output
"""

import os
import re
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Text cleaning
# ─────────────────────────────────────────────────────────────────────────────

def clean_pdf_text(raw: str) -> str:
    """
    Fix PDF extraction artifacts:
      1. Remove UTF-16 LE null bytes (\\x00) between every character
      2. Remove other control characters (keep newlines)
      3. Fix 'T erraform', 'P ython' — capital letter split from word
         caused by text-box boundaries in multi-column PDF layouts
      4. Normalize whitespace
    """
    if not raw:
        return ""

    # Remove UTF-16 LE null bytes
    cleaned = raw.replace('\x00', '')

    # Remove control characters (keep \n and \t)
    cleaned = re.sub(r'[\x01-\x08\x0b-\x1f\x7f-\x9f]', ' ', cleaned)

    # Fix "T erraform" → "Terraform", "P ython" → "Python"
    cleaned = re.sub(r'\b([A-Z])\s+([a-z]{3,})\b', r'\1\2', cleaned)

    # Normalize whitespace
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    return cleaned.strip()


# ─────────────────────────────────────────────────────────────────────────────
#  PDF extraction — multi-strategy, picks the best result
# ─────────────────────────────────────────────────────────────────────────────

def _try_pdfplumber(source) -> str:
    """Extract using pdfplumber. Returns empty string on failure."""
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(source) as pdf:
            for page in pdf.pages:
                # extract_words is more robust for multi-column layouts
                words = page.extract_words(keep_blank_chars=False)
                if words:
                    parts.append(' '.join(w['text'] for w in words))
                else:
                    text = page.extract_text()
                    if text:
                        parts.append(text)
        return clean_pdf_text('\n'.join(parts))
    except Exception as e:
        logger.debug(f"pdfplumber failed: {e}")
        return ""


def _try_pypdf(source) -> str:
    """
    Extract using pypdf. Handles UTF-16 encoded fonts that pdfplumber misses.
    Returns empty string on failure.
    """
    try:
        # Reset file pointer if this is a file-like object
        if hasattr(source, 'seek'):
            source.seek(0)
        from pypdf import PdfReader
        reader = PdfReader(source)
        parts = [page.extract_text() or '' for page in reader.pages]
        return clean_pdf_text('\n'.join(parts))
    except Exception as e:
        logger.debug(f"pypdf failed: {e}")
        return ""


def extract_text_from_pdf(source) -> str:
    """
    Extract all text from a PDF using multi-strategy approach.

    Tries both pdfplumber and pypdf, then uses whichever returns more content.
    This handles both standard PDFs (pdfplumber) and PDFs with Unicode-encoded
    fonts (pypdf) without needing to know which type you have upfront.

    `source` can be a file path (str) or a file-like object (BytesIO, tempfile).
    """
    text_pdfplumber = _try_pdfplumber(source)
    text_pypdf      = _try_pypdf(source)

    # Choose whichever gave more content
    if len(text_pypdf) > len(text_pdfplumber):
        logger.debug(f"Using pypdf ({len(text_pypdf)} chars > pdfplumber {len(text_pdfplumber)} chars)")
        return text_pypdf
    else:
        logger.debug(f"Using pdfplumber ({len(text_pdfplumber)} chars)")
        return text_pdfplumber


# ─────────────────────────────────────────────────────────────────────────────
#  DOCX extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_from_docx(source) -> str:
    """Extract all paragraph text from a DOCX file."""
    try:
        import docx
        doc = docx.Document(source)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return ' '.join(paragraphs)
    except Exception as e:
        logger.error(f"DOCX extraction failed: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
#  Auto-detect and extract
# ─────────────────────────────────────────────────────────────────────────────

def extract_resume_text(source) -> str:
    """Auto-detect format (PDF/DOCX) from file extension and extract text."""
    name = getattr(source, 'name', None) or (source if isinstance(source, str) else '')
    ext  = os.path.splitext(name)[-1].lower()
    if ext == '.docx':
        return extract_text_from_docx(source)
    return extract_text_from_pdf(source)