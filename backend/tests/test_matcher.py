"""Unit tests for ResumeMatcher"""
import pytest
from bm25_module.matcher import ResumeMatcher

def test_matcher_init(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [{"id": j["id"], "text": j["text"]} for j in jobs_data])
    assert m.resume_engine is not None
    assert m.job_engine is not None

def test_matcher_no_resumes_raises():
    with pytest.raises(ValueError):
        ResumeMatcher(resumes=[], jobs=[]).match_job_to_candidates("test")

def test_match_job_to_candidates_structure(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=3)
    assert isinstance(results, list)
    assert len(results) == 3
    for item in results:
        assert "id" in item
        assert "score" in item
        assert "matched_terms" in item
        assert "match_count" in item
        assert isinstance(item["score"], float)
        assert isinstance(item["matched_terms"], list)

def test_results_sorted_descending(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=5)
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)

def test_devops_job_ranks_devops_resume(sample_resumes, jobs_data):
    devops_job = next(j for j in jobs_data if j["id"].startswith("DEV_"))
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(devops_job["text"], top_k=3)
    top_ids = [r["id"] for r in results]
    assert any("DevOps" in rid or "Cloud" in rid for rid in top_ids), \
        f"Expected DevOps/Cloud in top results, got: {top_ids}"

def test_data_science_job_matches(sample_resumes, jobs_data):
    ds_job = next(j for j in jobs_data if j["id"].startswith("DS_"))
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(ds_job["text"], top_k=3)
    top_ids = [r["id"] for r in results]
    assert any("DS" in rid or "ML" in rid for rid in top_ids), \
        f"Expected DS/ML in top results, got: {top_ids}"

def test_ux_job_matches(sample_resumes, jobs_data):
    ux_job = next(j for j in jobs_data if j["id"].startswith("UX_"))
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(ux_job["text"], top_k=3)
    top_ids = [r["id"] for r in results]
    assert any("UX" in rid for rid in top_ids), \
        f"Expected UX in top results, got: {top_ids}"

def test_security_job_matches(sample_resumes, jobs_data):
    sec_job = next(j for j in jobs_data if j["id"].startswith("SEC_"))
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(sec_job["text"], top_k=3)
    top_ids = [r["id"] for r in results]
    assert any("Security" in rid for rid in top_ids), \
        f"Expected Security in top results, got: {top_ids}"

def test_bidirectional_match(sample_resumes, jobs_data):
    jobs = [{"id": j["id"], "text": j["text"]} for j in jobs_data]
    m = ResumeMatcher(sample_resumes, jobs)
    devops_resume = next(r for r in sample_resumes if "DevOps" in r["id"])
    results = m.match_candidate_to_jobs(devops_resume["text"], top_k=5)
    job_ids = [r["id"] for r in results]
    assert any(jid.startswith("DEV_") for jid in job_ids), \
        f"Expected DEV_ job for DevOps resume, got: {job_ids}"

def test_scores_not_all_zero(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=5)
    assert any(r["score"] > 0 for r in results), "All scores are zero — BM25 broken"

def test_full_corpus_stability(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    for job in jobs_data:
        results = m.match_job_to_candidates(job["text"], top_k=3)
        assert len(results) == 3, f"Expected 3 results for job {job['id']}"

def test_top_k_respects_limit(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=2)
    assert len(results) == 2

def test_matched_terms_are_relevant(sample_resumes):
    resumes = [{"id": "r1.pdf", "text": "Python developer Flask REST API SQL"}]
    m = ResumeMatcher(resumes, [])
    results = m.match_job_to_candidates("Python Flask developer needed", top_k=1)
    terms = results[0]["matched_terms"]
    assert "python" in terms or "flask" in terms or "developer" in terms