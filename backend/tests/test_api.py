"""Integration tests for the Flask API"""
import json
import pytest

def test_home_returns_200(flask_client):
    resp = flask_client.get("/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "status" in data
    assert "matcher_ready" in data

def test_list_companies(flask_client):
    resp = flask_client.get("/companies")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)

def test_add_company(flask_client):
    resp = flask_client.post("/companies", json={"name": "APITestCorp", "industry": "Tech"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "APITestCorp"

def test_add_company_missing_name(flask_client):
    resp = flask_client.post("/companies", json={"industry": "Tech"})
    assert resp.status_code == 400

def test_list_jobs(flask_client):
    resp = flask_client.get("/jobs")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)

def test_get_job_by_code_found(flask_client):
    resp = flask_client.get("/jobs/DEV_001")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["job_code"] == "DEV_001"

def test_get_job_by_code_not_found(flask_client):
    resp = flask_client.get("/jobs/NONEXISTENT_999")
    assert resp.status_code == 404

def test_add_job(flask_client):
    payload = {
        "job_code": "API_TEST_001",
        "title": "API Test Engineer",
        "description": "Looking for a test engineer with pytest experience and CI/CD knowledge",
        "company_name": "TestCompanyAPI"
    }
    resp = flask_client.post("/jobs", json=payload)
    assert resp.status_code == 201

def test_add_job_missing_field(flask_client):
    resp = flask_client.post("/jobs", json={"title": "No code job"})
    assert resp.status_code == 400

def test_list_resumes(flask_client):
    resp = flask_client.get("/resumes")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)

def test_match_without_resumes_returns_503(flask_client):
    # This test passes when no resumes are in warehouse (fresh test DB)
    resp = flask_client.post("/match", json={"job_text": "python developer"})
    # Could be 503 (no resumes) or 200 (if other tests already loaded resumes)
    assert resp.status_code in (200, 503)

def test_match_missing_job_text(flask_client):
    resp = flask_client.post("/match", json={"top_k": 3})
    assert resp.status_code == 400

def test_match_empty_job_text(flask_client):
    resp = flask_client.post("/match", json={"job_text": "   "})
    assert resp.status_code == 400

def test_history_endpoint(flask_client):
    resp = flask_client.get("/history")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)

def test_history_with_limit(flask_client):
    resp = flask_client.get("/history?limit=5")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) <= 5

def test_upload_resume_no_file(flask_client):
    resp = flask_client.post("/upload_resume")
    assert resp.status_code == 400

def test_upload_match_no_file(flask_client):
    resp = flask_client.post("/upload_match", data={"job_text": "python developer"})
    assert resp.status_code == 400

def test_upload_match_no_job_text(flask_client):
    import io
    fake_pdf = (io.BytesIO(b"fake"), "test.pdf")
    resp = flask_client.post("/upload_match", data={"resumes": fake_pdf})
    assert resp.status_code == 400
