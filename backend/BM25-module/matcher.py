# matcher.py
from bm25_engine import BM25Engine
from utils import preprocess_text

class ResumeMatcher:
    def __init__(self, resumes, jobs):
        """
        resumes: list of dicts {id, text}
        jobs: list of dicts {id, text}
        """
        self.resumes = resumes
        self.jobs = jobs

        self.resume_engine = BM25Engine([r["text"] for r in resumes])
        self.job_engine = BM25Engine([j["text"] for j in jobs])

    def match_job_to_candidates(self, job_text, top_k=5):
        results = self.resume_engine.search(job_text, top_k)
        return self._format_results(results, self.resumes, job_text)

    def match_candidate_to_jobs(self, resume_text, top_k=5):
        results = self.job_engine.search(resume_text, top_k)
        return self._format_results(results, self.jobs, resume_text)

    def _format_results(self, results, dataset, query):
        formatted = []
        query_tokens = set(preprocess_text(query))

        for idx, score in results:
            doc_tokens = set(preprocess_text(dataset[idx]["text"]))
            matched_terms = list(query_tokens.intersection(doc_tokens))

            formatted.append({
                "id": dataset[idx]["id"],
                "score": round(float(score), 4),
                "matched_terms": matched_terms[:10]  # explanation
            })

        return formatted