"""
app.py  --  Resume Job Matching API (warehouse-backed)
"""
import os, sys, json, tempfile, logging
from flask import Flask, request, jsonify
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)   # only backend/ on path, NOT bm25_module/ inside it

from bm25_module.matcher import ResumeMatcher
from bm25_module.parser  import extract_text_from_pdf
import database as db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

db.init_db()
db.seed_jobs_from_json(os.path.join(BASE_DIR, "data", "jobs", "jobs.json"))

# ─────────────────────── matcher state ────────────────────────
_matcher     = None
_resume_rows = []   # list of {id, text, _db_id}

def _refresh_matcher():
    global _matcher, _resume_rows
    rows = []
    with db.get_connection() as conn:
        for r in conn.execute("SELECT id,filename,extracted_text FROM dim_resumes").fetchall():
            rows.append({"id": r["filename"], "text": r["extracted_text"], "_db_id": r["id"]})
    jobs = [{"id": j["job_code"], "text": j["description"]} for j in db.get_all_jobs()]
    _resume_rows = rows
    _matcher = ResumeMatcher(resumes=rows, jobs=jobs) if rows else None
    logger.info("Matcher refreshed: %d resumes, %d jobs", len(rows), len(jobs))

_refresh_matcher()

# ─────────────────────── helpers ──────────────────────────────
def _safe_extract(file_storage):
    suf = os.path.splitext(file_storage.filename)[-1].lower() or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suf) as tmp:
        file_storage.save(tmp.name); path = tmp.name
    try:
        return extract_text_from_pdf(path)
    finally:
        os.unlink(path)

# ─────────────────────── routes ───────────────────────────────
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "Resume Job Matching API is running",
        "warehouse_resumes": len(db.get_all_resumes()),
        "warehouse_jobs":    len(db.get_all_jobs()),
        "matcher_ready":     _matcher is not None
    })

@app.route("/companies", methods=["GET"])
def list_companies():
    return jsonify(db.get_all_companies())

@app.route("/companies", methods=["POST"])
def add_company():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Company 'name' is required"}), 400
    cid = db.upsert_company(name, data.get("industry"), data.get("website"))
    return jsonify({"id": cid, "name": name}), 201

@app.route("/jobs", methods=["GET"])
def list_jobs():
    cid = request.args.get("company_id", type=int)
    return jsonify(db.get_all_jobs(company_id=cid))

@app.route("/jobs/<job_code>", methods=["GET"])
def get_job(job_code):
    job = db.get_job_by_code(job_code)
    return (jsonify(job) if job else jsonify({"error": f"Job '{job_code}' not found"}), 404 if not job else 200)

@app.route("/jobs", methods=["POST"])
def add_job():
    data = request.get_json(silent=True) or {}
    for f in ("job_code","title","description"):
        if not (data.get(f) or "").strip():
            return jsonify({"error": f"'{f}' is required"}), 400
    cid = data.get("company_id")
    if not cid and data.get("company_name"):
        cid = db.upsert_company(data["company_name"].strip())
    jid = db.upsert_job(data["job_code"].strip(), data["title"].strip(), data["description"].strip(), company_id=cid)
    _refresh_matcher()
    return jsonify({"id": jid, "job_code": data["job_code"]}), 201

@app.route("/resumes", methods=["GET"])
def list_resumes():
    return jsonify(db.get_all_resumes())

@app.route("/upload_resume", methods=["POST"])
def upload_resume():
    if "resume" not in request.files:
        return jsonify({"error": "Use field name 'resume'"}), 400
    file = request.files["resume"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files supported"}), 400
    try:
        text = _safe_extract(file)
    except Exception as e:
        return jsonify({"error": str(e)}), 422
    if not text.strip():
        return jsonify({"error": "No readable text found"}), 422
    rid, is_new = db.store_resume(file.filename, text)
    _refresh_matcher()
    return jsonify({"resume_id": rid, "filename": file.filename, "is_new": is_new,
                    "message": "Stored & indexed." if is_new else "Already in warehouse."}), 201 if is_new else 200

@app.route("/match", methods=["POST"])
def match():
    data  = request.get_json(silent=True) or {}
    jtext = (data.get("job_text") or "").strip()
    if not jtext:
        return jsonify({"error": "'job_text' is required"}), 400   # validate FIRST
    if _matcher is None:
        return jsonify({"error": "No resumes in warehouse. Upload resumes first."}), 503
    top_k = min(int(data.get("top_k", 5)), len(_resume_rows))
    try:
        results = _matcher.match_job_to_candidates(jtext, top_k=top_k)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    id_map = {r["id"]: r["_db_id"] for r in _resume_rows}
    for r in results: r["resume_db_id"] = id_map.get(r["id"], -1)
    jcode = data.get("job_code")
    if jcode:
        job = db.get_job_by_code(jcode)
        if job: db.store_match_results(job["id"], results)
    return jsonify({"job_text": jtext, "top_k": top_k,
                    "total_resumes_in_warehouse": len(_resume_rows), "results": results})

@app.route("/match/job/<job_code>", methods=["GET"])
def match_by_job_code(job_code):
    job = db.get_job_by_code(job_code)
    if not job: return jsonify({"error": f"Job '{job_code}' not found"}), 404
    if _matcher is None: return jsonify({"error": "No resumes in warehouse."}), 503
    top_k = min(request.args.get("top_k", 5, type=int), len(_resume_rows))
    try:
        results = _matcher.match_job_to_candidates(job["description"], top_k=top_k)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    id_map = {r["id"]: r["_db_id"] for r in _resume_rows}
    for r in results: r["resume_db_id"] = id_map.get(r["id"], -1)
    db.store_match_results(job["id"], results)
    return jsonify({"job_code": job_code, "job_title": job["title"],
                    "company": job.get("company_name"), "top_k": top_k, "results": results})

@app.route("/history", methods=["GET"])
def match_history():
    return jsonify(db.get_match_history(
        job_id=request.args.get("job_id", type=int),
        resume_id=request.args.get("resume_id", type=int),
        limit=request.args.get("limit", 50, type=int)
    ))

@app.route("/upload_match", methods=["POST"])
def upload_match():
    if "resumes" not in request.files:
        return jsonify({"error": "Use field 'resumes'"}), 400
    jtext = request.form.get("job_text","").strip()
    if not jtext: return jsonify({"error": "'job_text' required"}), 400
    files = request.files.getlist("resumes")
    if not files or all(f.filename=="" for f in files):
        return jsonify({"error": "No valid files"}), 400
    parsed, errors = [], []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            errors.append({"file": f.filename, "error": "Not a PDF"}); continue
        try:
            text = _safe_extract(f)
            if not text.strip(): errors.append({"file": f.filename, "error": "No text"}); continue
            rid, _ = db.store_resume(f.filename, text)
            parsed.append({"id": f.filename, "text": text, "_db_id": rid})
        except Exception as e:
            errors.append({"file": f.filename, "error": str(e)})
    if not parsed:
        return jsonify({"error": "No resumes parsed", "parse_errors": errors}), 422
    try:
        tm = ResumeMatcher(resumes=parsed, jobs=[])
        results = tm.match_job_to_candidates(jtext, top_k=len(parsed))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    id_map = {r["id"]: r["_db_id"] for r in parsed}
    for r in results: r["resume_db_id"] = id_map.get(r["id"], -1)
    _refresh_matcher()
    return jsonify({"job_text": jtext, "total_uploaded": len(files),
                    "total_scored": len(parsed), "results": results, "parse_errors": errors})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)