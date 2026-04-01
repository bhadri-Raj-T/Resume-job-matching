"""
services/analysis_service.py  (v3 — bugfix release)
──────────────────────────────────────────────────────
INDIVIDUAL FLOW pipeline. Zero BM25. Zero NLTK dependency.

Bugs fixed vs v2:
  1. Skills 0% / None detected
     → Removed _normalise() pre-processing that stripped the slash from CI/CD
     → extract_skills() already lowercases internally; normalise() was redundant
       and broke the 'ci/cd' alias regex pattern
  2. Semantic score too low (5.4%)
     → TF-IDF function now uses Jaccard-boosted cosine for short texts
     → Added skill-overlap bonus to semantic when OpenAI unavailable
  3. Added self-contained SKILL_DB so this module never depends on nltk/utils
     (the feedback_engine import works only if nltk is installed; we add fallback)

Final score = 50% semantic + 30% skill + 10% experience + 10% education
All scores clamped [0, 100]. No negative values possible.
"""

import re
import math
import logging
import sys
import os

_SVC_DIR  = os.path.dirname(os.path.abspath(__file__))
_BM25_DIR = os.path.join(os.path.dirname(_SVC_DIR), "BM25-module")
sys.path.insert(0, _SVC_DIR)
sys.path.insert(0, _BM25_DIR)

from embedding_service import get_similarity  # type: ignore
from scoring_service import (                  # type: ignore
    skill_score, experience_score, education_score,
    final_score, compute_whatif_score,
    WEIGHT_SEMANTIC, WEIGHT_SKILL,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Self-contained skill taxonomy
#  (mirrors feedback_engine._SKILL_DB so we don't depend on NLTK being present)
#  Format: (canonical_name, [aliases], weight, suggestion, learn_time)
# ─────────────────────────────────────────────────────────────────────────────

_SKILL_DB = [
    # Languages
    ("Python",     ["python", "py"],                                                            3, "Add a Python project (FastAPI/Django/Flask) to GitHub.",              "highlight existing"),
    ("Java",       ["java", "jvm", "spring boot", "spring"],                                   3, "Mention Java version and frameworks (Spring Boot) used.",             "highlight existing"),
    ("JavaScript", ["javascript", "js", "ecmascript", "es6", "node.js", "nodejs", "express"],  3, "Showcase a JS project with modern ES6+ features.",                    "highlight existing"),
    ("TypeScript", ["typescript", "ts"],                                                        2, "Migrate a JS project to TypeScript and mention strict typing.",        "1–2 weeks"),
    ("Go",         ["golang", "go lang"],                                                       2, "Build a REST API or CLI tool in Go.",                                  "3–4 weeks"),
    ("Ruby",       ["ruby", "rails", "ruby on rails"],                                         2, "Add a Rails API project or mention MVC experience.",                  "2–3 weeks"),
    ("Rust",       ["rust lang", "rust programming"],                                           2, "Build a systems-level CLI tool in Rust.",                             "4–6 weeks"),
    ("C++",        ["c++", "cpp", "c plus plus"],                                               2, "Highlight performance-critical projects.",                             "highlight existing"),
    ("Scala",      ["scala", "spark scala"],                                                    2, "Highlight Spark/Scala data pipeline work.",                           "3–4 weeks"),
    ("R",          ["r programming", "rstudio", "tidyverse"],                                   2, "Add an R data analysis or visualization project.",                    "2–3 weeks"),

    # Web / Frontend
    ("React",      ["react", "react.js", "reactjs", "react native", "next.js", "nextjs"],      3, "Build a React app with hooks; deploy to Vercel.",                     "3–4 weeks"),
    ("Angular",    ["angular", "angularjs"],                                                    2, "Add an Angular project showcasing services and RxJS.",                "3–4 weeks"),
    ("Vue",        ["vue", "vue.js", "vuejs", "nuxt"],                                          2, "Build and deploy a Vue/Nuxt app.",                                    "2–3 weeks"),
    ("HTML/CSS",   ["html", "html5", "css", "css3", "sass", "scss", "tailwind"],               2, "Mention responsive design projects and CSS frameworks.",              "highlight existing"),
    ("Django",     ["django", "django rest", "drf"],                                            2, "Add a Django REST API project with auth and deployment.",             "2–3 weeks"),
    ("Flask",      ["flask"],                                                                   2, "Describe a Flask microservice project.",                               "1 week"),
    ("FastAPI",    ["fastapi", "fast api"],                                                     2, "Add a FastAPI project with async endpoints.",                         "1 week"),

    # Databases
    ("SQL",        ["sql", "mysql", "postgresql", "postgres", "sqlite", "mssql"],              3, "Showcase complex queries, indexing, and schema design.",              "highlight existing"),
    ("MongoDB",    ["mongodb", "mongo", "nosql"],                                               2, "Add a MongoDB project with aggregation pipelines.",                   "1–2 weeks"),
    ("Redis",      ["redis", "caching"],                                                        2, "Mention Redis usage for caching or pub/sub.",                         "1 week"),
    ("PostgreSQL", ["postgresql", "postgres", "psql"],                                          2, "Highlight advanced PostgreSQL: JSONB, full-text search.",             "highlight existing"),

    # Cloud & DevOps  ← most important for this use case
    ("AWS",        ["aws", "amazon web services", "ec2", "s3 bucket", "lambda",
                    "aws certified", "amazon aws", "aws cloud"],                                3, "Get AWS Cloud Practitioner cert; deploy a project on AWS.",           "4–6 weeks for cert"),
    ("Azure",      ["azure", "microsoft azure", "azure devops", "azure cloud"],                2, "Deploy a project to Azure; mention AKS or Azure Functions.",          "3–4 weeks"),
    ("GCP",        ["gcp", "google cloud", "google cloud platform", "bigquery",
                    "cloud run"],                                                               2, "Deploy to GCP and mention BigQuery or Cloud Run.",                    "3–4 weeks"),
    ("Docker",     ["docker", "dockerfile", "containeriz", "docker hub",
                    "docker certified", "container"],                                           3, "Containerize a project, push to Docker Hub, and add to GitHub.",     "3–5 days"),
    ("Kubernetes", ["kubernetes", "k8s", "kubectl", "helm", "eks", "aks", "gke",
                    "certified kubernetes", "cka", "minikube"],                                3, "Deploy a Dockerized app to Kubernetes (Minikube locally or cloud).",  "2–3 weeks"),
    ("Terraform",  ["terraform", "infrastructure as code", "iac"],                             2, "Write Terraform configs for a cloud project and add to GitHub.",      "1–2 weeks"),
    ("CI/CD",      ["ci/cd", "cicd", "ci cd", "continuous integration",
                    "continuous deployment", "continuous delivery",
                    "jenkins", "gitlab ci", "github actions", "circleci",
                    "travis ci", "pipeline", "cd pipeline", "ci pipeline"],                    3, "Set up a GitHub Actions pipeline for lint + test + deploy.",          "3–5 days"),
    ("Linux",      ["linux", "unix", "bash", "shell script", "bash script",
                    "shell scripting", "bash scripting", "command line",
                    "ubuntu", "centos", "redhat", "debian", "kali"],                           2, "Add automation scripts; mention distros and admin experience.",        "highlight existing"),
    ("Ansible",    ["ansible", "configuration management", "playbook"],                        1, "Write Ansible playbooks to provision a VM.",                          "1–2 weeks"),
    ("Prometheus", ["prometheus", "grafana", "monitoring", "alertmanager"],                    1, "Add monitoring setup with Prometheus/Grafana to a project.",          "1 week"),

    # ML / AI / Data
    ("Machine Learning", ["machine learning", " ml ", "supervised learning",
                          "unsupervised learning", "random forest", "xgboost"],               3, "Add an end-to-end ML project to GitHub.",                             "4–8 weeks"),
    ("Deep Learning",    ["deep learning", "neural network", "cnn", "rnn", "lstm"],           2, "Build and train a neural network; share a Jupyter notebook.",         "4–6 weeks"),
    ("TensorFlow",       ["tensorflow", "keras"],                                              2, "Add a TensorFlow/Keras project with training metrics.",               "2–3 weeks"),
    ("PyTorch",          ["pytorch", "torch"],                                                 2, "Implement a model in PyTorch; share notebooks.",                      "2–3 weeks"),
    ("scikit-learn",     ["scikit-learn", "sklearn", "scikit learn"],                          2, "Showcase a classification/regression project with metrics.",          "1–2 weeks"),
    ("NLP",              ["nlp", "natural language processing", "text mining",
                          "bert", "transformers", "hugging face", "huggingface"],              3, "Add an NLP project using HuggingFace Transformers.",                  "3–4 weeks"),
    ("Data Science",     ["data science", "data analysis", "pandas", "numpy",
                          "matplotlib", "seaborn", "jupyter"],                                 2, "Add a Jupyter notebook project with EDA and visualizations.",         "2–3 weeks"),

    # Tools / Practices
    ("Git",              ["git", "github", "gitlab", "bitbucket", "version control"],         3, "Ensure active public GitHub repos; highlight branching strategies.",  "highlight existing"),
    ("Agile",            ["agile", "scrum", "kanban", "sprint", "jira"],                       2, "Mention sprint ceremonies, story-pointing, or velocity metrics.",    "highlight existing"),
    ("Microservices",    ["microservices", "microservice", "service mesh", "istio"],           2, "Describe a microservices architecture with services and deployment.", "highlight existing"),
    ("Testing",          ["testing", "unit testing", "integration testing",
                          "pytest", "jest", "selenium", "tdd", "bdd", "qa",
                          "test coverage", "quality assurance"],                               2, "Add test coverage metrics; mention frameworks and coverage %.",        "highlight existing"),
    ("Security",         ["security", "owasp", "penetration testing", "pentest",
                          "cybersecurity", "vulnerability", "cissp", "ceh",
                          "siem", "soc", "firewall", "encryption"],                           2, "Mention security audits, OWASP practices, or certifications.",        "highlight existing"),
    ("Figma",            ["figma", "sketch", "adobe xd", "wireframe", "prototype",
                          "ui design", "ux design"],                                           2, "Add a Figma portfolio link with case studies.",                       "highlight existing"),
]

# Build alias lookup: lowercase_alias → (canonical, weight, suggestion, learn_time)
_ALIAS_MAP: dict = {}
for _entry in _SKILL_DB:
    _canonical, _aliases, _weight, _suggestion, _learn_time = _entry
    for _alias in _aliases:
        _ALIAS_MAP[_alias.lower()] = (_canonical, _weight, _suggestion, _learn_time)


# ─────────────────────────────────────────────────────────────────────────────
#  Skill extraction — self-contained, no NLTK required
# ─────────────────────────────────────────────────────────────────────────────

def extract_skills(text: str) -> dict:
    """
    Extract known skills from text using the local _ALIAS_MAP.

    Key design decisions (v3):
      - Does NOT pre-normalise text (no slash removal) because aliases like
        'ci/cd' need the slash to match
      - Uses word-boundary regex (?<![a-z0-9]) / (?![a-z0-9])
      - Falls back to simple 'in' check for multi-word aliases that contain
        special chars (e.g. 'ci/cd')
      - Returns {canonical: (weight, suggestion, learn_time)}
    """
    text_lower = text.lower()
    found: dict = {}

    for alias, (canonical, weight, suggestion, learn_time) in _ALIAS_MAP.items():
        if canonical in found:
            continue  # already matched this skill via a different alias

        # Primary: word-boundary regex
        escaped = re.escape(alias)
        pattern = r'(?<![a-z0-9])' + escaped + r'(?![a-z0-9])'
        if re.search(pattern, text_lower):
            found[canonical] = (weight, suggestion, learn_time)
            continue

        # Fallback: plain substring (catches 'containeriz' prefix, partial matches)
        if len(alias) >= 5 and alias in text_lower:
            found[canonical] = (weight, suggestion, learn_time)

    return found


# ─────────────────────────────────────────────────────────────────────────────
#  Actionable feedback templates
# ─────────────────────────────────────────────────────────────────────────────

_ACTION_TEMPLATES = {
    "Docker":      "Containerize one of your projects using Docker, push to Docker Hub, and document it in your GitHub README.",
    "Kubernetes":  "Deploy a Dockerized app to Kubernetes (start with Minikube locally, then try EKS or GKE).",
    "AWS":         "Get the AWS Cloud Practitioner certification and deploy at least one project on AWS — add it to your resume.",
    "Azure":       "Deploy a project to Azure App Service or AKS; mention specific Azure services used.",
    "GCP":         "Complete the Google Cloud Associate Engineer path and deploy a project using Cloud Run or BigQuery.",
    "CI/CD":       "Set up a GitHub Actions pipeline for lint + test + deploy on one of your public repositories.",
    "Terraform":   "Write Terraform configs to provision your cloud infrastructure and store them in GitHub.",
    "Ansible":     "Write Ansible playbooks to automate VM provisioning and add them to your portfolio.",
    "Python":      "Add a Python project using FastAPI, Django, or data-science stack and publish it on GitHub.",
    "Go":          "Build a production-quality REST API or CLI tool in Go; highlight performance and concurrency.",
    "React":       "Build a React app with hooks and state management; deploy to Vercel or Netlify.",
    "Node.js":     "Build a Node/Express REST API with JWT auth, document it with Swagger, and deploy it.",
    "Machine Learning": "Add an end-to-end ML project (data → training → evaluation → API) to GitHub.",
    "NLP":         "Build an NLP pipeline using HuggingFace Transformers and share a Jupyter notebook.",
    "Security":    "Document security practices (OWASP, pen-testing); consider CEH or OSCP certification.",
    "Testing":     "Add unit and integration test coverage (≥80%) to a project; mention frameworks and coverage %.",
    "Git":         "Ensure active public GitHub repos; highlight branching strategies and code-review experience.",
    "SQL":         "Add a project with complex SQL (JOINs, CTEs, window functions) and schema design.",
    "MongoDB":     "Add a MongoDB project using aggregation pipelines and indexing.",
    "Linux":       "Add automation scripts you've written; mention distros and system admin experience.",
    "Ruby":        "Add a Rails API project and mention MVC architecture experience.",
    "Azure":       "Deploy a project to Azure; mention AKS, Azure Functions, or other services used.",
}


def _get_action(skill: str, default: str) -> str:
    return _ACTION_TEMPLATES.get(skill, default)


# ─────────────────────────────────────────────────────────────────────────────
#  Impact estimation (self-contained, no estimate_skill_impact dependency)
# ─────────────────────────────────────────────────────────────────────────────

def _estimate_impact(missing_skills: dict, job_skills: dict) -> list:
    """
    For each missing skill, estimate composite score improvement.
    Impact = weight/total_weight * WEIGHT_SKILL * 100
    """
    total_weight = sum(v[0] for v in job_skills.values()) if job_skills else 1
    results = []
    for skill, (weight, suggestion, learn_time) in missing_skills.items():
        delta_skill  = weight / total_weight if total_weight > 0 else 0
        impact_pct   = round(delta_skill * WEIGHT_SKILL * 100, 1)
        results.append({
            "skill":       skill,
            "impact":      impact_pct,
            "weight":      weight,
            "suggestion":  _get_action(skill, suggestion),
            "learn_time":  learn_time,
        })
    results.sort(key=lambda x: x["impact"], reverse=True)
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Main analysis function
# ─────────────────────────────────────────────────────────────────────────────

def analyze_single(resume_text: str, job_text: str, resume_id: str = "") -> dict:
    """
    Full individual-flow analysis for ONE resume vs ONE job description.

    v3 fixes:
      - Uses self-contained extract_skills (no NLTK dependency)
      - No _normalise() pre-processing (preserves CI/CD slash for regex)
      - Semantic score uses get_similarity (TF-IDF fallback or OpenAI)
      - All scores guaranteed 0-100
    """

    # ── 1. Skill extraction (raw text — no pre-processing) ───────────────────
    resume_skills = extract_skills(resume_text)
    job_skills    = extract_skills(job_text)

    matched_skills = {s: v for s, v in resume_skills.items() if s in job_skills}
    missing_skills = {s: v for s, v in job_skills.items()    if s not in resume_skills}
    bonus_skills   = {s: v for s, v in resume_skills.items() if s not in job_skills}

    # ── 2. Four scoring signals ───────────────────────────────────────────────
    sem = get_similarity(resume_text, job_text)
    sk  = skill_score(resume_skills, job_skills)
    exp = experience_score(resume_text, job_text)
    edu = education_score(resume_text, job_text)

    # ── 3. Final composite (always 0–100) ─────────────────────────────────────
    composite = final_score(sem, sk, exp, edu)

    # ── 4. Impact list ────────────────────────────────────────────────────────
    impact_list = _estimate_impact(missing_skills, job_skills)

    # ── 5. Fit label ──────────────────────────────────────────────────────────
    if composite >= 80:
        fit_label, fit_color = "Excellent Fit", "green"
    elif composite >= 60:
        fit_label, fit_color = "Good Fit", "amber"
    elif composite >= 40:
        fit_label, fit_color = "Fair Fit", "orange"
    else:
        fit_label, fit_color = "Low Fit", "red"

    # ── 6. Top 5 feedback actions ─────────────────────────────────────────────
    feedback = [
        {
            "skill":      item["skill"],
            "action":     item["suggestion"],
            "impact_pct": item["impact"],
            "learn_time": item.get("learn_time", ""),
        }
        for item in impact_list[:5]
    ]

    return {
        "id":              resume_id,
        "match_score":     composite,
        "composite_score": composite,      # backward compat alias
        "breakdown": {
            "semantic":   round(sem * 100, 1),
            "skills":     round(sk  * 100, 1),
            "experience": round(exp * 100, 1),
            "education":  round(edu * 100, 1),
        },
        "matched_skills":    sorted(matched_skills.keys()),
        "missing_skills":    sorted(missing_skills.keys()),
        "bonus_skills":      sorted(bonus_skills.keys()),
        "job_skills_found":  sorted(job_skills.keys()),
        "impact_list":       impact_list,
        "feedback":          feedback,
        "fit_label":         fit_label,
        "fit_color":         fit_color,
        # Passed back for what-if (avoids re-computing embeddings)
        "_semantic":      sem,
        "_exp":           exp,
        "_edu":           edu,
        "_resume_skills": {k: list(v) for k, v in resume_skills.items()},
        "_job_skills":    {k: list(v) for k, v in job_skills.items()},
    }


# ─────────────────────────────────────────────────────────────────────────────
#  What-if simulation
# ─────────────────────────────────────────────────────────────────────────────

def simulate_whatif_individual(
    resume_text: str,
    job_text: str,
    add_skills: list,
    current_semantic: float = -1,
    current_exp: float = -1,
    current_edu: float = -1,
) -> dict:
    """
    What-if simulation. BM25-free. All scores guaranteed >= 0.
    Recomputes any missing signals automatically.
    """
    if current_semantic < 0:
        current_semantic = get_similarity(resume_text, job_text)
    if current_exp < 0:
        current_exp = experience_score(resume_text, job_text)
    if current_edu < 0:
        current_edu = education_score(resume_text, job_text)

    resume_skills = extract_skills(resume_text)
    job_skills    = extract_skills(job_text)

    return compute_whatif_score(
        resume_skills=resume_skills,
        added_skills=add_skills,
        job_skills=job_skills,
        current_semantic=current_semantic,
        current_exp=current_exp,
        current_edu=current_edu,
    )