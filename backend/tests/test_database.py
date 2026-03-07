"""Unit tests for the SQLite warehouse layer"""
import pytest
import database as db

@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()

def test_init_db_creates_tables():
    with db.get_connection() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "dim_companies" in tables
    assert "dim_jobs"       in tables
    assert "dim_resumes"    in tables
    assert "fact_matches"   in tables

def test_upsert_company_creates_new():
    cid = db.upsert_company("TestCorp", industry="Tech")
    assert isinstance(cid, int)
    assert cid > 0

def test_upsert_company_idempotent():
    cid1 = db.upsert_company("IdempotentCorp")
    cid2 = db.upsert_company("IdempotentCorp")
    assert cid1 == cid2

def test_get_all_companies_includes_new():
    db.upsert_company("ListableCorp")
    companies = db.get_all_companies()
    names = [c["name"] for c in companies]
    assert "ListableCorp" in names

def test_upsert_job_creates_and_returns_id():
    cid = db.upsert_company("JobCorp")
    jid = db.upsert_job("TEST_001", "Test Job", "Looking for a tester", company_id=cid)
    assert isinstance(jid, int)

def test_upsert_job_idempotent():
    db.upsert_company("RepeatCorp")
    jid1 = db.upsert_job("REPEAT_001", "Job", "Description")
    jid2 = db.upsert_job("REPEAT_001", "Job", "Description")
    assert jid1 == jid2

def test_get_job_by_code():
    db.upsert_job("LOOKUP_001", "Lookup Job", "A job to look up")
    job = db.get_job_by_code("LOOKUP_001")
    assert job is not None
    assert job["job_code"] == "LOOKUP_001"
    assert job["title"] == "Lookup Job"

def test_get_job_by_code_not_found():
    job = db.get_job_by_code("NONEXISTENT_999")
    assert job is None

def test_get_all_jobs_returns_list():
    jobs = db.get_all_jobs()
    assert isinstance(jobs, list)

def test_store_resume_new():
    rid, is_new = db.store_resume("test_resume.pdf", "Python developer with 5 years experience in Flask")
    assert isinstance(rid, int)
    assert is_new is True

def test_store_resume_duplicate():
    text = "Unique resume text for duplicate test XYZ123"
    rid1, new1 = db.store_resume("dup1.pdf", text)
    rid2, new2 = db.store_resume("dup2.pdf", text)
    assert rid1 == rid2
    assert new1 is True
    assert new2 is False

def test_get_resume_by_hash():
    text = "Findable resume content ABCDEF"
    db.store_resume("findme.pdf", text)
    result = db.get_resume_by_hash(text)
    assert result is not None
    assert result["filename"] == "findme.pdf"

def test_get_all_resumes_returns_list():
    db.store_resume("listed.pdf", "Listed resume content unique 12345")
    resumes = db.get_all_resumes()
    assert isinstance(resumes, list)
    assert len(resumes) >= 1

def test_store_match_results():
    cid = db.upsert_company("MatchCorp")
    jid = db.upsert_job("MATCH_001", "Match Job", "Python Flask developer needed", company_id=cid)
    rid, _ = db.store_resume("matched.pdf", "Python Flask developer experienced")
    db.store_match_results(jid, [
        {"resume_db_id": rid, "score": 4.5, "matched_terms": ["python", "flask"], "match_count": 2}
    ])
    history = db.get_match_history(job_id=jid)
    assert len(history) >= 1
    assert history[0]["bm25_score"] == 4.5

def test_get_match_history_by_resume():
    cid = db.upsert_company("HistoryCorp")
    jid = db.upsert_job("HIST_001", "History Job", "Java Spring Boot developer")
    rid, _ = db.store_resume("history_resume.pdf", "Java Spring Boot microservices developer senior")
    db.store_match_results(jid, [
        {"resume_db_id": rid, "score": 3.2, "matched_terms": ["java"], "match_count": 1}
    ])
    history = db.get_match_history(resume_id=rid)
    assert any(h["job_code"] == "HIST_001" for h in history)

def test_seed_jobs_from_json(jobs_json_path):
    count = db.seed_jobs_from_json(jobs_json_path)
    assert count > 0
    jobs = db.get_all_jobs()
    assert len(jobs) >= count

def test_seed_jobs_missing_file():
    count = db.seed_jobs_from_json("/nonexistent/path/jobs.json")
    assert count == 0

def test_get_resume_tokens_null_when_missing():
    rid, _ = db.store_resume("no_tokens.pdf", "Resume without tokens stored 99887766")
    result = db.get_resume_tokens(rid)
    assert result is None
