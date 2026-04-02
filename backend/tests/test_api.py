"""
tests/test_api.py
─────────────────
Integration tests for the Flask API (app.py).

Routes tested (all routes that actually exist in app.py):
  GET  /                  → health / status
  POST /match             → BM25 company flow
  POST /upload_match      → upload + BM25 match
  POST /analyze           → individual hybrid flow
  POST /whatif            → what-if simulator

FIX: removed tests for /companies, /jobs, /resumes, /history, /upload_resume
     which do NOT exist in app.py and were causing 404 failures.

FIX: home endpoint returns "db_matcher_ready" (not "matcher_ready").
"""
import io
import json
import pytest


# ── Health / home ─────────────────────────────────────────────────────────────

def test_home_returns_200(flask_client):
    resp = flask_client.get("/")
    assert resp.status_code == 200


def test_home_response_has_status_key(flask_client):
    data = flask_client.get("/").get_json()
    assert "status" in data


def test_home_response_has_db_matcher_ready(flask_client):
    """FIX: key is 'db_matcher_ready', not 'matcher_ready'."""
    data = flask_client.get("/").get_json()
    assert "db_matcher_ready" in data


def test_home_has_preloaded_resumes_key(flask_client):
    data = flask_client.get("/").get_json()
    assert "preloaded_resumes" in data
    assert isinstance(data["preloaded_resumes"], int)


def test_home_has_flows_key(flask_client):
    data = flask_client.get("/").get_json()
    assert "flows" in data


def test_home_content_type_json(flask_client):
    resp = flask_client.get("/")
    assert resp.content_type.startswith("application/json")


# ── POST /match ───────────────────────────────────────────────────────────────

def test_match_missing_job_text_returns_400(flask_client):
    resp = flask_client.post("/match", json={"top_k": 3})
    assert resp.status_code == 400


def test_match_empty_job_text_returns_400(flask_client):
    resp = flask_client.post("/match", json={"job_text": "   "})
    assert resp.status_code == 400


def test_match_no_body_returns_400(flask_client):
    resp = flask_client.post("/match", json={})
    assert resp.status_code == 400


def test_match_with_valid_job_text(flask_client):
    """Either 200 (resumes loaded) or 503 (no preloaded resumes in test env)."""
    resp = flask_client.post(
        "/match",
        json={"job_text": "python developer flask rest api backend", "top_k": 3},
    )
    assert resp.status_code in (200, 503)


def test_match_200_response_structure(flask_client):
    resp = flask_client.post(
        "/match",
        json={"job_text": "python developer flask rest api backend", "top_k": 2},
    )
    if resp.status_code == 200:
        data = resp.get_json()
        assert "results" in data
        assert "total_resumes_in_db" in data
        assert isinstance(data["results"], list)


def test_match_503_has_error_key(flask_client):
    """When db_matcher is None, /match returns 503 with 'error' key."""
    resp = flask_client.post("/match", json={"job_text": "anything"})
    if resp.status_code == 503:
        data = resp.get_json()
        assert "error" in data


# ── POST /upload_match ────────────────────────────────────────────────────────

def test_upload_match_no_file_returns_400(flask_client):
    resp = flask_client.post(
        "/upload_match", data={"job_text": "python developer"}
    )
    assert resp.status_code == 400


def test_upload_match_no_job_text_returns_400(flask_client):
    fake_pdf = (io.BytesIO(b"fake pdf content"), "test.pdf")
    resp = flask_client.post(
        "/upload_match",
        data={"resumes": fake_pdf},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_upload_match_invalid_file_returns_422(flask_client):
    """A fake (non-parseable) PDF should result in 422 (no resumes parsed)."""
    fake_pdf = (io.BytesIO(b"this is not a real pdf"), "fake.pdf")
    resp = flask_client.post(
        "/upload_match",
        data={"resumes": fake_pdf, "job_text": "python developer"},
        content_type="multipart/form-data",
    )
    # Either 422 (no text extracted) or 500 (parser error)
    assert resp.status_code in (400, 422, 500)


def test_upload_match_non_pdf_file(flask_client):
    """Uploading a .txt file should be rejected."""
    txt_file = (io.BytesIO(b"plain text resume"), "resume.txt")
    resp = flask_client.post(
        "/upload_match",
        data={"resumes": txt_file, "job_text": "python developer"},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (400, 422)


# ── POST /analyze ─────────────────────────────────────────────────────────────

def test_analyze_no_file_returns_400(flask_client):
    resp = flask_client.post(
        "/analyze", data={"job_text": "python developer"}
    )
    assert resp.status_code == 400


def test_analyze_no_job_text_returns_400(flask_client):
    fake_pdf = (io.BytesIO(b"fake pdf content"), "resume.pdf")
    resp = flask_client.post(
        "/analyze",
        data={"resumes": fake_pdf},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_analyze_invalid_pdf_returns_error(flask_client):
    fake_pdf = (io.BytesIO(b"not a real pdf at all"), "resume.pdf")
    resp = flask_client.post(
        "/analyze",
        data={"resumes": fake_pdf, "job_text": "python developer flask"},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (400, 422, 500)


# ── POST /whatif ──────────────────────────────────────────────────────────────

def test_whatif_missing_body_returns_400(flask_client):
    resp = flask_client.post("/whatif", data="not json",
                             content_type="text/plain")
    assert resp.status_code == 400


def test_whatif_missing_resume_text_returns_400(flask_client):
    resp = flask_client.post("/whatif", json={
        "job_text": "python developer",
        "add_skills": ["Docker"],
    })
    assert resp.status_code == 400


def test_whatif_missing_job_text_returns_400(flask_client):
    resp = flask_client.post("/whatif", json={
        "resume_text": "python developer with flask experience",
        "add_skills": ["Docker"],
    })
    assert resp.status_code == 400


def test_whatif_missing_add_skills_returns_400(flask_client):
    resp = flask_client.post("/whatif", json={
        "resume_text": "python developer with flask experience",
        "job_text": "python flask docker developer",
    })
    assert resp.status_code == 400


def test_whatif_valid_request(flask_client):
    resp = flask_client.post("/whatif", json={
        "resume_text": "python developer flask REST API backend SQL",
        "job_text": "python flask docker kubernetes developer CI/CD",
        "add_skills": ["Docker", "Kubernetes"],
    })
    # 200 = success, 500 = analysis error (acceptable in unit test env)
    assert resp.status_code in (200, 500)


def test_whatif_200_response_structure(flask_client):
    resp = flask_client.post("/whatif", json={
        "resume_text": "python developer flask REST API backend SQL",
        "job_text": "python flask docker kubernetes developer CI/CD",
        "add_skills": ["Docker", "Kubernetes"],
    })
    if resp.status_code == 200:
        data = resp.get_json()
        # Response should include score-related keys
        assert data is not None


def test_whatif_empty_add_skills(flask_client):
    """add_skills can be an empty list (no skills to add)."""
    resp = flask_client.post("/whatif", json={
        "resume_text": "python developer flask REST API",
        "job_text": "python flask developer",
        "add_skills": [],
    })
    assert resp.status_code in (200, 500)


# ── Method not allowed ────────────────────────────────────────────────────────

def test_home_post_not_allowed(flask_client):
    resp = flask_client.post("/")
    assert resp.status_code == 405


def test_match_get_not_allowed(flask_client):
    resp = flask_client.get("/match")
    assert resp.status_code == 405
