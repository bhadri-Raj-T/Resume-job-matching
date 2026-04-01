"""
<<<<<<< HEAD
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

from matcher         import ResumeMatcher
from parser          import extract_text_from_pdf
from feedback_engine import extract_skills
from analysis_service import analyze_single, simulate_whatif_individual

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ── Pre-load resumes for company flow ────────────────────────────────────────
RESUME_DIR = os.path.join(BASE_DIR, "data", "resumes")
preloaded_resumes = []
if os.path.exists(RESUME_DIR):
    for filename in sorted(os.listdir(RESUME_DIR)):
        if filename.lower().endswith(".pdf"):
            fp = os.path.join(RESUME_DIR, filename)
            try:
                text = extract_text_from_pdf(fp)
=======
app.py — Resume Job Matching API
Flask backend with BM25-powered resume matching.
"""

import os
import sys
import json
import tempfile
import logging

from flask import Flask, request, jsonify
from flask_cors import CORS

# ---------- Path setup ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BM25_DIR = os.path.join(BASE_DIR, "BM25-module")
sys.path.insert(0, BM25_DIR)

from matcher import ResumeMatcher
from parser import extract_text_from_pdf

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ---------- Flask app ----------
app = Flask(__name__)
CORS(app)

# ---------- Load pre-indexed resumes ----------
RESUME_DIR = os.path.join(BASE_DIR, "data", "resumes")
preloaded_resumes = []

if os.path.exists(RESUME_DIR):
    for filename in sorted(os.listdir(RESUME_DIR)):
        if filename.lower().endswith(".pdf"):
            file_path = os.path.join(RESUME_DIR, filename)
            try:
                text = extract_text_from_pdf(file_path)
>>>>>>> 4811b8de6831bd805ba04ff820a40c1390059b12
                if text and text.strip():
                    preloaded_resumes.append({"id": filename, "text": text})
            except Exception as e:
                logger.warning(f"Skipping {filename}: {e}")

logger.info(f"Loaded {len(preloaded_resumes)} pre-indexed resumes")

<<<<<<< HEAD
JOB_FILE = os.path.join(BASE_DIR, "data", "jobs", "jobs.json")
preloaded_jobs = []
=======
# ---------- Load pre-indexed jobs ----------
JOB_FILE = os.path.join(BASE_DIR, "data", "jobs", "jobs.json")
preloaded_jobs = []

>>>>>>> 4811b8de6831bd805ba04ff820a40c1390059b12
if os.path.exists(JOB_FILE):
    try:
        with open(JOB_FILE, "r", encoding="utf-8") as f:
            preloaded_jobs = json.load(f)
        logger.info(f"Loaded {len(preloaded_jobs)} jobs")
    except Exception as e:
        logger.error(f"Failed to load jobs.json: {e}")

<<<<<<< HEAD
=======
# ---------- Initialize matcher for pre-loaded data ----------
>>>>>>> 4811b8de6831bd805ba04ff820a40c1390059b12
db_matcher = None
if preloaded_resumes:
    try:
        db_matcher = ResumeMatcher(
            resumes=preloaded_resumes,
            jobs=preloaded_jobs if preloaded_jobs else []
        )
<<<<<<< HEAD
        logger.info("BM25 database matcher ready")
    except Exception as e:
        logger.error(f"Failed to init db_matcher: {e}")


def _safe_extract_pdf(file_storage) -> str:
=======
        logger.info("Database matcher initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize db_matcher: {e}")
else:
    logger.warning("No pre-indexed resumes found. /match route will be unavailable.")


# ─────────────────────────────────────────────
#  Helper
# ─────────────────────────────────────────────

def _safe_extract_pdf(file_storage) -> str:
    """
    Extract text from a Werkzeug FileStorage object by writing to a
    named temp file (pdfplumber needs a seekable file).
    """
>>>>>>> 4811b8de6831bd805ba04ff820a40c1390059b12
    suffix = os.path.splitext(file_storage.filename)[-1].lower() or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file_storage.save(tmp.name)
        tmp_path = tmp.name
    try:
        text = extract_text_from_pdf(tmp_path)
    finally:
        os.unlink(tmp_path)
    return text


<<<<<<< HEAD
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


# ── COMPANY FLOW: BM25 (completely unchanged) ─────────────────────────────────

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
=======
# ─────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "Resume Job Matching API is running",
        "preloaded_resumes": len(preloaded_resumes),
        "preloaded_jobs": len(preloaded_jobs),
        "db_matcher_ready": db_matcher is not None
    })


@app.route("/match", methods=["POST"])
def match():
    """
    Match a job description against the pre-loaded resume database.
    Body: { "job_text": "...", "top_k": 5 }
    """
    if db_matcher is None:
        return jsonify({
            "error": "Database matcher not initialized. Ensure resumes are present in data/resumes/."
        }), 503

    data = request.get_json(silent=True)
    if not data or not data.get("job_text", "").strip():
        return jsonify({"error": "'job_text' field is required and must not be empty."}), 400

    job_text = data["job_text"].strip()
    top_k = min(int(data.get("top_k", 5)), len(preloaded_resumes))

    try:
        results = db_matcher.match_job_to_candidates(job_text, top_k=top_k)
    except Exception as e:
        logger.exception("Error during /match")
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "job_text": job_text,
        "top_k": top_k,
        "total_resumes_in_db": len(preloaded_resumes),
        "results": results
    })
>>>>>>> 4811b8de6831bd805ba04ff820a40c1390059b12


@app.route("/upload_match", methods=["POST"])
def upload_match():
<<<<<<< HEAD
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
=======
    """
    Upload one or more PDF resumes and a job description.
    Each resume is scored independently against the job description.
    Results are returned sorted by score descending.

    Form fields:
        job_text  — job description string (required)
        resumes   — one or more PDF files (required)
    """
    if "resumes" not in request.files:
        return jsonify({"error": "No resume files uploaded. Use field name 'resumes'."}), 400

    job_text = request.form.get("job_text", "").strip()
    if not job_text:
        return jsonify({"error": "'job_text' form field is required and must not be empty."}), 400

    uploaded_files = request.files.getlist("resumes")
    if not uploaded_files or all(f.filename == "" for f in uploaded_files):
        return jsonify({"error": "No valid files received."}), 400

    # Extract text from every uploaded PDF
    parsed_resumes = []
    parse_errors = []

    for file in uploaded_files:
        if not file.filename.lower().endswith(".pdf"):
            parse_errors.append({"file": file.filename, "error": "Not a PDF — skipped."})
            continue
        try:
            text = _safe_extract_pdf(file)
            if not text or not text.strip():
                parse_errors.append({"file": file.filename, "error": "No readable text extracted — skipped."})
                continue
            parsed_resumes.append({"id": file.filename, "text": text})
        except Exception as e:
            parse_errors.append({"file": file.filename, "error": str(e)})

    if not parsed_resumes:
        return jsonify({
            "error": "No resumes could be parsed successfully.",
            "parse_errors": parse_errors
        }), 422

    # Build a fresh matcher for only the uploaded resumes
>>>>>>> 4811b8de6831bd805ba04ff820a40c1390059b12
    try:
        temp_matcher = ResumeMatcher(resumes=parsed_resumes, jobs=[])
        results = temp_matcher.match_job_to_candidates(job_text, top_k=len(parsed_resumes))
    except Exception as e:
<<<<<<< HEAD
        return jsonify({"error": str(e)}), 500
    return jsonify({"job_text": job_text, "total_scored": len(parsed_resumes),
                    "results": results, "parse_errors": parse_errors})


# ── INDIVIDUAL FLOW: Hybrid scoring (NO BM25) ─────────────────────────────────

@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Full analysis — hybrid scoring.
    Works correctly for 1 or more resumes. Scores are always 0-100.
    """
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
    })


@app.route("/whatif", methods=["POST"])
def whatif():
    """
    What-if simulation. NO BM25. Scores always >= 0.
    Body: { resume_text, job_text, add_skills, current_semantic?, current_exp?, current_edu? }
    """
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

=======
        logger.exception("Error during /upload_match scoring")
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "job_text": job_text,
        "total_uploaded": len(uploaded_files),
        "total_scored": len(parsed_resumes),
        "results": results,          # already sorted descending by matcher
        "parse_errors": parse_errors  # files that were skipped, if any
    })


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────
>>>>>>> 4811b8de6831bd805ba04ff820a40c1390059b12

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)