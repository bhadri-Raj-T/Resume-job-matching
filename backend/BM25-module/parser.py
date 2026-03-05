# parser.py
"""
Text extraction utilities for resume files.
Supports PDF (via pdfplumber) and DOCX (via python-docx).
"""

import os
import pdfplumber
import docx


def extract_text_from_pdf(source) -> str:
    """
    Extract all text from a PDF.

    `source` can be:
      - A file path (str or os.PathLike)
      - A file-like object (e.g. tempfile, BytesIO)

    Returns a single cleaned string.
    """
    text_parts = []
    with pdfplumber.open(source) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return " ".join(text_parts).strip()


def extract_text_from_docx(source) -> str:
    """
    Extract all paragraph text from a DOCX file.

    `source` can be a file path or file-like object.
    """
    doc = docx.Document(source)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return " ".join(paragraphs)


def extract_resume_text(source) -> str:
    """
    Auto-detect format from file path extension and extract text.
    For file-like objects without a name, defaults to PDF.
    """
    name = getattr(source, "name", None) or (source if isinstance(source, str) else "")
    ext = os.path.splitext(name)[-1].lower()

    if ext == ".docx":
        return extract_text_from_docx(source)
    else:
        # Default to PDF for .pdf or unknown extensions
        return extract_text_from_pdf(source)