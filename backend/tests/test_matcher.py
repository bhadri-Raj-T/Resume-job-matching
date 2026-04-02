"""
tests/test_matcher.py
──────────────────────
Unit tests for ResumeMatcher (BM25-powered two-way matcher).

Covers:
  - Initialisation (resumes-only, jobs-only, both, neither)
  - match_job_to_candidates: structure, ordering, top_k, term relevance
  - match_candidate_to_jobs: bidirectional matching
  - Domain-specific relevance: DevOps, DS/ML, UX, Security jobs
  - Edge cases: empty query, top_k=1, large corpus
"""
import pytest
from bm25_module.matcher import ResumeMatcher


# ── Init ──────────────────────────────────────────────────────────────────────

def test_matcher_init_with_resumes_and_jobs(sample_resumes, jobs_data):
    jobs = [{"id": j["id"], "text": j["text"]} for j in jobs_data]
    m = ResumeMatcher(sample_resumes, jobs)
    assert m.resume_engine is not None
    assert m.job_engine is not None


def test_matcher_init_resumes_only(sample_resumes):
    m = ResumeMatcher(sample_resumes, [])
    assert m.resume_engine is not None
    assert m.job_engine is None


def test_matcher_init_jobs_only(jobs_data):
    jobs = [{"id": j["id"], "text": j["text"]} for j in jobs_data]
    m = ResumeMatcher([], jobs)
    assert m.resume_engine is None
    assert m.job_engine is not None


def test_matcher_init_empty():
    m = ResumeMatcher([], [])
    assert m.resume_engine is None
    assert m.job_engine is None


def test_matcher_no_resumes_raises_on_match(jobs_data):
    m = ResumeMatcher(resumes=[], jobs=[])
    with pytest.raises(ValueError, match="Resume engine not initialized"):
        m.match_job_to_candidates("python developer")


def test_matcher_no_jobs_raises_on_candidate_match(sample_resumes):
    m = ResumeMatcher(resumes=sample_resumes, jobs=[])
    with pytest.raises(ValueError, match="Job engine not initialized"):
        m.match_candidate_to_jobs("python developer flask")


# ── match_job_to_candidates: result structure ─────────────────────────────────

def test_match_job_returns_list(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=3)
    assert isinstance(results, list)


def test_match_job_result_has_required_keys(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=3)
    for item in results:
        assert "id" in item
        assert "score" in item
        assert "matched_terms" in item
        assert "match_count" in item


def test_match_job_score_is_float(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=3)
    for item in results:
        assert isinstance(item["score"], float)


def test_match_job_matched_terms_is_list(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=3)
    for item in results:
        assert isinstance(item["matched_terms"], list)


def test_match_job_match_count_is_int(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=3)
    for item in results:
        assert isinstance(item["match_count"], int)


def test_match_job_id_is_string(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=3)
    for item in results:
        assert isinstance(item["id"], str)


# ── match_job_to_candidates: ordering & top_k ────────────────────────────────

def test_results_sorted_descending(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=5)
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_top_k_respected(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=2)
    assert len(results) == 2


def test_top_k_one(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=1)
    assert len(results) == 1


def test_top_k_capped_at_corpus_size(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=1000)
    assert len(results) <= len(sample_resumes)


# ── Scores ────────────────────────────────────────────────────────────────────

def test_scores_not_all_zero(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=5)
    assert any(r["score"] > 0 for r in results), "All BM25 scores are zero"


def test_scores_non_negative(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=5)
    for r in results:
        assert r["score"] >= 0.0


def test_score_rounded_to_4dp(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=3)
    for r in results:
        assert round(r["score"], 4) == r["score"]


# ── Domain-specific relevance ─────────────────────────────────────────────────

def test_devops_job_ranks_devops_resume_in_top3(sample_resumes, jobs_data):
    devops_job = next(j for j in jobs_data if j["id"].startswith("DEV_"))
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(devops_job["text"], top_k=3)
    top_ids = [r["id"] for r in results]
    assert any("DevOps" in rid or "Cloud" in rid for rid in top_ids), (
        f"Expected DevOps/Cloud resume in top-3, got: {top_ids}"
    )


def test_data_science_job_ranks_ds_resume_in_top3(sample_resumes, jobs_data):
    ds_job = next(j for j in jobs_data if j["id"].startswith("DS_"))
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(ds_job["text"], top_k=3)
    top_ids = [r["id"] for r in results]
    assert any("DS" in rid or "ML" in rid for rid in top_ids), (
        f"Expected DS/ML resume in top-3, got: {top_ids}"
    )


def test_ux_job_ranks_ux_resume_in_top3(sample_resumes, jobs_data):
    ux_job = next(j for j in jobs_data if j["id"].startswith("UX_"))
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(ux_job["text"], top_k=3)
    top_ids = [r["id"] for r in results]
    assert any("UX" in rid for rid in top_ids), (
        f"Expected UX resume in top-3, got: {top_ids}"
    )


def test_security_job_ranks_security_resume_in_top3(sample_resumes, jobs_data):
    sec_job = next(j for j in jobs_data if j["id"].startswith("SEC_"))
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(sec_job["text"], top_k=3)
    top_ids = [r["id"] for r in results]
    assert any("Security" in rid for rid in top_ids), (
        f"Expected Security resume in top-3, got: {top_ids}"
    )


# ── Bidirectional: match_candidate_to_jobs ────────────────────────────────────

def test_bidirectional_match_devops_resume_to_jobs(sample_resumes, jobs_data):
    jobs = [{"id": j["id"], "text": j["text"]} for j in jobs_data]
    m = ResumeMatcher(sample_resumes, jobs)
    devops_resume = next(r for r in sample_resumes if "DevOps" in r["id"])
    results = m.match_candidate_to_jobs(devops_resume["text"], top_k=5)
    job_ids = [r["id"] for r in results]
    assert any(jid.startswith("DEV_") for jid in job_ids), (
        f"Expected DEV_ job for DevOps resume, got: {job_ids}"
    )


def test_bidirectional_result_structure(sample_resumes, jobs_data):
    jobs = [{"id": j["id"], "text": j["text"]} for j in jobs_data]
    m = ResumeMatcher(sample_resumes, jobs)
    results = m.match_candidate_to_jobs(sample_resumes[0]["text"], top_k=3)
    for item in results:
        assert "id" in item and "score" in item


def test_bidirectional_sorted_descending(sample_resumes, jobs_data):
    jobs = [{"id": j["id"], "text": j["text"]} for j in jobs_data]
    m = ResumeMatcher(sample_resumes, jobs)
    results = m.match_candidate_to_jobs(sample_resumes[0]["text"], top_k=5)
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


# ── Matched terms ─────────────────────────────────────────────────────────────

def test_matched_terms_are_lowercase(sample_resumes):
    resumes = [{"id": "r1.pdf", "text": "Python developer Flask REST API SQL"}]
    m = ResumeMatcher(resumes, [])
    results = m.match_job_to_candidates("Python Flask developer needed", top_k=1)
    for term in results[0]["matched_terms"]:
        assert term == term.lower(), f"Term '{term}' should be lowercase"


def test_matched_terms_contain_relevant_keywords(sample_resumes):
    resumes = [{"id": "r1.pdf", "text": "Python developer Flask REST API SQL"}]
    m = ResumeMatcher(resumes, [])
    results = m.match_job_to_candidates("Python Flask developer needed", top_k=1)
    terms = results[0]["matched_terms"]
    assert any(t in ("python", "flask", "developer") for t in terms)


def test_match_count_equals_matched_terms_length(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=3)
    for r in results:
        assert r["match_count"] == len(r["matched_terms"])


def test_matched_terms_capped_at_15(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    results = m.match_job_to_candidates(jobs_data[0]["text"], top_k=5)
    for r in results:
        assert len(r["matched_terms"]) <= 15


# ── Stability ─────────────────────────────────────────────────────────────────

def test_full_corpus_stability(sample_resumes, jobs_data):
    """Matching every job should return exactly 3 results without error."""
    m = ResumeMatcher(sample_resumes, [])
    for job in jobs_data:
        results = m.match_job_to_candidates(job["text"], top_k=3)
        assert len(results) == 3, f"Expected 3 results for job {job['id']}"


def test_repeated_calls_same_output(sample_resumes, jobs_data):
    m = ResumeMatcher(sample_resumes, [])
    r1 = m.match_job_to_candidates(jobs_data[0]["text"], top_k=3)
    r2 = m.match_job_to_candidates(jobs_data[0]["text"], top_k=3)
    assert r1 == r2


# ── Single-document corpus ────────────────────────────────────────────────────

def test_single_resume_always_returned():
    resumes = [{"id": "only.pdf", "text": "Python developer Flask REST API backend SQL"}]
    m = ResumeMatcher(resumes, [])
    results = m.match_job_to_candidates("Python developer needed", top_k=1)
    assert len(results) == 1
    assert results[0]["id"] == "only.pdf"
