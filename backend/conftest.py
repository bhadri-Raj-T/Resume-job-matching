"""
conftest.py  --  Fixes ModuleNotFoundError by adding BM25-module to sys.path
                 BEFORE any test imports happen.
"""
import os, sys, tempfile, json, pytest

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))   # backend/ itself
BM25_DIR    = os.path.join(BACKEND_DIR, "bm25_module")

for p in (BACKEND_DIR, BM25_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

# Isolated test DB
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_PATH"] = _tmp.name

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
    return [
        {"id": "Resume_DevOps_001.pdf",  "text": "DevOps engineer AWS Docker Kubernetes Jenkins CI/CD Terraform Python Bash Prometheus Grafana"},
        {"id": "Resume_DS_001.pdf",       "text": "Data Scientist Python machine learning scikit-learn pandas numpy tensorflow deep learning NLP SQL"},
        {"id": "Resume_UX_001.pdf",       "text": "UX UI Designer Figma wireframing user research prototyping usability testing Adobe XD CSS HTML"},
        {"id": "Resume_Backend_001.pdf",  "text": "Backend Developer Python Django Flask REST API PostgreSQL Redis microservices Docker"},
        {"id": "Resume_Security_001.pdf", "text": "Cybersecurity Analyst penetration testing SIEM firewall OWASP vulnerability assessment network security"},
        {"id": "Resume_Cloud_001.pdf",    "text": "Cloud Architect AWS Azure GCP infrastructure Terraform serverless Lambda EC2 S3 multi-cloud"},
        {"id": "Resume_ML_001.pdf",       "text": "Machine Learning Engineer deep learning PyTorch TensorFlow model deployment MLOps pipeline GPU training"},
        {"id": "Resume_Mobile_001.pdf",   "text": "Mobile Developer iOS Android Swift Kotlin React Native Flutter cross-platform app development"},
    ]

@pytest.fixture(scope="session")
def flask_client():
    import database as db
    db.init_db()
    from app import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app.test_client()