import os
import json
import pytest

from matcher import ResumeMatcher
from parser import extract_resume_text


# -----------------------------
# Fixtures
# -----------------------------

@pytest.fixture(scope="module")
def resumes_data():
    resume_folder = "backend/data/resumes"
    resumes = []

    for file in os.listdir(resume_folder):
        path = os.path.join(resume_folder, file)
        text = extract_resume_text(path)

        if text.strip():
            resumes.append({
                "id": file,
                "text": text
            })

    return resumes


@pytest.fixture(scope="module")
def jobs_data():
    with open("backend/data/jobs/jobs.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def matcher(resumes_data, jobs_data):
    return ResumeMatcher(resumes_data, jobs_data)


# -----------------------------
# 1️⃣ Basic Initialization Test
# -----------------------------

def test_bm25_initialization(resumes_data):
    assert len(resumes_data) > 0, "No resumes loaded"
    assert all(len(r["text"]) > 0 for r in resumes_data)


# -----------------------------
# 2️⃣ Top-K Structure Test
# -----------------------------

def test_top_k_output_structure(matcher, jobs_data):
    job = jobs_data[0]["text"]
    results = matcher.match_job_to_candidates(job, top_k=5)

    assert isinstance(results, list)
    assert len(results) == 5

    for item in results:
        assert "id" in item
        assert "score" in item
        assert "matched_terms" in item
        assert isinstance(item["score"], float)


# -----------------------------
# 3️⃣ DevOps Job Should Rank DevOps Resume Higher
# -----------------------------

def test_devops_job_matching(matcher, jobs_data):
    devops_job = next(j for j in jobs_data if j["id"].startswith("DEV_"))
    results = matcher.match_job_to_candidates(devops_job["text"], top_k=5)

    top_ids = [r["id"] for r in results]

    assert any("DevOps" in rid or "Cloud" in rid for rid in top_ids), \
        "DevOps-related resumes not ranked high for DevOps job"


# -----------------------------
# 4️⃣ Data Science Matching
# -----------------------------

def test_data_science_job_matching(matcher, jobs_data):
    ds_job = next(j for j in jobs_data if j["id"].startswith("DS_"))
    results = matcher.match_job_to_candidates(ds_job["text"], top_k=5)

    top_ids = [r["id"] for r in results]

    assert any("Data_Scientist" in rid or "Machine_Learning" in rid for rid in top_ids), \
        "Data Science resumes not ranked high for DS job"


# -----------------------------
# 5️⃣ UX Matching
# -----------------------------

def test_ux_job_matching(matcher, jobs_data):
    ux_job = next(j for j in jobs_data if j["id"].startswith("UX_"))
    results = matcher.match_job_to_candidates(ux_job["text"], top_k=5)

    top_ids = [r["id"] for r in results]

    assert any("UX_UI" in rid for rid in top_ids), \
        "UX resumes not ranked high for UX job"


# -----------------------------
# 6️⃣ Cybersecurity Matching
# -----------------------------

def test_security_job_matching(matcher, jobs_data):
    sec_job = next(j for j in jobs_data if j["id"].startswith("SEC_"))
    results = matcher.match_job_to_candidates(sec_job["text"], top_k=5)

    top_ids = [r["id"] for r in results]

    assert any("Cybersecurity" in rid for rid in top_ids), \
        "Security resumes not ranked high for Security job"


# -----------------------------
# 7️⃣ Bidirectional Matching
# -----------------------------

def test_candidate_to_job_matching(matcher, resumes_data):
    resume = next(r for r in resumes_data if "DevOps" in r["id"])
    results = matcher.match_candidate_to_jobs(resume["text"], top_k=5)

    top_job_ids = [r["id"] for r in results]

    assert any(job_id.startswith("DEV_") for job_id in top_job_ids), \
        "DevOps resume not matching DevOps jobs properly"


# -----------------------------
# 8️⃣ Score Sanity Check
# -----------------------------

def test_scores_not_all_zero(matcher, jobs_data):
    job = jobs_data[0]["text"]
    results = matcher.match_job_to_candidates(job, top_k=5)

    scores = [r["score"] for r in results]

    assert any(score != 0 for score in scores), \
        "All scores are zero — BM25 may not be working"


# -----------------------------
# 9️⃣ No Crash With Full Corpus
# -----------------------------

def test_full_corpus_stability(matcher, jobs_data):
    for job in jobs_data:
        results = matcher.match_job_to_candidates(job["text"], top_k=3)
        assert len(results) == 3