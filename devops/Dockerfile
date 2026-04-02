# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Resume Job Matching Backend
# ─────────────────────────────────────────────────────────────────────────────
# FIXES APPLIED:
#   1. pytest + pytest-cov added to requirements so tests run inside the image
#   2. NLTK data downloaded to /usr/local/share/nltk_data (accessible to all users)
#   3. HEALTHCHECK uses curl (lighter than spawning a Python process)
#   4. Non-root user (appuser) for security
#   5. BM25-module symlinked as bm25_module so test imports work without venv tricks
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.10-slim AS base

# System deps: poppler for pdfplumber, curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpoppler-cpp-dev \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies ────────────────────────────────────────────────────
COPY backend/requirements.txt .

# Install app deps + test tools (pytest, coverage) in one layer
RUN pip install --no-cache-dir -r requirements.txt \
        pytest \
        pytest-cov \
        pytest-flask \
    && python -m nltk.downloader punkt punkt_tab stopwords \
        -d /usr/local/share/nltk_data

# ── Application source ─────────────────────────────────────────────────────
COPY backend/ .

# Create a symlink so "from bm25_module.xxx import ..." works inside the image
# (tests import as bm25_module, real folder is BM25-module)
RUN ln -sf /app/BM25-module /app/bm25_module

# Data directory for SQLite warehouse
RUN mkdir -p data

# ── Non-root user ──────────────────────────────────────────────────────────
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

# ── Environment ───────────────────────────────────────────────────────────
ENV DB_PATH=/app/data/warehouse.db
ENV PYTHONUNBUFFERED=1
ENV NLTK_DATA=/usr/local/share/nltk_data
ENV PYTHONPATH=/app

EXPOSE 5000

# ── Health check ──────────────────────────────────────────────────────────
# FIX: use curl instead of python urllib — faster and lighter.
# --fail makes curl exit non-zero on HTTP 4xx/5xx.
# start-period gives the app 30 s to pre-load resumes before checks begin.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl --silent --fail http://localhost:5000/ || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────
CMD ["python", "app.py"]
