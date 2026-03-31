# matcher.py
from bm25_engine import BM25Engine
from utils import preprocess_text


class ResumeMatcher:
    """
    BM25-powered matcher between resumes and job descriptions.

    Both `resumes` and `jobs` are lists of dicts: {"id": str, "text": str}
    Either list may be empty — the corresponding engine simply won't be built.
    """

    def __init__(self, resumes=None, jobs=None):
        self.resumes = resumes or []
        self.jobs = jobs or []

        self.resume_engine = None
        self.job_engine = None

        if self.resumes:
            self.resume_engine = BM25Engine([r["text"] for r in self.resumes])

        if self.jobs:
            self.job_engine = BM25Engine([j["text"] for j in self.jobs])

    # ── Public API ────────────────────────────────────────────────────────────

    def match_job_to_candidates(self, job_text: str, top_k: int = 5):
        """Score all resumes against a job description. Returns sorted descending."""
        if not self.resume_engine:
            raise ValueError("Resume engine not initialized — no valid resumes provided.")

        top_k = min(top_k, len(self.resumes))
        raw_results = self.resume_engine.search(job_text, top_k=top_k)
        return self._format_results(raw_results, self.resumes, job_text)

    def match_candidate_to_jobs(self, resume_text: str, top_k: int = 5):
        """Score all jobs against a resume. Returns sorted descending."""
        if not self.job_engine:
            raise ValueError("Job engine not initialized — no valid jobs provided.")

        top_k = min(top_k, len(self.jobs))
        raw_results = self.job_engine.search(resume_text, top_k=top_k)
        return self._format_results(raw_results, self.jobs, resume_text)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _format_results(self, raw_results, dataset, query):
        """
        Convert raw (index, score) pairs into a clean list of dicts,
        sorted by score descending.
        """
        query_tokens = set(preprocess_text(query))
        formatted = []

        for idx, score in raw_results:
            doc = dataset[idx]
            doc_tokens = set(preprocess_text(doc["text"]))
            matched_terms = sorted(query_tokens.intersection(doc_tokens))

            formatted.append({
                "id": doc["id"],
                "score": round(float(score), 4),
                "matched_terms": matched_terms[:15],
                "match_count": len(matched_terms)
            })

        # Guarantee descending order (BM25Engine already sorts, but be explicit)
        formatted.sort(key=lambda x: x["score"], reverse=True)
        return formatted