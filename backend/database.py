"""
database.py  --  Data Warehouse Layer (SQLite star-schema)
"""
import os, sqlite3, json, hashlib, logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "warehouse.db")
)

@contextmanager
def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS dim_companies (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL UNIQUE,
                industry   TEXT,
                website    TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS dim_jobs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                job_code         TEXT NOT NULL UNIQUE,
                title            TEXT NOT NULL,
                company_id       INTEGER REFERENCES dim_companies(id),
                description      TEXT NOT NULL,
                processed_tokens TEXT,
                created_at       TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS dim_resumes (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                filename         TEXT NOT NULL,
                file_hash        TEXT NOT NULL UNIQUE,
                extracted_text   TEXT NOT NULL,
                processed_tokens TEXT,
                uploaded_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS fact_matches (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id     INTEGER NOT NULL REFERENCES dim_resumes(id),
                job_id        INTEGER NOT NULL REFERENCES dim_jobs(id),
                bm25_score    REAL NOT NULL,
                matched_terms TEXT,
                match_count   INTEGER,
                matched_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_company   ON dim_jobs(company_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_code      ON dim_jobs(job_code);
            CREATE INDEX IF NOT EXISTS idx_resumes_hash   ON dim_resumes(file_hash);
            CREATE INDEX IF NOT EXISTS idx_matches_job    ON fact_matches(job_id);
            CREATE INDEX IF NOT EXISTS idx_matches_resume ON fact_matches(resume_id);
        """)
    logger.info("DB init at %s", DB_PATH)

# --- Companies ---
def upsert_company(name, industry=None, website=None):
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM dim_companies WHERE name=?", (name,)).fetchone()
        if row: return row["id"]
        return conn.execute("INSERT INTO dim_companies(name,industry,website) VALUES(?,?,?)", (name,industry,website)).lastrowid

def get_all_companies():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM dim_companies ORDER BY name").fetchall()]

# --- Jobs ---
def upsert_job(job_code, title, description, company_id=None, processed_tokens=None):
    tj = json.dumps(processed_tokens) if processed_tokens else None
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM dim_jobs WHERE job_code=?", (job_code,)).fetchone()
        if row:
            if tj: conn.execute("UPDATE dim_jobs SET processed_tokens=? WHERE job_code=?", (tj, job_code))
            return row["id"]
        return conn.execute(
            "INSERT INTO dim_jobs(job_code,title,company_id,description,processed_tokens) VALUES(?,?,?,?,?)",
            (job_code, title, company_id, description, tj)
        ).lastrowid

def get_all_jobs(company_id=None):
    with get_connection() as conn:
        sql = "SELECT j.*,c.name as company_name FROM dim_jobs j LEFT JOIN dim_companies c ON j.company_id=c.id"
        if company_id:
            return [dict(r) for r in conn.execute(sql+" WHERE j.company_id=? ORDER BY j.job_code", (company_id,)).fetchall()]
        return [dict(r) for r in conn.execute(sql+" ORDER BY j.job_code").fetchall()]

def get_job_by_code(job_code):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT j.*,c.name as company_name FROM dim_jobs j LEFT JOIN dim_companies c ON j.company_id=c.id WHERE j.job_code=?",
            (job_code,)
        ).fetchone()
        return dict(row) if row else None

# --- Resumes ---
def _hash(text): return hashlib.sha256(text.encode()).hexdigest()

def store_resume(filename, extracted_text, processed_tokens=None):
    fh = _hash(extracted_text)
    tj = json.dumps(processed_tokens) if processed_tokens else None
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM dim_resumes WHERE file_hash=?", (fh,)).fetchone()
        if row: return row["id"], False
        rid = conn.execute(
            "INSERT INTO dim_resumes(filename,file_hash,extracted_text,processed_tokens) VALUES(?,?,?,?)",
            (filename, fh, extracted_text, tj)
        ).lastrowid
        return rid, True

def get_resume_by_hash(text):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM dim_resumes WHERE file_hash=?", (_hash(text),)).fetchone()
        return dict(row) if row else None

def get_all_resumes():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT id,filename,uploaded_at FROM dim_resumes ORDER BY uploaded_at DESC").fetchall()]

def get_resume_tokens(resume_id):
    with get_connection() as conn:
        row = conn.execute("SELECT processed_tokens FROM dim_resumes WHERE id=?", (resume_id,)).fetchone()
        return json.loads(row["processed_tokens"]) if row and row["processed_tokens"] else None

# --- Matches ---
def store_match_results(job_id, results):
    rows = [(r["resume_db_id"], job_id, r["score"], json.dumps(r.get("matched_terms",[])), r.get("match_count",0)) for r in results]
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO fact_matches(resume_id,job_id,bm25_score,matched_terms,match_count) VALUES(?,?,?,?,?)",
            rows
        )

def get_match_history(job_id=None, resume_id=None, limit=50):
    sql = """SELECT fm.id,fm.bm25_score,fm.match_count,fm.matched_at,
                    r.filename AS resume_filename, j.job_code, j.title AS job_title, c.name AS company_name
             FROM fact_matches fm
             JOIN dim_resumes r ON fm.resume_id=r.id
             JOIN dim_jobs j ON fm.job_id=j.id
             LEFT JOIN dim_companies c ON j.company_id=c.id"""
    with get_connection() as conn:
        if job_id and resume_id:
            rows = conn.execute(sql+" WHERE fm.job_id=? AND fm.resume_id=? ORDER BY fm.bm25_score DESC LIMIT ?", (job_id,resume_id,limit)).fetchall()
        elif job_id:
            rows = conn.execute(sql+" WHERE fm.job_id=? ORDER BY fm.bm25_score DESC LIMIT ?", (job_id,limit)).fetchall()
        elif resume_id:
            rows = conn.execute(sql+" WHERE fm.resume_id=? ORDER BY fm.bm25_score DESC LIMIT ?", (resume_id,limit)).fetchall()
        else:
            rows = conn.execute(sql+" ORDER BY fm.matched_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

# --- Seed ---
def seed_jobs_from_json(jobs_json_path):
    if not os.path.exists(jobs_json_path): return 0
    with open(jobs_json_path, encoding="utf-8") as f:
        jobs = json.load(f)
    for job in jobs:
        cid = upsert_company(job.get("company","Unknown"))
        upsert_job(job["id"], job.get("title", job["id"]), job["text"], company_id=cid)
    logger.info("Seeded %d jobs", len(jobs))
    return len(jobs)
