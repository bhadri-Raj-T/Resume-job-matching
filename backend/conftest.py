"""
conftest.py  --  Fixes ModuleNotFoundError by adding BM25-module to sys.path
                 BEFORE any test imports happen.

FIXES APPLIED:
  - BM25_DIR now uses "BM25-module" (actual folder name, not "bm25_module")
  - Also adds it under the alias used by test imports (sys.modules trick)
  - DB_PATH uses a proper tempfile so parallel runs don't collide
"""
import os
import sys
import tempfile
import json
import types
import pytest

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))   # backend/ itself
BM25_DIR    = os.path.join(BACKEND_DIR, "BM25-module")     # actual folder name

# Ensure both backend/ and BM25-module/ are on sys.path
for p in (BACKEND_DIR, BM25_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

# The test files import from "bm25_module.*" (underscore), but the real folder
# is "BM25-module" (hyphen).  Create a virtual package alias so both spellings work.
if "bm25_module" not in sys.modules:
    pkg = types.ModuleType("bm25_module")
    pkg.__path__ = [BM25_DIR]
    pkg.__package__ = "bm25_module"
    sys.modules["bm25_module"] = pkg

# Isolated test DB — each pytest session gets its own file
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_PATH"] = _tmp.name


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def backend_dir():
    return BACKEND_DIR


@pytest.fixture(scope="session")
def jobs_json_path(backend_dir):
    return os.path.join(backend_dir, "data", "jobs", "jobs.json")


@pytest.fixture(scope="session")
def jobs_data(jobs_json_path):
    with open(jobs_json_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def sample_resumes():
    """Eight diverse resumes that cover all job categories in jobs.json."""
    return [
        {
            "id": "Resume_DevOps_001.pdf",
            "text": (
                "DevOps engineer AWS Docker Kubernetes Jenkins CI/CD Terraform "
                "Python Bash Prometheus Grafana Ansible Helm GitOps ArgoCD"
            ),
        },
        {
            "id": "Resume_DS_001.pdf",
            "text": (
                "Data Scientist Python machine learning scikit-learn pandas numpy "
                "tensorflow deep learning NLP SQL statistics hypothesis testing"
            ),
        },
        {
            "id": "Resume_UX_001.pdf",
            "text": (
                "UX UI Designer Figma wireframing user research prototyping "
                "usability testing Adobe XD CSS HTML accessibility design systems"
            ),
        },
        {
            "id": "Resume_Backend_001.pdf",
            "text": (
                "Backend Developer Python Django Flask REST API PostgreSQL Redis "
                "microservices Docker SQLAlchemy authentication JWT"
            ),
        },
        {
            "id": "Resume_Security_001.pdf",
            "text": (
                "Cybersecurity Analyst penetration testing SIEM firewall OWASP "
                "vulnerability assessment network security incident response SOC"
            ),
        },
        {
            "id": "Resume_Cloud_001.pdf",
            "text": (
                "Cloud Architect AWS Azure GCP infrastructure Terraform serverless "
                "Lambda EC2 S3 multi-cloud cost optimisation VPC networking"
            ),
        },
        {
            "id": "Resume_ML_001.pdf",
            "text": (
                "Machine Learning Engineer deep learning PyTorch TensorFlow model "
                "deployment MLOps pipeline GPU training feature engineering"
            ),
        },
        {
            "id": "Resume_Mobile_001.pdf",
            "text": (
                "Mobile Developer iOS Android Swift Kotlin React Native Flutter "
                "cross-platform app development REST API push notifications"
            ),
        },
    ]


@pytest.fixture(scope="session")
def flask_client():
    """Flask test client with an initialised DB."""
    import database as db
    db.init_db()
    from app import app as flask_app
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client
