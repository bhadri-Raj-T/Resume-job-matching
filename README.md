# ResumeIQ — AI Resume & Job Matching System

A full-stack AI-powered resume analysis and job matching platform. Upload resumes, paste a job description, and get detailed match scores, skill gap analysis, and personalised improvement suggestions — all in real time.

**Live demo:** [bhadri-raj-t.github.io/Resume-job-matching](https://bhadri-raj-t.github.io/Resume-job-matching) · **API:** hosted on Render

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [API Reference](#api-reference)
- [Local Development](#local-development)
- [Deployment](#deployment)
- [Running Tests](#running-tests)
- [Environment Variables](#environment-variables)
- [Tech Stack](#tech-stack)

---

## Features

| Feature | Description |
|---|---|
| **Upload & Analyse** | Upload one or more PDF resumes and get a composite match score against any job description |
| **Database Match** | Match a job description against 400+ pre-indexed resumes using BM25 full-text search |
| **Skill Gap Analysis** | Identifies matched and missing skills from a curated taxonomy of 50+ tech skills |
| **What-If Simulation** | See exactly how much your score improves if you add specific skills |
| **AI Suggestions** | Groq-powered personalised improvement tips based on the actual job description |
| **Hybrid Scoring** | Combines semantic similarity (TF-IDF cosine), skill overlap, experience years, and education tier |

---

## Architecture

```
┌─────────────────────────────────┐       ┌──────────────────────────────────────┐
│        Frontend (GitHub Pages)  │       │         Backend (Render)             │
│                                 │       │                                      │
│  ┌──────────────┐               │       │  ┌───────────┐   ┌────────────────┐  │
│  │ Upload &     │  POST /analyze│──────▶│  │ Analysis  │   │ BM25 Module    │  │
│  │ Analyse tab  │◀──────────────│       │  │ Service   │   │                │  │
│  └──────────────┘               │       │  │ (Hybrid)  │   │ bm25_engine.py │  │
│                                 │       │  └─────┬─────┘   │ matcher.py     │  │
│  ┌──────────────┐               │       │        │          │ parser.py      │  │
│  │ Database     │  POST /match  │──────▶│  ┌─────▼─────┐   │ utils.py       │  │
│  │ Match tab    │◀──────────────│       │  │ ResumeMatcher   └────────────────┘  │
│  └──────────────┘               │       │  │ (BM25)    │                      │
│                                 │       │  └───────────┘                      │
│  ┌──────────────┐               │       │                                      │
│  │ What-If      │  POST /whatif │──────▶│  ┌───────────┐   ┌────────────────┐  │
│  │ Simulator    │◀──────────────│       │  │ Scoring   │   │ Groq AI        │  │
│  └──────────────┘               │       │  │ Service   │   │ (suggestions)  │  │
│                                 │       │  └───────────┘   └────────────────┘  │
└─────────────────────────────────┘       └──────────────────────────────────────┘
```

**Two matching flows:**

- **Company flow** (`/match`, `/upload_match`) — BM25 keyword search, fast, used for bulk candidate screening
- **Individual flow** (`/analyze`, `/whatif`) — Hybrid scoring (semantic + skill + experience + education), used for detailed personal analysis

---

## Project Structure

```
Resume-job-matching/
├── frontend/
│   └── src/
│       ├── index.html          # Single-page app (two-tab UI)
│       ├── script.js           # All UI logic, API calls, rendering
│       └── style.css           # Styling (Syne + DM Sans fonts)
│
├── backend/
│   ├── app.py                  # Flask API entry point, route definitions
│   ├── requirements.txt        # Python dependencies
│   ├── render.yaml             # Render deployment config
│   │
│   ├── BM25-module/            # Core keyword-matching engine
│   │   ├── bm25_engine.py      # BM25Okapi wrapper with index mapping
│   │   ├── matcher.py          # ResumeMatcher: resume↔job orchestration
│   │   ├── parser.py           # Multi-strategy PDF text extraction
│   │   ├── utils.py            # Text preprocessing (tokenise, stopwords)
│   │   └── feedback_engine.py  # Skill taxonomy + extraction logic
│   │
│   ├── services/
│   │   ├── analysis_service.py # Hybrid scoring pipeline (individual flow)
│   │   ├── scoring_service.py  # Skill / experience / education scorers
│   │   └── embedding_service.py# TF-IDF cosine similarity + Groq AI
│   │
│   ├── data/
│   │   ├── resumes/            # 400 pre-indexed PDF resumes
│   │   └── jobs/jobs.json      # Seeded job descriptions
│   │
│   ├── utils/
│   │   └── resume_validator.py # PDF validation helpers
│   │
│   └── tests/
│       ├── test_utils.py
│       ├── test_bm25_engine.py
│       ├── test_matcher.py
│       ├── test_database.py
│       └── test_api.py
│
├── devops/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── Jenkinsfile             # CI/CD pipeline (checkout → test → build → deploy)
│
└── .github/
    └── workflows/
        └── deploy-frontend.yml # GitHub Actions: auto-deploy frontend to Pages
```

---

## How It Works

### Scoring (Individual Flow)

Each resume is scored across four dimensions that combine into a single composite percentage:

| Component | Weight | Method |
|---|---|---|
| Semantic similarity | 50% | TF-IDF cosine similarity between resume and job description |
| Skill match | 30% | Weighted overlap against a 50+ skill taxonomy |
| Experience | 10% | Years extracted from text via regex; ratio to job requirement |
| Education | 10% | Tier comparison (PhD=5 → bootcamp=1) |

**Formula:** `score = 0.50×semantic + 0.30×skill + 0.10×experience + 0.10×education`

### BM25 (Company Flow)

Uses [rank-bm25](https://github.com/dorianbrown/rank_bm25) (BM25Okapi) to index all pre-loaded resumes at startup. At query time the job description is tokenised and scored against the corpus — returns ranked candidates with matched terms.

### PDF Parsing

Two-strategy extraction with automatic best-pick:

1. **pdfplumber** — layout-aware, best for most PDFs
2. **pypdf** — handles UTF-16 encoded fonts that pdfplumber silently skips

Whichever produces more characters wins.

---

## API Reference

**Base URL:** `https://your-render-app.onrender.com`

### `GET /`
Health check. Returns service status and whether the BM25 db_matcher is ready.

```json
{
  "status": "Resume Job Matching API v2",
  "preloaded_resumes": 400,
  "db_matcher_ready": true,
  "flows": {
    "company": "/match, /upload_match  (BM25)",
    "individual": "/analyze, /whatif      (hybrid — no BM25)"
  }
}
```

---

### `POST /analyze`
Upload resumes and analyse them against a job description (individual hybrid flow).

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `resumes` | file(s) | yes | One or more PDF files |
| `job_text` | string | yes | The full job description |

**Response:**
```json
{
  "job_text": "...",
  "total_uploaded": 2,
  "total_scored": 2,
  "scoring_mode": "individual_hybrid",
  "analyses": [
    {
      "id": "resume.pdf",
      "match_score": 78.4,
      "composite_score": 78.4,
      "semantic_score": 0.82,
      "skill_score": 0.71,
      "experience_score": 0.85,
      "education_score": 0.90,
      "matched_skills": ["Python", "AWS", "Docker"],
      "missing_skills": ["Kubernetes", "Terraform"],
      "suggestions": ["..."]
    }
  ]
}
```

---

### `POST /match`
Match a job description against the pre-loaded resume database (BM25 company flow).

**Request:** `application/json`

```json
{
  "job_text": "Senior Python developer with AWS and Kubernetes experience",
  "top_k": 5
}
```

**Response:**
```json
{
  "job_text": "...",
  "top_k": 5,
  "total_resumes_in_db": 400,
  "results": [
    {
      "id": "Resume_010_DevOps_Engineer.pdf",
      "score": 4.2871,
      "matched_terms": ["python", "aws", "kubernetes", "docker"],
      "match_count": 4
    }
  ]
}
```

---

### `POST /upload_match`
Upload your own batch of resumes and rank them against a job description (BM25).

**Request:** `multipart/form-data`

| Field | Type | Required |
|---|---|---|
| `resumes` | file(s) | yes |
| `job_text` | string | yes |

---

### `POST /whatif`
Simulate how adding specific skills would change a resume's match score.

**Request:** `application/json`

```json
{
  "resume_text": "...",
  "job_text": "...",
  "add_skills": ["Kubernetes", "Terraform"],
  "current_semantic": 0.82,
  "current_exp": 0.85,
  "current_edu": 0.90
}
```

**Response:**
```json
{
  "current_score": 72.5,
  "simulated_score": 81.3,
  "delta": 8.8,
  "new_skill_score": 0.87,
  "skills_effective": ["Kubernetes", "Terraform"],
  "skills_not_in_jd": []
}
```

---

## Local Development

### Prerequisites

- Python 3.10+
- pip

### Setup

```bash
# Clone the repo
git clone https://github.com/bhadri-Raj-T/Resume-job-matching.git
cd Resume-job-matching

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Download NLTK data
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords')"
```

### Run the backend

```bash
cd backend
python app.py
# API is now running at http://localhost:5000
```

### Run the frontend

Open `frontend/src/index.html` in your browser, or serve it with any static server:

```bash
# Using Python's built-in server
cd frontend/src
python -m http.server 5500
# Visit http://localhost:5500
```

> Make sure the API URL in `script.js` points to `http://localhost:5000` for local dev.

### Run with Docker

```bash
# From project root
docker build -f devops/Dockerfile -t resume-matcher .
docker run -p 5000:5000 resume-matcher
```

Or with docker-compose:

```bash
docker compose -f devops/docker-compose.yml up
```

---

## Deployment

### Backend — Render

The backend is deployed as a Render web service using `backend/render.yaml`.

1. Push the repo to GitHub
2. Create a new **Web Service** on [render.com](https://render.com)
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` — no manual config needed
5. Add your `GROQ_API_KEY` in the Render environment variables dashboard
6. Deploy

> **Note:** The `render.yaml` sets `NLTK_DATA` to a persistent path so NLTK data downloaded at build time is available at runtime. This is what keeps `db_matcher_ready: true`.

### Frontend — GitHub Pages

The frontend deploys automatically via GitHub Actions on every push to `main`.

The workflow file is at `.github/workflows/deploy-frontend.yml`. No manual steps needed after the first setup — just push and the live site updates within ~30 seconds.

---

## Running Tests

```bash
cd backend

# Run all tests
python -m pytest -v

# Run a specific module
python -m pytest tests/test_matcher.py -v

# Run with coverage report
python -m pytest --cov=. --cov-report=term-missing
```

| Test file | What it covers |
|---|---|
| `test_utils.py` | Tokenisation, stopword removal, tech-term preservation |
| `test_bm25_engine.py` | BM25Engine init, search, empty-doc edge cases |
| `test_matcher.py` | ResumeMatcher end-to-end: job→resume and resume→job |
| `test_database.py` | SQLite warehouse CRUD for companies, jobs, resumes |
| `test_api.py` | Flask endpoints: status codes, error handling, response shapes |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | No | Enables AI-powered improvement suggestions via Groq. Falls back to static templates if not set. |
| `NLTK_DATA` | No | Path where NLTK corpora are stored. Set automatically by `render.yaml` on Render. |
| `PORT` | No | Port for gunicorn (Render sets this automatically). Defaults to `5000`. |
| `DB_PATH` | No | Path to the SQLite warehouse file. Defaults to `backend/data/warehouse.db`. |

---

## Tech Stack

**Frontend**
- Vanilla HTML / CSS / JavaScript (no framework)
- Hosted on GitHub Pages

**Backend**
- Python 3.10+ · Flask · flask-cors
- Gunicorn (production server)
- Hosted on Render

**Matching & NLP**
- [rank-bm25](https://github.com/dorianbrown/rank_bm25) — BM25Okapi full-text search
- scikit-learn — TF-IDF vectoriser + cosine similarity
- NLTK — tokenisation and stopwords (with regex fallback)
- pdfplumber + pypdf — multi-strategy PDF text extraction

**AI**
- [Groq](https://groq.com) — fast LLM inference for personalised improvement suggestions

**DevOps**
- Docker + docker-compose
- Jenkins (CI/CD pipeline: test → build → deploy)
- GitHub Actions (frontend auto-deploy)

---

## Contributing

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Make your changes, then commit
git add .
git commit -m "describe your change"
git push origin feature/your-feature-name

# Open a pull request — merges are done manually on GitHub
```

Run `pytest -v` before opening a PR to make sure all tests pass.

---

## License

MIT — see [LICENSE](LICENSE) for details.
