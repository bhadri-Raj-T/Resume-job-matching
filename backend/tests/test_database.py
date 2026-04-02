"""
tests/test_database.py
───────────────────────
Unit tests for the SQLite data-warehouse layer (database.py).

Covers:
  - init_db: table and index creation
  - Companies: upsert, idempotency, list
  - Jobs: upsert, idempotency, lookup by code, list, missing
  - Resumes: store (new & duplicate), hash-based lookup, list, tokens
  - Matches: store results, query by job, query by resume
  - History: limit parameter
  - Seeding: seed_jobs_from_json, missing file
"""
import pytest
import database as db


@pytest.fixture(autouse=True)
def fresh_db():
    """Re-initialise the DB before every test (uses temp path from conftest)."""
    db.init_db()


# ── init_db ───────────────────────────────────────────────────────────────────

def test_init_db_creates_all_tables():
    with db.get_connection() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "dim_companies" in tables
    assert "dim_jobs" in tables
    assert "dim_resumes" in tables
    assert "fact_matches" in tables


def test_init_db_idempotent():
    """Calling init_db twice must not raise (CREATE TABLE IF NOT EXISTS)."""
    db.init_db()
    db.init_db()


def test_init_db_creates_indexes():
    with db.get_connection() as conn:
        indexes = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
    assert "idx_jobs_code" in indexes
    assert "idx_resumes_hash" in indexes
    assert "idx_matches_job" in indexes
    assert "idx_matches_resume" in indexes


# ── Companies ─────────────────────────────────────────────────────────────────

def test_upsert_company_returns_int():
    cid = db.upsert_company("TestCorp", industry="Tech")
    assert isinstance(cid, int)
    assert cid > 0


def test_upsert_company_idempotent():
    cid1 = db.upsert_company("IdempotentCorp")
    cid2 = db.upsert_company("IdempotentCorp")
    assert cid1 == cid2


def test_upsert_company_with_industry():
    cid = db.upsert_company("FinTech Inc", industry="Finance")
    assert cid > 0


def test_upsert_company_with_website():
    cid = db.upsert_company("WebCorp", website="https://webcorp.example.com")
    assert cid > 0


def test_get_all_companies_returns_list():
    companies = db.get_all_companies()
    assert isinstance(companies, list)


def test_get_all_companies_includes_inserted():
    db.upsert_company("ListableCorp")
    companies = db.get_all_companies()
    names = [c["name"] for c in companies]
    assert "ListableCorp" in names


def test_get_all_companies_sorted_by_name():
    db.upsert_company("ZetaCorp")
    db.upsert_company("AlphaCorp")
    companies = db.get_all_companies()
    names = [c["name"] for c in companies]
    assert names == sorted(names)


def test_upsert_company_different_names_different_ids():
    cid1 = db.upsert_company("Corp_Alpha_Unique_1")
    cid2 = db.upsert_company("Corp_Beta_Unique_2")
    assert cid1 != cid2


# ── Jobs ──────────────────────────────────────────────────────────────────────

def test_upsert_job_returns_int():
    jid = db.upsert_job("JOB_001", "Software Engineer", "Python developer needed")
    assert isinstance(jid, int)
    assert jid > 0


def test_upsert_job_with_company():
    cid = db.upsert_company("JobCorp")
    jid = db.upsert_job("JOB_CORP_001", "Test Job", "Looking for a tester", company_id=cid)
    assert isinstance(jid, int)


def test_upsert_job_idempotent():
    jid1 = db.upsert_job("REPEAT_001", "Job Title", "Description")
    jid2 = db.upsert_job("REPEAT_001", "Job Title", "Description")
    assert jid1 == jid2


def test_get_job_by_code_found():
    db.upsert_job("LOOKUP_001", "Lookup Job", "A job to look up by code")
    job = db.get_job_by_code("LOOKUP_001")
    assert job is not None
    assert job["job_code"] == "LOOKUP_001"
    assert job["title"] == "Lookup Job"


def test_get_job_by_code_not_found():
    assert db.get_job_by_code("NONEXISTENT_999") is None


def test_get_job_by_code_includes_description():
    db.upsert_job("DESC_001", "Desc Job", "Detailed description here")
    job = db.get_job_by_code("DESC_001")
    assert job["description"] == "Detailed description here"


def test_get_all_jobs_returns_list():
    assert isinstance(db.get_all_jobs(), list)


def test_get_all_jobs_includes_inserted():
    db.upsert_job("LIST_JOB_001", "Listed Job", "A job in the list")
    jobs = db.get_all_jobs()
    codes = [j["job_code"] for j in jobs]
    assert "LIST_JOB_001" in codes


def test_get_all_jobs_filter_by_company():
    cid = db.upsert_company("FilterCorp")
    db.upsert_job("FILTER_001", "Filtered Job", "Filter company job", company_id=cid)
    jobs = db.get_all_jobs(company_id=cid)
    assert all(j["company_name"] == "FilterCorp" for j in jobs)


def test_upsert_job_with_processed_tokens():
    tokens = ["python", "flask", "developer"]
    jid = db.upsert_job("TOKEN_JOB_001", "Token Job", "Python Flask developer", processed_tokens=tokens)
    assert jid > 0


# ── Resumes ───────────────────────────────────────────────────────────────────

def test_store_resume_returns_id_and_bool():
    rid, is_new = db.store_resume("resume.pdf", "Python developer with Flask experience")
    assert isinstance(rid, int)
    assert isinstance(is_new, bool)


def test_store_resume_new_is_true():
    _, is_new = db.store_resume("new_resume.pdf", "Unique resume content XYZ_NEW_UNIQUE_123")
    assert is_new is True


def test_store_resume_duplicate_is_false():
    text = "Duplicate resume text content ABCDE_DUPLICATE"
    _, new1 = db.store_resume("dup1.pdf", text)
    _, new2 = db.store_resume("dup2.pdf", text)
    assert new1 is True
    assert new2 is False


def test_store_resume_duplicate_same_id():
    text = "Same hash same ID content XYZABC_SAME"
    rid1, _ = db.store_resume("file1.pdf", text)
    rid2, _ = db.store_resume("file2.pdf", text)
    assert rid1 == rid2


def test_get_resume_by_hash_found():
    text = "Findable resume content unique ABCDEF_FIND"
    db.store_resume("findme.pdf", text)
    result = db.get_resume_by_hash(text)
    assert result is not None
    assert result["filename"] == "findme.pdf"


def test_get_resume_by_hash_not_found():
    result = db.get_resume_by_hash("text that was never stored XYZ999")
    assert result is None


def test_get_all_resumes_returns_list():
    assert isinstance(db.get_all_resumes(), list)


def test_get_all_resumes_includes_stored():
    db.store_resume("listed.pdf", "Listed resume content unique 12345_LISTED")
    resumes = db.get_all_resumes()
    filenames = [r["filename"] for r in resumes]
    assert "listed.pdf" in filenames


def test_get_resume_tokens_null_when_not_stored():
    rid, _ = db.store_resume("no_tokens.pdf", "Resume without tokens unique 99887766")
    assert db.get_resume_tokens(rid) is None


def test_store_resume_with_tokens():
    tokens = ["python", "flask", "backend"]
    rid, _ = db.store_resume(
        "tokenised.pdf",
        "Tokenised resume unique AAABBB_TOKEN",
        processed_tokens=tokens,
    )
    retrieved = db.get_resume_tokens(rid)
    assert retrieved == tokens


# ── Matches ───────────────────────────────────────────────────────────────────

def test_store_match_results_no_error():
    jid = db.upsert_job("MATCH_JOB_001", "Match Job", "Python Flask developer needed")
    rid, _ = db.store_resume("matched.pdf", "Python Flask developer experienced MATCH_UNIQUE")
    db.store_match_results(jid, [
        {"resume_db_id": rid, "score": 4.5, "matched_terms": ["python", "flask"], "match_count": 2}
    ])


def test_get_match_history_by_job_id():
    jid = db.upsert_job("HIST_JOB_001", "History Job", "Java Spring Boot microservices")
    rid, _ = db.store_resume("history_r.pdf", "Java Spring Boot microservices senior HIST_UNIQUE")
    db.store_match_results(jid, [
        {"resume_db_id": rid, "score": 3.2, "matched_terms": ["java"], "match_count": 1}
    ])
    history = db.get_match_history(job_id=jid)
    assert len(history) >= 1
    assert history[0]["bm25_score"] == 3.2


def test_get_match_history_by_resume_id():
    jid = db.upsert_job("HIST_JOB_002", "History Job 2", "Data Scientist Python SQL pandas")
    rid, _ = db.store_resume("hist_r2.pdf", "Data Scientist Python SQL pandas HIST_R2_UNIQUE")
    db.store_match_results(jid, [
        {"resume_db_id": rid, "score": 5.0, "matched_terms": ["python", "sql"], "match_count": 2}
    ])
    history = db.get_match_history(resume_id=rid)
    assert any(h["job_code"] == "HIST_JOB_002" for h in history)


def test_get_match_history_by_both():
    jid = db.upsert_job("HIST_BOTH_001", "Both Filter Job", "DevOps Docker Kubernetes")
    rid, _ = db.store_resume("both.pdf", "DevOps Docker Kubernetes BOTH_UNIQUE")
    db.store_match_results(jid, [
        {"resume_db_id": rid, "score": 2.8, "matched_terms": ["docker"], "match_count": 1}
    ])
    history = db.get_match_history(job_id=jid, resume_id=rid)
    assert len(history) >= 1


def test_get_match_history_global_returns_list():
    history = db.get_match_history()
    assert isinstance(history, list)


def test_get_match_history_limit():
    jid = db.upsert_job("LIMIT_JOB_001", "Limit Job", "Cloud Architect AWS GCP Terraform")
    for i in range(10):
        rid, _ = db.store_resume(f"limit_{i}.pdf", f"Cloud Architect resume number {i} LIMIT_UNIQUE_{i}")
        db.store_match_results(jid, [
            {"resume_db_id": rid, "score": float(i), "matched_terms": ["cloud"], "match_count": 1}
        ])
    history = db.get_match_history(limit=5)
    assert len(history) <= 5


def test_match_history_has_expected_keys():
    jid = db.upsert_job("KEY_JOB_001", "Key Check Job", "Python backend developer Flask")
    rid, _ = db.store_resume("key_check.pdf", "Python backend developer Flask KEY_UNIQUE")
    db.store_match_results(jid, [
        {"resume_db_id": rid, "score": 1.5, "matched_terms": ["python"], "match_count": 1}
    ])
    history = db.get_match_history(job_id=jid)
    assert len(history) >= 1
    row = history[0]
    for key in ("bm25_score", "match_count", "matched_at", "resume_filename", "job_code", "job_title"):
        assert key in row, f"Key '{key}' missing from history row"


# ── Seed jobs ─────────────────────────────────────────────────────────────────

def test_seed_jobs_from_json(jobs_json_path):
    count = db.seed_jobs_from_json(jobs_json_path)
    assert count > 0
    jobs = db.get_all_jobs()
    codes = [j["job_code"] for j in jobs]
    assert len(codes) >= count


def test_seed_jobs_idempotent(jobs_json_path):
    """Seeding twice should not duplicate jobs (job_code is UNIQUE)."""
    count1 = db.seed_jobs_from_json(jobs_json_path)
    total_after_first = len(db.get_all_jobs())
    count2 = db.seed_jobs_from_json(jobs_json_path)
    total_after_second = len(db.get_all_jobs())
    # Second seed returns same count and adds zero new rows
    assert count1 == count2
    assert total_after_first == total_after_second, (
        "Second seed call must not create duplicate job rows"
    )


def test_seed_jobs_missing_file():
    count = db.seed_jobs_from_json("/nonexistent/path/does_not_exist.json")
    assert count == 0
