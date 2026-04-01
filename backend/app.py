"""
app.py — Resume Job Matching API v2 (Hybrid Scoring)
─────────────────────────────────────────────────────
COMPANY FLOW  → /match, /upload_match  → BM25 (unchanged)
INDIVIDUAL FLOW → /analyze, /whatif   → Hybrid, NO BM25
"""

import os, sys, json, tempfile, logging
from flask import Flask, request, jsonify
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BM25_DIR = os.path.join(BASE_DIR, "BM25-module")
SVC_DIR  = os.path.join(BASE_DIR, "services")

sys.path.insert(0, BM25_DIR)
sys.path.insert(0, SVC_DIR)

from matcher          import ResumeMatcher
from parser           import extract_text_from_pdf
from feedback_engine  import extract_skills
from analysis_service import analyze_single, simulate_whatif_individual

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── CORS: allow GitHub Pages frontend + localhost for dev ─────────────────────
CORS(app, origins=[
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "https://yourusername.github.io",   # ← WILL BE REPLACED AUTOMATICALLY
])

# ── Pre-load resumes for company flow ────────────────────────────────────────
RESUME_DIR = os.path.join(BASE_DIR, "data", "resumes")
preloaded_resumes = []
if os.path.exists(RESUME_DIR):
    for filename in sorted(os.listdir(RESUME_DIR)):
        if filename.lower().endswith(".pdf"):
            fp = os.path.join(RESUME_DIR, filename)
            try:
                text = extract_text_from_pdf(fp)
                if text and text.strip():
                    preloaded_resumes.append({"id": filename, "text": text})
            except Exception as e:
                logger.warning(f"Skipping {filename}: {e}")

logger.info(f"Loaded {len(preloaded_resumes)} pre-indexed resumes")

JOB_FILE = os.path.join(BASE_DIR, "data", "jobs", "jobs.json")
preloaded_jobs = []
if os.path.exists(JOB_FILE):
    try:
        with open(JOB_FILE, "r", encoding="utf-8") as f:
            preloaded_jobs = json.load(f)
        logger.info(f"Loaded {len(preloaded_jobs)} jobs")
    except Exception as e:
        logger.error(f"Failed to load jobs.json: {e}")

db_matcher = None

def _rebuild_db_matcher():
    global db_matcher
    if preloaded_resumes:
        try:
            db_matcher = ResumeMatcher(
                resumes=preloaded_resumes,
                jobs=preloaded_jobs if preloaded_jobs else []
            )
            logger.info(f"BM25 matcher ready with {len(preloaded_resumes)} resumes")
        except Exception as e:
            logger.error(f"Failed to init db_matcher: {e}")
            db_matcher = None

_rebuild_db_matcher()


def _safe_extract_pdf(file_storage) -> str:
    suffix = os.path.splitext(file_storage.filename)[-1].lower() or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file_storage.save(tmp.name)
        tmp_path = tmp.name
    try:
        text = extract_text_from_pdf(tmp_path)
    finally:
        os.unlink(tmp_path)
    return text


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "Resume Job Matching API v2",
        "preloaded_resumes": len(preloaded_resumes),
        "db_matcher_ready":  db_matcher is not None,
        "flows": {
            "company":    "/match, /upload_match  (BM25)",
            "individual": "/analyze, /whatif      (hybrid — no BM25)"
        }
    })


@app.route("/match", methods=["POST"])
def match():
    if db_matcher is None:
        return jsonify({"error": "Database matcher not initialized."}), 503
    data = request.get_json(silent=True)
    if not data or not data.get("job_text", "").strip():
        return jsonify({"error": "'job_text' is required."}), 400
    job_text = data["job_text"].strip()
    top_k    = min(int(data.get("top_k", 5)), len(preloaded_resumes))
    try:
        results = db_matcher.match_job_to_candidates(job_text, top_k=top_k)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"job_text": job_text, "top_k": top_k,
                    "total_resumes_in_db": len(preloaded_resumes), "results": results})


@app.route("/upload_match", methods=["POST"])
def upload_match():
    if "resumes" not in request.files:
        return jsonify({"error": "No resume files uploaded."}), 400
    job_text = request.form.get("job_text", "").strip()
    if not job_text:
        return jsonify({"error": "'job_text' is required."}), 400
    parsed_resumes, parse_errors = [], []
    for file in request.files.getlist("resumes"):
        if not file.filename.lower().endswith(".pdf"):
            parse_errors.append({"file": file.filename, "error": "Not a PDF."}); continue
        try:
            text = _safe_extract_pdf(file)
            if not text or not text.strip():
                parse_errors.append({"file": file.filename, "error": "No text extracted."}); continue
            parsed_resumes.append({"id": file.filename, "text": text})
        except Exception as e:
            parse_errors.append({"file": file.filename, "error": str(e)})
    if not parsed_resumes:
        return jsonify({"error": "No resumes parsed.", "parse_errors": parse_errors}), 422
    try:
        temp_matcher = ResumeMatcher(resumes=parsed_resumes, jobs=[])
        results = temp_matcher.match_job_to_candidates(job_text, top_k=len(parsed_resumes))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"job_text": job_text, "total_scored": len(parsed_resumes),
                    "results": results, "parse_errors": parse_errors})


@app.route("/analyze", methods=["POST"])
def analyze():
    if "resumes" not in request.files:
        return jsonify({"error": "No resume files uploaded."}), 400
    job_text = request.form.get("job_text", "").strip()
    if not job_text:
        return jsonify({"error": "'job_text' is required."}), 400

    parsed_resumes, parse_errors = [], []
    for file in request.files.getlist("resumes"):
        if not file.filename.lower().endswith(".pdf"):
            parse_errors.append({"file": file.filename, "error": "Not a PDF."}); continue
        try:
            text = _safe_extract_pdf(file)
            if not text or not text.strip():
                parse_errors.append({"file": file.filename, "error": "No text extracted."}); continue
            parsed_resumes.append({"id": file.filename, "text": text})
        except Exception as e:
            parse_errors.append({"file": file.filename, "error": str(e)})

    if not parsed_resumes:
        return jsonify({"error": "No resumes parsed.", "parse_errors": parse_errors}), 422

    # Add new resumes to global BM25 corpus
    added_to_db = []
    existing_ids = {r["id"] for r in preloaded_resumes}
    for resume in parsed_resumes:
        if resume["id"] not in existing_ids:
            preloaded_resumes.append({"id": resume["id"], "text": resume["text"]})
            existing_ids.add(resume["id"])
            added_to_db.append(resume["id"])
    if added_to_db:
        _rebuild_db_matcher()

    analyses = []
    for resume in parsed_resumes:
        try:
            result = analyze_single(
                resume_text=resume["text"],
                job_text=job_text,
                resume_id=resume["id"],
            )
            analyses.append(result)
        except Exception as e:
            logger.warning(f"Analysis failed for {resume['id']}: {e}")
            analyses.append({"id": resume["id"], "error": str(e),
                             "match_score": 0, "composite_score": 0})

    analyses.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    resume_texts = {r["id"]: r["text"] for r in parsed_resumes}

    return jsonify({
        "job_text":       job_text,
        "total_uploaded": len(request.files.getlist("resumes")),
        "total_scored":   len(parsed_resumes),
        "analyses":       analyses,
        "resume_texts":   resume_texts,
        "parse_errors":   parse_errors,
        "scoring_mode":   "individual_hybrid",
        "added_to_db":    added_to_db,
        "total_in_db":    len(preloaded_resumes),
    })


@app.route("/whatif", methods=["POST"])
def whatif():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required."}), 400
    for field in ["resume_text", "job_text", "add_skills"]:
        if field not in data:
            return jsonify({"error": f"'{field}' is required."}), 400
    try:
        result = simulate_whatif_individual(
            resume_text=data["resume_text"],
            job_text=data["job_text"],
            add_skills=data["add_skills"],
            current_semantic=float(data.get("current_semantic", -1)),
            current_exp=float(data.get("current_exp",      -1)),
            current_edu=float(data.get("current_edu",      -1)),
        )
    except Exception as e:
        logger.exception("Error during /whatif")
        return jsonify({"error": str(e)}), 500
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
