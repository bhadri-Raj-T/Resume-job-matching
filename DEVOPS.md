# DevOps Documentation — Resume Job Matching System
**Review 2 Submission**

---

## 1. Project Overview (DevOps Scope)

This document covers all DevOps-related aspects of the Resume Job Matching project:
containerisation with Docker, continuous integration and delivery with Jenkins,
automated testing with pytest, and local deployment workflow.

The application is a Flask REST API backed by a SQLite data warehouse.
The CI/CD pipeline automates testing, building a Docker image, and deploying
the container on a local Jenkins/Docker setup.

---

## 2. Project Structure

```
resume-matcher/
├── backend/                  # Application source
│   ├── app.py                # Flask API entry point
│   ├── database.py           # SQLite warehouse layer
│   ├── BM25-module/          # Core matching engine
│   │   ├── bm25_engine.py
│   │   ├── matcher.py
│   │   ├── parser.py
│   │   └── utils.py
│   ├── data/
│   │   ├── jobs/jobs.json    # Seeded job data
│   │   └── warehouse.db      # SQLite DB (generated at runtime)
│   ├── tests/                # All pytest test modules
│   │   ├── conftest.py       # Path fix + shared fixtures
│   │   ├── test_utils.py
│   │   ├── test_bm25_engine.py
│   │   ├── test_matcher.py
│   │   ├── test_database.py
│   │   └── test_api.py
│   ├── requirements.txt
│   └── pytest.ini
├── devops/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── Jenkinsfile
└── docs/
    └── DEVOPS.md             # This file
```

---

## 3. Data Warehouse Design

### Why SQLite?
SQLite is an embedded, zero-configuration database. For a college-level project
running locally it is ideal: no separate database service to manage, the file
travels with the project, and it supports enough concurrency for this use case.

### Schema (Star Schema)

```
               ┌────────────────┐
               │  dim_companies │
               │  id, name,     │
               │  industry      │
               └───────┬────────┘
                       │ 1
                       │
               ┌───────▼────────┐        ┌─────────────────┐
               │   dim_jobs     │        │   dim_resumes    │
               │  id, job_code, │        │  id, filename,   │
               │  title,        │        │  file_hash,      │
               │  description   │        │  extracted_text  │
               └───────┬────────┘        └────────┬────────┘
                       │                          │
                       │ N                     N  │
                       └─────────┐  ┌────────────┘
                                 │  │
                          ┌──────▼──▼──────┐
                          │  fact_matches  │
                          │  resume_id,    │
                          │  job_id,       │
                          │  bm25_score,   │
                          │  matched_terms │
                          └───────────────┘
```

**Key design decisions:**
- `file_hash` (SHA-256) on `dim_resumes` prevents duplicate processing — uploading
  the same PDF twice is a no-op.
- `processed_tokens` column caches tokenisation output so resumes are never
  re-parsed from raw text on repeated queries.
- The `fact_matches` table stores every match event, enabling history queries.

---

## 4. Docker Setup

### 4.1 Dockerfile

Located at `devops/Dockerfile`. Build context is the **project root** so that
`COPY backend/` can copy the full backend directory.

Key choices:
- Base image `python:3.10-slim` keeps the image small.
- NLTK data is downloaded at **build time** so the container starts instantly.
- A named Docker volume (`warehouse_data`) persists the SQLite file across
  container restarts.
- A `HEALTHCHECK` instruction lets Docker (and docker-compose) know when the
  app is ready.

### 4.2 Build and Run Manually

```bash
# From project root
docker build -f devops/Dockerfile -t resume-matcher-backend .
docker run -d \
    --name resume-matcher-backend \
    -p 5000:5000 \
    -v resume_warehouse:/app/data \
    resume-matcher-backend
```

### 4.3 docker-compose

```bash
# From project root
docker compose -f devops/docker-compose.yml up -d        # start
docker compose -f devops/docker-compose.yml down         # stop
docker compose -f devops/docker-compose.yml logs -f      # watch logs
```

The compose file mounts a named volume so the warehouse survives `docker compose down`.

---

## 5. Automated Testing with pytest

### 5.1 Running Tests Locally

```bash
cd backend
python -m pytest                         # run all tests (uses pytest.ini)
python -m pytest tests/test_utils.py    # single file
python -m pytest -v --tb=long           # verbose with full tracebacks
python -m pytest --cov=. --cov-report=term-missing   # with coverage
```

> **Note on ModuleNotFoundError** — The `tests/conftest.py` file inserts both
> `backend/` and `backend/BM25-module/` into `sys.path` before any test
> imports. This means pytest can be run from `backend/` **or** from the project
> root without path errors.

### 5.2 Test Modules

| File | What It Tests |
|------|--------------|
| `test_utils.py` | Text preprocessing (tokenisation, stopwords, tech-term preservation) |
| `test_bm25_engine.py` | BM25Engine initialisation, search, edge cases |
| `test_matcher.py` | ResumeMatcher end-to-end: job↔resume and resume↔job matching |
| `test_database.py` | SQLite warehouse: CRUD for companies, jobs, resumes, match history |
| `test_api.py` | Flask API endpoints: status codes, error handling, response shapes |

### 5.3 Test Isolation

Tests use a temporary SQLite file (set via `DB_PATH` env var in `conftest.py`),
so they never touch the production warehouse.

---

## 6. Jenkins Pipeline

### 6.1 Prerequisites (Local Jenkins)

1. Jenkins running locally (default port 8080).
2. Docker installed and the Jenkins user added to the `docker` group:
   ```bash
   sudo usermod -aG docker jenkins
   sudo systemctl restart jenkins
   ```
3. Python 3.10+ available on the Jenkins agent.
4. The GitHub repository URL configured in the Jenkinsfile.

### 6.2 Pipeline Stages

```
Checkout → Install Dependencies → Test Utils → Test BM25 Engine →
Test Matcher → Test Database → Test API → Full Suite + Coverage →
Docker Build → Docker Deploy → Health Check
```

Each test stage runs a **separate pytest invocation** for a specific module.
If any stage fails, Jenkins stops immediately and shows exactly which test
file caused the failure.

### 6.3 Creating the Pipeline in Jenkins

1. Open Jenkins → New Item → Pipeline.
2. Name it `resume-matcher`.
3. Under **Pipeline** → Definition → select **Pipeline script from SCM**.
4. SCM: Git, Repository URL: your GitHub URL.
5. Script Path: `devops/Jenkinsfile`.
6. Save and click **Build Now**.

### 6.4 Reading Build Output

Each test stage produces output like:

```
PASSED tests/test_utils.py::test_basic_tokenization
PASSED tests/test_utils.py::test_stopwords_removed
...
5 passed in 0.34s
```

If a test fails you will see:

```
FAILED tests/test_matcher.py::test_devops_job_ranks_devops_resume
AssertionError: Expected DevOps/Cloud in top results, got: [...]
```

---

## 7. CI/CD Flow Summary

```
Developer pushes code to GitHub
           │
           ▼
    Jenkins detects change
           │
           ▼
   Install Dependencies
           │
           ▼
  ┌────────────────────┐
  │  Test Utils        │ ← fails fast if preprocessing broken
  │  Test BM25 Engine  │ ← fails fast if BM25 core broken
  │  Test Matcher      │ ← fails fast if matching logic broken
  │  Test Database     │ ← fails fast if warehouse broken
  │  Test API          │ ← fails fast if API endpoints broken
  │  Full Suite +Cov   │ ← generates coverage.xml
  └────────────────────┘
           │ all pass
           ▼
    Docker Build (image tagged with BUILD_NUMBER)
           │
           ▼
    Docker Deploy (old container replaced)
           │
           ▼
    Health Check (curl http://localhost:5000/)
           │
           ▼
    SUCCESS / FAILURE notification
```

---

## 8. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PATH` | `backend/data/warehouse.db` | Path to the SQLite warehouse file |
| `PYTHONUNBUFFERED` | `1` | Ensures real-time log output in Docker |

---

## 9. Suggestions for Future Improvement

These are ideas to strengthen the project further:

- **Replace SQLite with PostgreSQL** for production — add a `db` service to docker-compose.
- **Add pytest-html** for an HTML test report artifact in Jenkins.
- **Docker multi-stage build** to separate a test stage (running pytest inside Docker) from the runtime image.
- **GitHub Actions** as an alternative to local Jenkins — runs on every push automatically with no local setup.
- **SonarQube** for static code analysis — add a stage to the Jenkinsfile.
- **Named pipeline triggers** — configure Jenkins to poll GitHub every 5 minutes or use a webhook.
