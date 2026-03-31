"""
services/analysis_service.py  (v4 - Groq AI suggestions)
──────────────────────────────────────────────────────────
INDIVIDUAL FLOW pipeline. Zero BM25. Zero NLTK dependency.

v4 changes:
  - AI-powered improvement suggestions via Groq SDK (streaming)
  - Falls back to static templates if Groq unavailable/fails
  - Groq generates personalised suggestions based on actual JD context

Install: pip install groq
Key is read from embedding_service._GROQ_KEY (set it there once)
"""

import re
import math
import json
import logging
import sys
import os

_SVC_DIR  = os.path.dirname(os.path.abspath(__file__))
_BM25_DIR = os.path.join(os.path.dirname(_SVC_DIR), "BM25-module")
sys.path.insert(0, _SVC_DIR)
sys.path.insert(0, _BM25_DIR)

from embedding_service import get_similarity, _GROQ_KEY, _GROQ_AVAILABLE  # type: ignore
from scoring_service import (                                                # type: ignore
    skill_score, experience_score, education_score,
    final_score, compute_whatif_score,
    WEIGHT_SEMANTIC, WEIGHT_SKILL,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Skill taxonomy
# ─────────────────────────────────────────────────────────────────────────────

_SKILL_DB = [
    # Languages
    ("Python",     ["python", "py"],                                                            3, "Add a Python project (FastAPI/Django/Flask) to GitHub.",              "highlight existing"),
    ("Java",       ["java", "jvm", "spring boot", "spring"],                                   3, "Mention Java version and frameworks (Spring Boot) used.",             "highlight existing"),
    ("JavaScript", ["javascript", "js", "ecmascript", "es6", "node.js", "nodejs", "express"],  3, "Showcase a JS project with modern ES6+ features.",                    "highlight existing"),
    ("TypeScript", ["typescript", "ts"],                                                        2, "Migrate a JS project to TypeScript and mention strict typing.",        "1-2 weeks"),
    ("Go",         ["golang", "go lang"],                                                       2, "Build a REST API or CLI tool in Go.",                                  "3-4 weeks"),
    ("Ruby",       ["ruby", "rails", "ruby on rails"],                                         2, "Add a Rails API project or mention MVC experience.",                  "2-3 weeks"),
    ("Rust",       ["rust lang", "rust programming"],                                           2, "Build a systems-level CLI tool in Rust.",                             "4-6 weeks"),
    ("C++",        ["c++", "cpp", "c plus plus"],                                               2, "Highlight performance-critical projects.",                             "highlight existing"),
    ("Scala",      ["scala", "spark scala"],                                                    2, "Highlight Spark/Scala data pipeline work.",                           "3-4 weeks"),
    ("R",          ["r programming", "rstudio", "tidyverse"],                                   2, "Add an R data analysis or visualization project.",                    "2-3 weeks"),
    # Web / Frontend
    ("React",      ["react", "react.js", "reactjs", "react native", "next.js", "nextjs"],      3, "Build a React app with hooks; deploy to Vercel.",                     "3-4 weeks"),
    ("Angular",    ["angular", "angularjs"],                                                    2, "Add an Angular project showcasing services and RxJS.",                "3-4 weeks"),
    ("Vue",        ["vue", "vue.js", "vuejs", "nuxt"],                                          2, "Build and deploy a Vue/Nuxt app.",                                    "2-3 weeks"),
    ("HTML/CSS",   ["html", "html5", "css", "css3", "sass", "scss", "tailwind"],               2, "Mention responsive design projects and CSS frameworks.",              "highlight existing"),
    ("Django",     ["django", "django rest", "drf"],                                            2, "Add a Django REST API project with auth and deployment.",             "2-3 weeks"),
    ("Flask",      ["flask"],                                                                   2, "Describe a Flask microservice project.",                               "1 week"),
    ("FastAPI",    ["fastapi", "fast api"],                                                     2, "Add a FastAPI project with async endpoints.",                         "1 week"),
    # Databases
    ("SQL",        ["sql", "mysql", "postgresql", "postgres", "sqlite", "mssql"],              3, "Showcase complex queries, indexing, and schema design.",              "highlight existing"),
    ("MongoDB",    ["mongodb", "mongo", "nosql"],                                               2, "Add a MongoDB project with aggregation pipelines.",                   "1-2 weeks"),
    ("Redis",      ["redis", "caching"],                                                        2, "Mention Redis usage for caching or pub/sub.",                         "1 week"),
    ("PostgreSQL", ["postgresql", "postgres", "psql"],                                          2, "Highlight advanced PostgreSQL: JSONB, full-text search.",             "highlight existing"),
    # Cloud & DevOps
    ("AWS",        ["aws", "amazon web services", "ec2", "s3 bucket", "lambda",
                    "aws certified", "amazon aws", "aws cloud"],                                3, "Get AWS Cloud Practitioner cert; deploy a project on AWS.",           "4-6 weeks for cert"),
    ("Azure",      ["azure", "microsoft azure", "azure devops", "azure cloud"],                2, "Deploy a project to Azure; mention AKS or Azure Functions.",          "3-4 weeks"),
    ("GCP",        ["gcp", "google cloud", "google cloud platform", "bigquery", "cloud run"],  2, "Deploy to GCP and mention BigQuery or Cloud Run.",                    "3-4 weeks"),
    ("Docker",     ["docker", "dockerfile", "containeriz", "docker hub",
                    "docker certified", "container"],                                           3, "Containerize a project, push to Docker Hub, and add to GitHub.",     "3-5 days"),
    ("Kubernetes", ["kubernetes", "k8s", "kubectl", "helm", "eks", "aks", "gke",
                    "certified kubernetes", "cka", "minikube"],                                3, "Deploy a Dockerized app to Kubernetes (Minikube locally or cloud).",  "2-3 weeks"),
    ("Terraform",  ["terraform", "infrastructure as code", "iac"],                             2, "Write Terraform configs for a cloud project and add to GitHub.",      "1-2 weeks"),
    ("CI/CD",      ["ci/cd", "cicd", "ci cd", "continuous integration",
                    "continuous deployment", "continuous delivery",
                    "jenkins", "gitlab ci", "github actions", "circleci",
                    "travis ci", "pipeline", "cd pipeline", "ci pipeline"],                    3, "Set up a GitHub Actions pipeline for lint + test + deploy.",          "3-5 days"),
    ("Linux",      ["linux", "unix", "bash", "shell script", "bash script",
                    "shell scripting", "bash scripting", "command line",
                    "ubuntu", "centos", "redhat", "debian"],                                   2, "Add automation scripts; mention distros and admin experience.",        "highlight existing"),
    ("Ansible",    ["ansible", "configuration management", "playbook"],                        1, "Write Ansible playbooks to provision a VM.",                          "1-2 weeks"),
    ("Prometheus", ["prometheus", "grafana", "monitoring", "alertmanager"],                    1, "Add monitoring setup with Prometheus/Grafana to a project.",          "1 week"),
    # ML / AI / Data
    ("Machine Learning", ["machine learning", " ml ", "supervised learning",
                          "unsupervised learning", "random forest", "xgboost"],               3, "Add an end-to-end ML project to GitHub.",                             "4-8 weeks"),
    ("Deep Learning",    ["deep learning", "neural network", "cnn", "rnn", "lstm"],           2, "Build and train a neural network; share a Jupyter notebook.",         "4-6 weeks"),
    ("TensorFlow",       ["tensorflow", "keras"],                                              2, "Add a TensorFlow/Keras project with training metrics.",               "2-3 weeks"),
    ("PyTorch",          ["pytorch", "torch"],                                                 2, "Implement a model in PyTorch; share notebooks.",                      "2-3 weeks"),
    ("scikit-learn",     ["scikit-learn", "sklearn", "scikit learn"],                          2, "Showcase a classification/regression project with metrics.",          "1-2 weeks"),
    ("NLP",              ["nlp", "natural language processing", "text mining",
                          "bert", "transformers", "hugging face", "huggingface"],              3, "Add an NLP project using HuggingFace Transformers.",                  "3-4 weeks"),
    ("Data Science",     ["data science", "data analysis", "pandas", "numpy",
                          "matplotlib", "seaborn", "jupyter"],                                 2, "Add a Jupyter notebook project with EDA and visualizations.",         "2-3 weeks"),
    # Tools / Practices
    ("Git",              ["git", "github", "gitlab", "bitbucket", "version control"],         3, "Ensure active public GitHub repos; highlight branching strategies.",  "highlight existing"),
    ("Agile",            ["agile", "scrum", "kanban", "sprint", "jira"],                       2, "Mention sprint ceremonies, story-pointing, or velocity metrics.",    "highlight existing"),
    ("Microservices",    ["microservices", "microservice", "service mesh", "istio"],           2, "Describe a microservices architecture with services and deployment.", "highlight existing"),
    ("Testing",          ["testing", "unit testing", "integration testing",
                          "pytest", "jest", "selenium", "tdd", "bdd", "qa",
                          "test coverage", "quality assurance"],                               2, "Add test coverage metrics; mention frameworks and coverage %.",        "highlight existing"),
    ("Security",         ["security", "owasp", "penetration testing", "pentest",
                          "cybersecurity", "vulnerability", "cissp", "ceh"],                  2, "Mention security audits, OWASP practices, or certifications.",        "highlight existing"),
    ("Figma",            ["figma", "sketch", "adobe xd", "wireframe", "prototype",
                          "ui design", "ux design"],                                           2, "Add a Figma portfolio link with case studies.",                       "highlight existing"),
]

# Build alias lookup
_ALIAS_MAP: dict = {}
for _entry in _SKILL_DB:
    _canonical, _aliases, _weight, _suggestion, _learn_time = _entry
    for _alias in _aliases:
        _ALIAS_MAP[_alias.lower()] = (_canonical, _weight, _suggestion, _learn_time)

# Static fallback templates
_ACTION_TEMPLATES = {
    "Docker":      "Containerize one of your projects using Docker, push to Docker Hub, and document it in your GitHub README.",
    "Kubernetes":  "Deploy a Dockerized app to Kubernetes (start with Minikube locally, then try EKS or GKE).",
    "AWS":         "Get the AWS Cloud Practitioner certification and deploy at least one project on AWS.",
    "CI/CD":       "Set up a GitHub Actions pipeline for lint + test + deploy on one of your public repositories.",
    "Python":      "Add a Python project using FastAPI, Django, or data-science stack and publish it on GitHub.",
    "React":       "Build a React app with hooks and state management; deploy to Vercel or Netlify.",
    "TypeScript":  "Migrate an existing JavaScript project to TypeScript; enable strict mode.",
    "MongoDB":     "Add a MongoDB project using aggregation pipelines and indexing on MongoDB Atlas.",
    "Testing":     "Add unit and integration test coverage (>=80%) to a project; mention frameworks and coverage %.",
    "Git":         "Ensure active public GitHub repos; highlight branching strategies and code-review experience.",
}


def _get_static_action(skill: str, default: str) -> str:
    return _ACTION_TEMPLATES.get(skill, default)


# ─────────────────────────────────────────────────────────────────────────────
#  Groq AI suggestions  (uses groq SDK with streaming)
# ─────────────────────────────────────────────────────────────────────────────

def _get_groq_suggestions(missing_skills: list, job_text: str, resume_text: str) -> dict:
    """
    Call Groq (streaming) to generate personalised suggestions for missing skills.
    Returns { "SkillName": {"suggestion": "...", "learn_time": "..."} }
    Returns {} on any failure so static templates are used instead.
    """
    if not _GROQ_AVAILABLE or not _GROQ_KEY or _GROQ_KEY == "your-groq-api-key-here":
        return {}
    if not missing_skills:
        return {}

    skills_str = ", ".join(missing_skills[:8])  # cap at 8 to keep tokens low

    prompt = f"""You are a career coach helping a software developer improve their resume for a specific job.

The candidate is MISSING these skills that the job requires: {skills_str}

JOB DESCRIPTION (first 800 chars):
{job_text[:800]}

CANDIDATE RESUME (first 600 chars):
{resume_text[:600]}

For each missing skill, give:
1. A specific actionable suggestion (1-2 sentences) based on how the skill is used in THIS job
2. A realistic time estimate to acquire it

Respond ONLY with a valid JSON object, no markdown, no extra text:
{{
  "SkillName1": {{"suggestion": "...", "learn_time": "X weeks"}},
  "SkillName2": {{"suggestion": "...", "learn_time": "X days"}}
}}

Use EXACTLY the skill names provided. Keep each suggestion under 160 characters."""

    try:
        from groq import Groq as _GroqClient
        client = _GroqClient(api_key=_GROQ_KEY)

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a career coaching assistant. Respond only with valid JSON objects, no markdown."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.3,
            max_completion_tokens=600,
            top_p=1,
            stream=True,
            stop=None,
        )

        # Collect streamed chunks into full response
        response_text = ""
        for chunk in completion:
            response_text += chunk.choices[0].delta.content or ""

        # Strip markdown fences if model added them
        response_text = re.sub(r"```json\s*", "", response_text).strip()
        response_text = re.sub(r"```\s*",     "", response_text).strip()

        parsed = json.loads(response_text)
        logger.info(f"Groq AI suggestions received for {len(parsed)} skills: {list(parsed.keys())}")
        return parsed

    except Exception as e:
        logger.warning(f"Groq suggestions failed: {e} — using static templates")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
#  Skill extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_skills(text: str) -> dict:
    text_lower = text.lower()
    found: dict = {}

    for alias, (canonical, weight, suggestion, learn_time) in _ALIAS_MAP.items():
        if canonical in found:
            continue
        escaped = re.escape(alias)
        pattern = r'(?<![a-z0-9])' + escaped + r'(?![a-z0-9])'
        if re.search(pattern, text_lower):
            found[canonical] = (weight, suggestion, learn_time)
            continue
        if len(alias) >= 5 and alias in text_lower:
            found[canonical] = (weight, suggestion, learn_time)

    return found


# ─────────────────────────────────────────────────────────────────────────────
#  Impact estimation — uses Groq suggestions when available
# ─────────────────────────────────────────────────────────────────────────────

def _estimate_impact(missing_skills: dict, job_skills: dict,
                     job_text: str = "", resume_text: str = "") -> list:
    total_weight = sum(v[0] for v in job_skills.values()) if job_skills else 1

    # Single batch Groq call for all missing skills
    ai_suggestions = _get_groq_suggestions(
        missing_skills=list(missing_skills.keys()),
        job_text=job_text,
        resume_text=resume_text,
    )

    results = []
    for skill, (weight, default_suggestion, default_learn_time) in missing_skills.items():
        delta_skill = weight / total_weight if total_weight > 0 else 0
        impact_pct  = round(delta_skill * WEIGHT_SKILL * 100, 1)

        # Prefer AI suggestion, fall back to static template, then DB default
        if skill in ai_suggestions and isinstance(ai_suggestions[skill], dict):
            suggestion = ai_suggestions[skill].get("suggestion") or _get_static_action(skill, default_suggestion)
            learn_time = ai_suggestions[skill].get("learn_time") or default_learn_time
            ai_powered = True
        else:
            suggestion = _get_static_action(skill, default_suggestion)
            learn_time = default_learn_time
            ai_powered = False

        results.append({
            "skill":      skill,
            "impact":     impact_pct,
            "weight":     weight,
            "suggestion": suggestion,
            "learn_time": learn_time,
            "ai_powered": ai_powered,   # frontend can show a sparkle badge
        })

    results.sort(key=lambda x: x["impact"], reverse=True)
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Main analysis function
# ─────────────────────────────────────────────────────────────────────────────

def analyze_single(resume_text: str, job_text: str, resume_id: str = "") -> dict:
    # 1. Skill extraction
    resume_skills = extract_skills(resume_text)
    job_skills    = extract_skills(job_text)

    matched_skills = {s: v for s, v in resume_skills.items() if s in job_skills}
    missing_skills = {s: v for s, v in job_skills.items()    if s not in resume_skills}
    bonus_skills   = {s: v for s, v in resume_skills.items() if s not in job_skills}

    # 2. Scoring signals (get_similarity uses Groq if key set)
    sem = get_similarity(resume_text, job_text)
    sk  = skill_score(resume_skills, job_skills)
    exp = experience_score(resume_text, job_text)
    edu = education_score(resume_text, job_text)

    # 3. Composite score
    composite = final_score(sem, sk, exp, edu)

    # 4. Impact list with Groq AI suggestions
    impact_list = _estimate_impact(
        missing_skills=missing_skills,
        job_skills=job_skills,
        job_text=job_text,
        resume_text=resume_text,
    )

    # 5. Fit label
    if composite >= 80:
        fit_label, fit_color = "Excellent Fit", "green"
    elif composite >= 60:
        fit_label, fit_color = "Good Fit", "amber"
    elif composite >= 40:
        fit_label, fit_color = "Fair Fit", "orange"
    else:
        fit_label, fit_color = "Low Fit", "red"

    # 6. Top 5 feedback
    feedback = [
        {
            "skill":      item["skill"],
            "action":     item["suggestion"],
            "impact_pct": item["impact"],
            "learn_time": item.get("learn_time", ""),
            "ai_powered": item.get("ai_powered", False),
        }
        for item in impact_list[:5]
    ]

    groq_active = bool(_GROQ_AVAILABLE and _GROQ_KEY and _GROQ_KEY != "your-groq-api-key-here")

    return {
        "id":              resume_id,
        "match_score":     composite,
        "composite_score": composite,
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
        "ai_suggestions":    groq_active,
        # Passed back for what-if
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