"""
app.py — Resume Job Matching API v2 (Hybrid Scoring + Blacklist Validation)
────────────────────────────────────────────────────────────────────────────
COMPANY FLOW  → /match, /upload_match  → BM25 (unchanged)
INDIVIDUAL FLOW → /analyze, /whatif   → Hybrid, NO BM25

BLACKLIST INTEGRATION (NEW):
  Every uploaded PDF in /upload_match and /analyze is now screened by
  utils/resume_validator.py BEFORE scoring. Blacklisted resumes are:
    - Excluded from scoring
    - Returned in a dedicated "blacklisted" list with their issues
    - Never added to the preloaded_resumes DB

  Blacklist checks (via validate_resume):
    1. Hidden/very-small font text (< 6pt with > 20 chars)
    2. White / invisible text (color == 16777215)
    3. High similarity to a job description (>= 90% — copy-paste fraud)
    4. No extractable text (scanned PDF)
"""

import os, sys, json, tempfile, logging
from flask import Flask, request, jsonify
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BM25_DIR = os.path.join(BASE_DIR, "BM25-module")
SVC_DIR  = os.path.join(BASE_DIR, "services")
UTL_DIR  = os.path.join(BASE_DIR, "utils")

sys.path.insert(0, BM25_DIR)
sys.path.insert(0, SVC_DIR)
sys.path.insert(0, UTL_DIR)

from matcher           import ResumeMatcher
from parser            import extract_text_from_pdf
from feedback_engine   import extract_skills
from analysis_service  import analyze_single, simulate_whatif_individual
from resume_validator  import validate_resume   # ← BLACKLIST

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── CORS ───────────────────────────────────────────────────────────────────────
CORS(app, resources={r"/*": {"origins": [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://bhadri-raj-t.github.io",
    "https://bhadri-raj-t.github.io/Resume-job-matching",
]}})

# ── Pre-load jobs & resumes ────────────────────────────────────────────────────
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
    if not preloaded_resumes:
        logger.warning("No resumes loaded — db_matcher skipped")
        return
    try:
        db_matcher = ResumeMatcher(
            resumes=preloaded_resumes,
            jobs=preloaded_jobs if preloaded_jobs else []
        )
        logger.info(f"BM25 matcher ready with {len(preloaded_resumes)} resumes")
    except Exception as e:
        logger.error(f"BM25 matcher init failed (non-fatal): {e}")
        db_matcher = None


_rebuild_db_matcher()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _save_temp_pdf(file_storage) -> str:
    """Save an uploaded FileStorage to a temp file and return the path."""
    suffix = os.path.splitext(file_storage.filename)[-1].lower() or ".pdf"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    file_storage.save(tmp.name)
    tmp.close()
    return tmp.name


def _safe_extract_pdf(file_storage) -> str:
    """Extract text from an uploaded PDF, cleaning up the temp file afterwards."""
    tmp_path = _save_temp_pdf(file_storage)
    try:
        return extract_text_from_pdf(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _run_blacklist_check(file_storage) -> tuple[str, list[str]]:
    """
    Save the PDF to a temp file, run validate_resume, delete the temp file.

    Returns:
        (tmp_path_already_deleted, issues)   — issues is [] if CLEAN
    """
    tmp_path = _save_temp_pdf(file_storage)
    try:
        issues = validate_resume(tmp_path, preloaded_jobs)
    except Exception as e:
        logger.warning(f"Blacklist check failed for {file_storage.filename}: {e}")
        issues = []          # don't block upload on validator error
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return issues


def _process_uploads(files):
    """
    Parse and blacklist-screen a list of FileStorage objects.

    Returns a dict with:
      clean      – list of {id, text} dicts ready for scoring
      blacklisted – list of {file, issues} dicts
      parse_errors – list of {file, error} dicts
    """
    clean        = []
    blacklisted  = []
    parse_errors = []

    for file in files:
        filename = file.filename

        # ── 1. Extension check ───────────────────────────────────────────
        if not filename.lower().endswith(".pdf"):
            parse_errors.append({"file": filename, "error": "Not a PDF."})
            continue

        # ── 2. Blacklist check (uses its own temp file) ──────────────────
        # We rewind the stream first in case it was already read
        file.stream.seek(0)
        issues = _run_blacklist_check(file)
        if issues:
            logger.warning(f"BLACKLISTED: {filename} — {issues}")
            blacklisted.append({"file": filename, "issues": issues})
            continue

        # ── 3. Text extraction ───────────────────────────────────────────
        file.stream.seek(0)
        try:
            text = _safe_extract_pdf(file)
            if not text or not text.strip():
                parse_errors.append({"file": filename, "error": "No text extracted."})
                continue
            clean.append({"id": filename, "text": text})
        except Exception as e:
            parse_errors.append({"file": filename, "error": str(e)})

    return {"clean": clean, "blacklisted": blacklisted, "parse_errors": parse_errors}


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status":             "Resume Job Matching API v2",
        "preloaded_resumes":  len(preloaded_resumes),
        "db_matcher_ready":   db_matcher is not None,
        "blacklist_enabled":  True,
        "flows": {
            "company":    "/match, /upload_match  (BM25)",
            "individual": "/analyze, /whatif      (hybrid — no BM25)"
        }
    })


@app.route("/match", methods=["POST"])
def match():
    if db_matcher is None:
        return jsonify({"error": "Database matcher not initialized. BM25 corpus unavailable."}), 503
    data = request.get_json(silent=True)
    if not data or not data.get("job_text", "").strip():
        return jsonify({"error": "'job_text' is required."}), 400
    job_text = data["job_text"].strip()
    top_k    = min(int(data.get("top_k", 5)), len(preloaded_resumes))
    try:
        results = db_matcher.match_job_to_candidates(job_text, top_k=top_k)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({
        "job_text": job_text, "top_k": top_k,
        "total_resumes_in_db": len(preloaded_resumes),
        "results": results
    })


@app.route("/upload_match", methods=["POST"])
def upload_match():
    """
    Company flow: upload resumes + job text → BM25 match.
    Blacklisted resumes are excluded from scoring and reported separately.
    """
    if "resumes" not in request.files:
        return jsonify({"error": "No resume files uploaded."}), 400
    job_text = request.form.get("job_text", "").strip()
    if not job_text:
        return jsonify({"error": "'job_text' is required."}), 400

    processed = _process_uploads(request.files.getlist("resumes"))
    clean        = processed["clean"]
    blacklisted  = processed["blacklisted"]
    parse_errors = processed["parse_errors"]

    if not clean:
        return jsonify({
            "error":        "No valid resumes to score (all were blacklisted or unparseable).",
            "blacklisted":  blacklisted,
            "parse_errors": parse_errors,
        }), 422

    try:
        temp_matcher = ResumeMatcher(resumes=clean, jobs=[])
        results = temp_matcher.match_job_to_candidates(job_text, top_k=len(clean))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "job_text":           job_text,
        "total_uploaded":     len(request.files.getlist("resumes")),
        "total_scored":       len(clean),
        "total_blacklisted":  len(blacklisted),
        "results":            results,
        "blacklisted":        blacklisted,
        "parse_errors":       parse_errors,
    })


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Individual flow: upload resumes + job text → hybrid analysis.
    Blacklisted resumes are excluded from analysis AND from the DB.
    """
    if "resumes" not in request.files:
        return jsonify({"error": "No resume files uploaded."}), 400
    job_text = request.form.get("job_text", "").strip()
    if not job_text:
        return jsonify({"error": "'job_text' is required."}), 400

    processed = _process_uploads(request.files.getlist("resumes"))
    clean        = processed["clean"]
    blacklisted  = processed["blacklisted"]
    parse_errors = processed["parse_errors"]

    if not clean:
        return jsonify({
            "error":        "No valid resumes to analyse (all were blacklisted or unparseable).",
            "blacklisted":  blacklisted,
            "parse_errors": parse_errors,
        }), 422

    # Only CLEAN resumes enter the preloaded DB
    added_to_db  = []
    existing_ids = {r["id"] for r in preloaded_resumes}
    for resume in clean:
        if resume["id"] not in existing_ids:
            preloaded_resumes.append({"id": resume["id"], "text": resume["text"]})
            existing_ids.add(resume["id"])
            added_to_db.append(resume["id"])
    if added_to_db:
        _rebuild_db_matcher()

    analyses = []
    for resume in clean:
        try:
            result = analyze_single(
                resume_text=resume["text"],
                job_text=job_text,
                resume_id=resume["id"],
            )
            analyses.append(result)
        except Exception as e:
            logger.warning(f"Analysis failed for {resume['id']}: {e}")
            analyses.append({
                "id": resume["id"], "error": str(e),
                "match_score": 0, "composite_score": 0
            })

    analyses.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    resume_texts = {r["id"]: r["text"] for r in clean}

    return jsonify({
        "job_text":          job_text,
        "total_uploaded":    len(request.files.getlist("resumes")),
        "total_scored":      len(clean),
        "total_blacklisted": len(blacklisted),
        "analyses":          analyses,
        "resume_texts":      resume_texts,
        "parse_errors":      parse_errors,
        "blacklisted":       blacklisted,
        "scoring_mode":      "individual_hybrid",
        "added_to_db":       added_to_db,
        "total_in_db":       len(preloaded_resumes),
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
