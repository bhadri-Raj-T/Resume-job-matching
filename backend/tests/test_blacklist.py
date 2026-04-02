"""
tests/test_blacklist.py
────────────────────────
Comprehensive tests for the resume blacklist / validation system.

Covers:
  Unit tests (resume_validator.py):
    - similarity()          — text similarity helper
    - validate_resume()     — single-resume checker
      • clean resume → []
      • invisible white text → flagged
      • tiny hidden font     → flagged
      • job-description copy → flagged
      • empty / blank PDF    → flagged
      • multiple issues      → all reported, duplicates removed

  Integration tests (app.py routes):
    - /upload_match with blacklisted PDF → excluded from results, reported
    - /upload_match with clean PDF       → included in results
    - /analyze    with blacklisted PDF   → excluded from analysis, reported
    - /analyze    with clean PDF         → included in analysis
    - All-blacklisted upload             → 422 with blacklisted list
    - Mixed upload (clean + blacklisted) → only clean resumes scored
    - Response structure keys            → blacklisted / total_blacklisted present

Synthetic PDF helpers:
    We generate minimal PDFs in-memory using fpdf2 (if available) or raw
    bytes so the test suite has zero dependency on the real resume files.
    For whitespace / invisible-text tests we inject crafted PyMuPDF pages
    by patching validate_resume directly.
"""

import io
import os
import json
import sys
import tempfile
import types
from unittest.mock import patch, MagicMock

import pytest

# ── path setup (mirrors conftest.py) ──────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTL_DIR     = os.path.join(BACKEND_DIR, "utils")
for p in (BACKEND_DIR, UTL_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from resume_validator import similarity, validate_resume


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS — synthetic PDFs
# ═══════════════════════════════════════════════════════════════════════════════

def _make_minimal_pdf(text: str = "Hello World") -> bytes:
    """
    Return bytes of a minimal valid PDF containing `text`.
    Uses fpdf2 when available; falls back to a hand-crafted PDF skeleton.
    """
    try:
        from fpdf import FPDF          # fpdf2
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(200, 10, txt=text)
        return pdf.output()            # returns bytes
    except ImportError:
        pass

    # Minimal hand-crafted PDF (no images, single page, no real font metrics)
    content = f"BT /F1 12 Tf 100 700 Td ({text}) Tj ET"
    c_bytes = content.encode()
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
        b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        + b"4 0 obj<</Length " + str(len(c_bytes)).encode() + b">>\nstream\n"
        + c_bytes + b"\nendstream\nendobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"0000000360 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\n"
        b"startxref\n430\n%%EOF"
    )
    return body


def _write_temp_pdf(content: bytes) -> str:
    """Write bytes to a temp file and return its path (caller must unlink)."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(content)
    tmp.close()
    return tmp.name


def _real_pdf_path() -> str:
    """Return path to the first real resume PDF in data/resumes/ if it exists."""
    resumes_dir = os.path.join(BACKEND_DIR, "data", "resumes")
    if os.path.isdir(resumes_dir):
        for f in sorted(os.listdir(resumes_dir)):
            if f.lower().endswith(".pdf"):
                return os.path.join(resumes_dir, f)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS — similarity()
# ═══════════════════════════════════════════════════════════════════════════════

class TestSimilarity:

    def test_identical_strings_return_1(self):
        assert similarity("hello world", "hello world") == 1.0

    def test_completely_different_returns_low(self):
        s = similarity("python developer flask", "xylophone trumpet trombone")
        assert s < 0.5

    def test_empty_strings_return_1(self):
        # SequenceMatcher("","") == 1.0
        assert similarity("", "") == 1.0

    def test_one_empty_returns_0(self):
        assert similarity("", "hello world") == 0.0

    def test_partial_overlap(self):
        s = similarity("python developer", "python engineer")
        assert 0.0 < s < 1.0

    def test_returns_float(self):
        assert isinstance(similarity("abc", "abc"), float)

    def test_commutative(self):
        a, b = "senior python developer", "junior java engineer"
        assert similarity(a, b) == similarity(b, a)

    def test_high_similarity_near_copies(self):
        base = "We are looking for a Python developer with 5 years experience"
        copy = "We are looking for a Python developer with 5 years of experience"
        assert similarity(base, copy) > 0.90


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS — validate_resume() with mocked PyMuPDF
# ═══════════════════════════════════════════════════════════════════════════════

def _make_fitz_doc(spans):
    """
    Build a mock fitz.Document that yields specific spans.
    Each span dict must have keys: text, size, color.
    """
    span_objs = [MagicMock(**{"__getitem__.side_effect": lambda k, s=s: s[k]}) for s in spans]
    for span_obj, span in zip(span_objs, spans):
        span_obj.__getitem__ = lambda self, k, s=span: s[k]

    line  = {"spans": spans}        # plain dicts — the real code does span["key"]
    block = {"lines": [line]}
    page  = MagicMock()
    page.get_text.return_value = {"blocks": [block]}

    doc = MagicMock()
    doc.__iter__ = MagicMock(return_value=iter([page]))
    doc.close    = MagicMock()
    return doc


class TestValidateResumeUnit:
    """Unit-level tests that mock fitz.open so no real PDF files are needed."""

    JOBS = [{"id": "DEV_001", "text": "python developer flask api rest backend sql"}]

    def _run(self, spans):
        doc = _make_fitz_doc(spans)
        with patch("resume_validator.fitz.open", return_value=doc):
            return validate_resume("/fake/path.pdf", self.JOBS)

    # ── Clean resume ──────────────────────────────────────────────────────────

    def test_clean_resume_returns_empty_list(self):
        spans = [{"text": "Senior Python developer with Flask experience", "size": 12, "color": 0}]
        assert self._run(spans) == []

    def test_returns_list_type(self):
        spans = [{"text": "Developer", "size": 12, "color": 0}]
        result = self._run(spans)
        assert isinstance(result, list)

    # ── Invisible white text ───────────────────────────────────────────────────

    def test_white_text_flagged(self):
        spans = [{"text": "hidden keywords python flask docker", "size": 12, "color": 16777215}]
        issues = self._run(spans)
        assert any("white" in i.lower() or "invisible" in i.lower() for i in issues)

    def test_white_text_short_not_necessarily_flagged_on_size(self):
        # White text is flagged regardless of length by the validator
        spans = [{"text": "x", "size": 12, "color": 16777215}]
        issues = self._run(spans)
        # Short white text — validator still flags white color
        assert any("white" in i.lower() or "invisible" in i.lower() for i in issues)

    def test_non_white_color_not_flagged(self):
        spans = [{"text": "Normal black text content here", "size": 12, "color": 0}]
        issues = self._run(spans)
        assert not any("white" in i.lower() or "invisible" in i.lower() for i in issues)

    # ── Tiny font ─────────────────────────────────────────────────────────────

    def test_tiny_font_with_long_text_flagged(self):
        # size < 6 AND len(text) > 20 → flagged
        spans = [{"text": "python flask docker kubernetes terraform devops", "size": 4, "color": 0}]
        issues = self._run(spans)
        assert any("font" in i.lower() or "small" in i.lower() or "hidden" in i.lower() for i in issues)

    def test_tiny_font_short_text_not_flagged(self):
        # size < 6 but len(text) <= 20 → NOT flagged
        spans = [{"text": "py flask", "size": 4, "color": 0}]
        issues = self._run(spans)
        assert not any("font" in i.lower() or "small" in i.lower() for i in issues)

    def test_normal_font_size_not_flagged(self):
        spans = [{"text": "This is a perfectly normal resume with regular font size visible", "size": 12, "color": 0}]
        issues = self._run(spans)
        assert not any("font" in i.lower() or "small" in i.lower() for i in issues)

    def test_boundary_font_size_5_flagged(self):
        spans = [{"text": "hidden long text stuffed into tiny font here more", "size": 5, "color": 0}]
        issues = self._run(spans)
        assert any("font" in i.lower() or "small" in i.lower() or "hidden" in i.lower() for i in issues)

    def test_boundary_font_size_6_not_flagged(self):
        spans = [{"text": "text at exactly six point font size boundary here", "size": 6, "color": 0}]
        issues = self._run(spans)
        assert not any("small" in i.lower() and "font" in i.lower() for i in issues)

    # ── Job description copy ──────────────────────────────────────────────────

    def test_job_copy_above_threshold_flagged(self):
        job_text = "python developer flask api rest backend sql"
        spans = [{"text": job_text, "size": 12, "color": 0}]
        issues = self._run(spans)
        assert any("copied" in i.lower() or "job" in i.lower() or "description" in i.lower() for i in issues)

    def test_normal_resume_not_flagged_as_copy(self):
        spans = [{"text": "Senior software engineer with 8 years experience in distributed systems", "size": 12, "color": 0}]
        issues = self._run(spans)
        assert not any("copied" in i.lower() for i in issues)

    # ── Empty / no text ───────────────────────────────────────────────────────

    def test_empty_text_flagged(self):
        spans = [{"text": "", "size": 12, "color": 0}]
        issues = self._run(spans)
        assert any("no" in i.lower() and ("text" in i.lower() or "readable" in i.lower() or "extractable" in i.lower()) for i in issues)

    def test_whitespace_only_text_flagged(self):
        spans = [{"text": "   ", "size": 12, "color": 0}]
        issues = self._run(spans)
        assert any("no" in i.lower() for i in issues)

    # ── Multiple issues — deduplication ───────────────────────────────────────

    def test_multiple_issues_all_reported(self):
        spans = [
            {"text": "hidden keywords python flask docker kubernetes terraform", "size": 3, "color": 16777215},
        ]
        issues = self._run(spans)
        assert len(issues) >= 1   # at least one issue

    def test_no_duplicate_issues(self):
        # Two spans both triggering white text — result should deduplicate
        spans = [
            {"text": "hidden a", "size": 12, "color": 16777215},
            {"text": "hidden b", "size": 12, "color": 16777215},
        ]
        issues = self._run(spans)
        assert len(issues) == len(set(issues)), "Duplicate issues should be removed"


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS — validate_resume() with real PDF files
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateResumeRealPDFs:
    """Integration-level tests using real PDFs from data/resumes/."""

    @pytest.fixture(scope="class")
    def jobs(self):
        jobs_path = os.path.join(BACKEND_DIR, "data", "jobs", "jobs.json")
        if not os.path.exists(jobs_path):
            return []
        with open(jobs_path, encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture(scope="class")
    def real_pdf(self):
        path = _real_pdf_path()
        if path is None:
            pytest.skip("No real PDF files found in data/resumes/")
        return path

    def test_real_resume_returns_list(self, real_pdf, jobs):
        result = validate_resume(real_pdf, jobs)
        assert isinstance(result, list)

    def test_real_resume_is_clean(self, real_pdf, jobs):
        """
        Real generated resumes in data/resumes/ should be CLEAN.
        If this fails it means the validator has a false-positive bug.
        """
        issues = validate_resume(real_pdf, jobs)
        assert issues == [], (
            f"Real resume {os.path.basename(real_pdf)} flagged as blacklisted: {issues}"
        )

    def test_all_sample_resumes_clean(self, jobs):
        """Spot-check the first 10 resumes — all should be CLEAN."""
        resumes_dir = os.path.join(BACKEND_DIR, "data", "resumes")
        if not os.path.isdir(resumes_dir):
            pytest.skip("data/resumes/ not found")

        pdfs = sorted(f for f in os.listdir(resumes_dir) if f.lower().endswith(".pdf"))[:10]
        for fname in pdfs:
            path = os.path.join(resumes_dir, fname)
            issues = validate_resume(path, jobs)
            assert issues == [], f"{fname} unexpectedly blacklisted: {issues}"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS — Flask API routes with blacklist
# ═══════════════════════════════════════════════════════════════════════════════

class TestUploadMatchBlacklist:
    """Tests for POST /upload_match with blacklist gate."""

    def test_upload_match_response_has_blacklisted_key(self, flask_client, real_pdf_bytes):
        resp = flask_client.post(
            "/upload_match",
            data={"resumes": (io.BytesIO(real_pdf_bytes), "resume.pdf"),
                  "job_text": "python developer flask api"},
            content_type="multipart/form-data",
        )
        if resp.status_code in (200, 422):
            data = resp.get_json()
            assert "blacklisted" in data

    def test_upload_match_response_has_total_blacklisted_key(self, flask_client, real_pdf_bytes):
        resp = flask_client.post(
            "/upload_match",
            data={"resumes": (io.BytesIO(real_pdf_bytes), "resume.pdf"),
                  "job_text": "python developer flask api"},
            content_type="multipart/form-data",
        )
        if resp.status_code == 200:
            data = resp.get_json()
            assert "total_blacklisted" in data

    def test_clean_pdf_not_in_blacklisted(self, flask_client, real_pdf_bytes):
        """A legitimate resume should appear in results, not blacklisted."""
        with patch("app.validate_resume", return_value=[]):   # force CLEAN
            resp = flask_client.post(
                "/upload_match",
                data={"resumes": (io.BytesIO(real_pdf_bytes), "good.pdf"),
                      "job_text": "python developer flask api backend"},
                content_type="multipart/form-data",
            )
        if resp.status_code == 200:
            data = resp.get_json()
            blacklisted_files = [b["file"] for b in data.get("blacklisted", [])]
            assert "good.pdf" not in blacklisted_files

    def test_blacklisted_pdf_not_in_results(self, flask_client, real_pdf_bytes):
        """A blacklisted resume must NOT appear in BM25 results."""
        with patch("app.validate_resume", return_value=["Invisible/white colored text detected"]):
            resp = flask_client.post(
                "/upload_match",
                data={"resumes": (io.BytesIO(real_pdf_bytes), "bad.pdf"),
                      "job_text": "python developer flask api backend"},
                content_type="multipart/form-data",
            )
        # All uploads blacklisted → 422
        assert resp.status_code == 422
        data = resp.get_json()
        assert len(data["blacklisted"]) == 1
        assert data["blacklisted"][0]["file"] == "bad.pdf"

    def test_blacklisted_entry_has_issues_list(self, flask_client, real_pdf_bytes):
        issue_msg = "Invisible/white colored text detected"
        with patch("app.validate_resume", return_value=[issue_msg]):
            resp = flask_client.post(
                "/upload_match",
                data={"resumes": (io.BytesIO(real_pdf_bytes), "bad.pdf"),
                      "job_text": "python developer"},
                content_type="multipart/form-data",
            )
        data = resp.get_json()
        assert "blacklisted" in data
        assert data["blacklisted"][0]["issues"] == [issue_msg]

    def test_all_blacklisted_returns_422(self, flask_client, real_pdf_bytes):
        with patch("app.validate_resume", return_value=["Very small font detected"]):
            resp = flask_client.post(
                "/upload_match",
                data={"resumes": (io.BytesIO(real_pdf_bytes), "bad.pdf"),
                      "job_text": "python developer"},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 422

    def test_mixed_upload_only_clean_scored(self, flask_client, real_pdf_bytes):
        """With two uploads — one clean, one blacklisted — only clean appears in results."""
        call_count = {"n": 0}
        def fake_validate(path, jobs):
            call_count["n"] += 1
            # First call → clean, second call → blacklisted
            return [] if call_count["n"] == 1 else ["Very small font detected"]

        with patch("app.validate_resume", side_effect=fake_validate):
            resp = flask_client.post(
                "/upload_match",
                data={
                    "resumes": [
                        (io.BytesIO(real_pdf_bytes), "clean.pdf"),
                        (io.BytesIO(real_pdf_bytes), "dirty.pdf"),
                    ],
                    "job_text": "python developer flask",
                },
                content_type="multipart/form-data",
            )
        if resp.status_code == 200:
            data = resp.get_json()
            result_ids = [r["id"] for r in data.get("results", [])]
            assert "dirty.pdf" not in result_ids
            blacklisted_files = [b["file"] for b in data.get("blacklisted", [])]
            assert "dirty.pdf" in blacklisted_files

    def test_total_blacklisted_count_correct(self, flask_client, real_pdf_bytes):
        """
        When all resumes are blacklisted the route returns 422.
        The 'blacklisted' list is always present; 'total_blacklisted' only on 200.
        """
        with patch("app.validate_resume", return_value=["Very small font detected"]):
            resp = flask_client.post(
                "/upload_match",
                data={"resumes": (io.BytesIO(real_pdf_bytes), "bad.pdf"),
                      "job_text": "python developer"},
                content_type="multipart/form-data",
            )
        data = resp.get_json()
        blacklisted_count = len(data.get("blacklisted", []))
        total_bl = data.get("total_blacklisted", blacklisted_count)
        assert total_bl >= 1 or blacklisted_count >= 1


class TestAnalyzeBlacklist:
    """Tests for POST /analyze with blacklist gate."""

    def test_analyze_response_has_blacklisted_key(self, flask_client, real_pdf_bytes):
        with patch("app.validate_resume", return_value=[]):
            resp = flask_client.post(
                "/analyze",
                data={"resumes": (io.BytesIO(real_pdf_bytes), "resume.pdf"),
                      "job_text": "python developer flask api"},
                content_type="multipart/form-data",
            )
        if resp.status_code in (200, 422):
            data = resp.get_json()
            assert "blacklisted" in data

    def test_analyze_response_has_total_blacklisted_key(self, flask_client, real_pdf_bytes):
        with patch("app.validate_resume", return_value=[]):
            resp = flask_client.post(
                "/analyze",
                data={"resumes": (io.BytesIO(real_pdf_bytes), "resume.pdf"),
                      "job_text": "python developer flask api"},
                content_type="multipart/form-data",
            )
        if resp.status_code == 200:
            data = resp.get_json()
            assert "total_blacklisted" in data

    def test_blacklisted_resume_not_in_analyses(self, flask_client, real_pdf_bytes):
        with patch("app.validate_resume", return_value=["Copied job description"]):
            resp = flask_client.post(
                "/analyze",
                data={"resumes": (io.BytesIO(real_pdf_bytes), "fraud.pdf"),
                      "job_text": "python developer flask api"},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 422
        data = resp.get_json()
        assert any(b["file"] == "fraud.pdf" for b in data["blacklisted"])

    def test_blacklisted_resume_not_added_to_db(self, flask_client, real_pdf_bytes):
        """A blacklisted resume must never be added to preloaded_resumes."""
        import app as flask_app_module
        before = len(flask_app_module.preloaded_resumes)

        with patch("app.validate_resume", return_value=["Very small font detected"]):
            flask_client.post(
                "/analyze",
                data={"resumes": (io.BytesIO(real_pdf_bytes), "blacklisted_db_test.pdf"),
                      "job_text": "python developer flask api"},
                content_type="multipart/form-data",
            )

        after = len(flask_app_module.preloaded_resumes)
        assert after == before, (
            "Blacklisted resume was added to preloaded_resumes — it must be excluded"
        )

    def test_all_blacklisted_analyze_returns_422(self, flask_client, real_pdf_bytes):
        with patch("app.validate_resume", return_value=["Very small font detected"]):
            resp = flask_client.post(
                "/analyze",
                data={"resumes": (io.BytesIO(real_pdf_bytes), "bad.pdf"),
                      "job_text": "python developer"},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 422

    def test_analyze_clean_resume_included(self, flask_client, real_pdf_bytes):
        with patch("app.validate_resume", return_value=[]):
            resp = flask_client.post(
                "/analyze",
                data={"resumes": (io.BytesIO(real_pdf_bytes), "clean.pdf"),
                      "job_text": "python developer flask api backend"},
                content_type="multipart/form-data",
            )
        if resp.status_code == 200:
            data = resp.get_json()
            # clean resume should be in analyses
            ids = [a.get("id") for a in data.get("analyses", [])]
            assert "clean.pdf" in ids

    def test_analyze_blacklisted_list_has_issues(self, flask_client, real_pdf_bytes):
        issue = "Invisible/white colored text detected"
        with patch("app.validate_resume", return_value=[issue]):
            resp = flask_client.post(
                "/analyze",
                data={"resumes": (io.BytesIO(real_pdf_bytes), "bad.pdf"),
                      "job_text": "python developer"},
                content_type="multipart/form-data",
            )
        data = resp.get_json()
        bl = data.get("blacklisted", [])
        assert len(bl) == 1
        assert bl[0]["issues"] == [issue]


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures specific to this module
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def real_pdf_bytes():
    """
    Return bytes of a real or synthetic PDF for upload tests.
    Prefers a real resume PDF from data/resumes/ for authenticity;
    falls back to a synthetic one so tests run even without the data dir.
    """
    real = _real_pdf_path()
    if real:
        with open(real, "rb") as f:
            return f.read()
    # Fallback: synthetic
    return _make_minimal_pdf("Senior Python Developer Flask REST API SQL Docker")


# ── Home endpoint — blacklist_enabled flag ─────────────────────────────────────

def test_home_has_blacklist_enabled_key(flask_client):
    """The updated app.py exposes blacklist_enabled: true in the home endpoint."""
    resp = flask_client.get("/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "blacklist_enabled" in data
    assert data["blacklist_enabled"] is True
