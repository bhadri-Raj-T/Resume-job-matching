import os
import json
from difflib import SequenceMatcher
import fitz  # PyMuPDF


MIN_FONT_SIZE = 6
SIMILARITY_THRESHOLD = 0.90


def extract_text_and_metadata(pdf_path):
    """
    Extract text and detect:
    - Very small fonts
    - Hidden white text
    """
    doc = fitz.open(pdf_path)
    full_text = ""
    small_font_detected = False
    hidden_text_detected = False

    for page in doc:
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    font_size = span["size"]
                    color = span.get("color", 0)

                    if text:
                        full_text += text + " "

                    # Check small font
                    if font_size < MIN_FONT_SIZE:
                        small_font_detected = True

                    # Check white text (color == 16777215 means white)
                    if color == 16777215:
                        hidden_text_detected = True

    doc.close()

    return full_text.strip(), small_font_detected, hidden_text_detected


def load_jobs(jobs_path):
    with open(jobs_path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_similarity(resume_text, jobs):
    """
    Check if resume text is copied from job description
    """
    for job in jobs:
        job_text = job.get("text", "").strip()

        if not job_text:
            continue

        # Exact match
        if job_text in resume_text:
            return "Job description copied exactly"

        # Similarity match
        similarity = SequenceMatcher(None, job_text, resume_text).ratio()
        if similarity > SIMILARITY_THRESHOLD:
            return "High similarity with job description"

    return None


def check_blacklist(pdf_path, jobs_path):
    """
    Main function used in pytest
    Returns:
        {
            "status": "CLEAN" or "BLACKLISTED",
            "reasons": []
        }
    """

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"{pdf_path} not found")

    try:
        text, small_font, hidden_text = extract_text_and_metadata(pdf_path)
    except Exception as e:
        raise Exception("Corrupted or unreadable PDF") from e

    reasons = []

    # Empty resume
    if not text:
        return {
            "status": "BLACKLISTED",
            "reasons": ["Empty resume"]
        }

    # No extractable text (scanned image)
    if len(text.strip()) == 0:
        return {
            "status": "BLACKLISTED",
            "reasons": ["No extractable text (possible scanned image)"]
        }

    # Small font detection
    if small_font:
        reasons.append("Very small hidden text detected")

    # Hidden white text detection
    if hidden_text:
        reasons.append("Hidden text (same color as background)")

    # Load jobs
    jobs = load_jobs(jobs_path)

    similarity_issue = check_similarity(text, jobs)
    if similarity_issue:
        reasons.append(similarity_issue)

    if reasons:
        return {
            "status": "BLACKLISTED",
            "reasons": reasons
        }

    return {
        "status": "CLEAN",
        "reasons": []
    }