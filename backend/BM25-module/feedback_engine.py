# feedback_engine.py
"""
Feedback Engine — the USP layer of ResumeIQ.

Performs:
  1. Skill extraction from resume text and job description text
  2. Skill gap analysis (matched vs missing vs bonus)
  3. Composite scoring (BM25 + skill_score)
  4. Per-skill impact estimation
  5. Actionable improvement suggestions
  6. What-if simulation: "if I add skill X, new score = ?"
"""

import re
from utils import preprocess_text

# ─────────────────────────────────────────────────────────────────────────────
#  Master skill taxonomy
#  Each entry: (canonical_name, [aliases...], weight, suggestion, learn_time)
#    weight      → relative importance for impact calc (1–3)
#    suggestion  → concrete action to add this skill to a resume
#    learn_time  → rough learning-time string shown to user
# ─────────────────────────────────────────────────────────────────────────────

_SKILL_DB = [
    # === Languages ===
    ("Python",        ["python", "py"],                                          3, "Add a Python project or mention frameworks (Django/Flask/FastAPI) in your experience section.", "already common — highlight projects"),
    ("Java",          ["java", "jvm"],                                           3, "Mention Java version (8/11/17) and any frameworks (Spring Boot, Maven) used.", "highlight existing or add a Spring Boot project"),
    ("JavaScript",    ["javascript", "js", "ecmascript"],                        3, "Showcase a frontend or Node.js project with modern JS (ES6+).", "highlight existing projects"),
    ("TypeScript",    ["typescript", "ts"],                                      2, "Migrate a JS project to TypeScript and mention strict typing experience.", "1–2 weeks"),
    ("Go",            ["golang", "go"],                                          2, "Build a REST API or CLI tool in Go and add it to your projects.", "3–4 weeks"),
    ("Rust",          ["rust"],                                                  2, "Build a systems-level project (e.g. CLI tool) in Rust.", "4–6 weeks"),
    ("C++",           ["c++", "cpp", "c plus plus"],                             2, "Highlight performance-critical projects or competitive programming.", "highlight existing"),
    ("Ruby",          ["ruby", "rails", "ruby on rails"],                        2, "Add a Rails API project or mention MVC experience.", "2–3 weeks"),
    ("PHP",           ["php", "laravel", "symfony"],                             2, "Mention Laravel/Symfony frameworks and a project URL.", "highlight existing"),
    ("Swift",         ["swift", "swiftui"],                                      2, "Publish or describe an iOS app in your projects section.", "4–6 weeks"),
    ("Kotlin",        ["kotlin"],                                                2, "Add an Android project or Kotlin-based Spring Boot app.", "2–3 weeks"),
    ("Scala",         ["scala", "spark scala"],                                  2, "Highlight Spark/Scala data pipeline work.", "3–4 weeks"),
    ("R",             ["r programming", "rstudio", "tidyverse", "ggplot"],       2, "Add an R-based data analysis or visualization project.", "2–3 weeks"),

    # === Web / Frontend ===
    ("React",         ["react", "react.js", "reactjs", "react native"],          3, "Build a React app with hooks, state management, and deploy it (Vercel/Netlify).", "3–4 weeks"),
    ("Angular",       ["angular", "angularjs"],                                  2, "Add an Angular project showcasing services and RxJS.", "3–4 weeks"),
    ("Vue",           ["vue", "vue.js", "vuejs", "nuxt"],                        2, "Build and deploy a Vue/Nuxt app; mention Vuex or Pinia.", "2–3 weeks"),
    ("Next.js",       ["next.js", "nextjs", "next js"],                          2, "Add a Next.js project with SSR/SSG and mention performance optimizations.", "1–2 weeks with React knowledge"),
    ("Node.js",       ["node.js", "nodejs", "node js", "express", "express.js"], 3, "Build a REST API with Node/Express and document it with Swagger.", "2–3 weeks"),
    ("HTML/CSS",      ["html", "html5", "css", "css3", "sass", "scss"],          2, "Mention responsive design projects and any CSS frameworks used.", "highlight existing"),
    ("Tailwind",      ["tailwind", "tailwindcss"],                               1, "Convert a project's styling to Tailwind and mention utility-first CSS.", "3–5 days"),

    # === Backend / API ===
    ("Django",        ["django", "django rest framework", "drf"],                2, "Add a Django REST API project with authentication and deployment.", "2–3 weeks"),
    ("Flask",         ["flask"],                                                  2, "Describe a Flask microservice project with API endpoints.", "1 week"),
    ("FastAPI",       ["fastapi", "fast api"],                                   2, "Add a FastAPI project with async endpoints and auto-generated docs.", "1 week"),
    ("REST API",      ["rest", "restful", "rest api", "http api"],               3, "Mention specific REST APIs you've built, including auth and versioning.", "highlight existing"),
    ("GraphQL",       ["graphql", "apollo"],                                     2, "Add a GraphQL API project or a client-side Apollo integration.", "2–3 weeks"),
    ("gRPC",          ["grpc"],                                                  1, "Build a microservice communicating over gRPC.", "2 weeks"),

    # === Databases ===
    ("SQL",           ["sql", "mysql", "postgresql", "postgres", "sqlite"],      3, "Showcase a project with complex queries, indexing, or schema design.", "highlight existing"),
    ("MongoDB",       ["mongodb", "mongo", "nosql"],                             2, "Add a MongoDB project mentioning aggregation pipelines and indexing.", "1–2 weeks"),
    ("Redis",         ["redis", "caching", "cache"],                             2, "Mention Redis usage for caching, sessions, or pub/sub in a project.", "1 week"),
    ("Elasticsearch", ["elasticsearch", "elastic", "kibana"],                   2, "Describe a search feature implemented with Elasticsearch.", "2 weeks"),
    ("Cassandra",     ["cassandra", "scylladb"],                                 1, "Add a wide-column store project or mention time-series data work.", "2–3 weeks"),
    ("PostgreSQL",    ["postgresql", "postgres", "psql"],                        2, "Highlight advanced PostgreSQL features: JSONB, full-text search, partitioning.", "highlight existing"),

    # === Cloud & DevOps ===
    ("AWS",           ["aws", "amazon web services", "ec2", "s3", "lambda", "rds", "cloudfront", "iam"], 3, "Get AWS Cloud Practitioner or Solutions Architect cert; add a cloud-deployed project.", "4–6 weeks for cert"),
    ("Azure",         ["azure", "microsoft azure", "azure devops"],              2, "Add an Azure-deployed project and mention services (AKS, Azure Functions).", "3–4 weeks"),
    ("GCP",           ["gcp", "google cloud", "google cloud platform", "bigquery"], 2, "Deploy a project on GCP and mention BigQuery or Cloud Run.", "3–4 weeks"),
    ("Docker",        ["docker", "containerization", "dockerfile", "container"], 3, "Containerize one of your projects and push to Docker Hub; add to GitHub.", "3–5 days"),
    ("Kubernetes",    ["kubernetes", "k8s", "kubectl", "helm", "eks", "aks", "gke"], 3, "Deploy a Dockerized app to Kubernetes (Minikube locally or a cloud cluster).", "2–3 weeks"),
    ("Terraform",     ["terraform", "iac", "infrastructure as code"],            2, "Write Terraform configs for an existing cloud project and add to repo.", "1–2 weeks"),
    ("CI/CD",         ["ci/cd", "cicd", "continuous integration", "continuous deployment", "jenkins", "gitlab ci", "github actions", "circleci"], 3, "Set up a GitHub Actions pipeline for lint + test + deploy on one of your projects.", "3–5 days"),
    ("Linux",         ["linux", "unix", "bash", "shell", "shell scripting", "bash scripting"], 2, "Add automation scripts you've written; mention distros and admin experience.", "highlight existing"),
    ("Ansible",       ["ansible", "configuration management"],                  1, "Write Ansible playbooks to provision a VM and document in README.", "1–2 weeks"),

    # === ML / AI / Data ===
    ("Machine Learning", ["machine learning", "ml", "supervised learning", "unsupervised learning"], 3, "Add an end-to-end ML project (data → model → evaluation) to GitHub.", "4–8 weeks"),
    ("Deep Learning", ["deep learning", "neural network", "neural networks", "dl"], 2, "Build and train a neural network (image/text classification) and document it.", "4–6 weeks"),
    ("TensorFlow",    ["tensorflow", "tf", "keras"],                             2, "Add a TensorFlow/Keras project with model training and evaluation metrics.", "2–3 weeks"),
    ("PyTorch",       ["pytorch", "torch"],                                      2, "Implement a model in PyTorch and share training/evaluation notebooks.", "2–3 weeks"),
    ("scikit-learn",  ["scikit-learn", "sklearn", "scikit learn"],               2, "Showcase a classification/regression project with cross-validation and metrics.", "1–2 weeks"),
    ("NLP",           ["nlp", "natural language processing", "text mining", "bert", "gpt", "transformers", "hugging face", "huggingface"], 3, "Add an NLP project (sentiment, classification, summarization) using HuggingFace.", "3–4 weeks"),
    ("Data Science",  ["data science", "data analysis", "pandas", "numpy", "matplotlib", "seaborn", "jupyter"], 2, "Add a Jupyter notebook project with EDA, visualizations, and insights.", "2–3 weeks"),
    ("MLOps",         ["mlops", "model deployment", "model monitoring", "mlflow", "kubeflow"], 2, "Deploy a model as a REST API and add monitoring; mention MLflow or similar.", "2–3 weeks"),
    ("LLM",           ["llm", "large language model", "openai", "langchain", "chatgpt", "gpt-4", "claude"], 2, "Build a small LLM-powered app (chatbot, summarizer) and deploy it.", "2–3 weeks"),

    # === Tools / Practices ===
    ("Git",           ["git", "github", "gitlab", "bitbucket", "version control"], 3, "Ensure your GitHub has active public repos; mention branching strategies used.", "highlight existing"),
    ("Agile/Scrum",   ["agile", "scrum", "kanban", "sprint", "jira", "confluence"], 2, "Mention specific sprint ceremonies, story-pointing, or velocity metrics.", "highlight existing"),
    ("Microservices", ["microservices", "microservice", "service mesh", "istio"], 2, "Describe a microservices project architecture: services, communication, deployment.", "highlight existing"),
    ("Testing",       ["testing", "unit testing", "pytest", "jest", "selenium", "tdd", "bdd", "qa"], 2, "Add test coverage metrics to a project README; mention frameworks and coverage %.", "highlight existing"),
    ("Security",      ["security", "owasp", "penetration testing", "pentest", "siem", "vulnerability", "cissp", "ceh"], 2, "Mention security audits, OWASP practices, or certifications achieved.", "highlight existing"),
    ("Figma",         ["figma", "sketch", "adobe xd", "ui design", "ux design", "wireframing", "prototyping"], 2, "Add a Figma portfolio link; include case studies with before/after.", "highlight existing"),
    ("Product Management", ["product management", "product manager", "roadmap", "stakeholder", "okr", "kpi"], 2, "Quantify impact: 'launched X feature used by Y users, resulting in Z% improvement'.", "highlight existing"),
]

# Build fast lookup: lowercase alias → (canonical, weight, suggestion, learn_time)
_ALIAS_MAP: dict = {}
for entry in _SKILL_DB:
    canonical, aliases, weight, suggestion, learn_time = entry
    for alias in aliases:
        _ALIAS_MAP[alias.lower()] = (canonical, weight, suggestion, learn_time)


def extract_skills(text: str) -> dict[str, tuple]:
    """
    Extract known skills from text.
    Returns {canonical_name: (weight, suggestion, learn_time)}
    """
    text_lower = text.lower()
    found: dict[str, tuple] = {}

    for alias, (canonical, weight, suggestion, learn_time) in _ALIAS_MAP.items():
        # Word-boundary match — avoids 'r' matching 'error', etc.
        pattern = r'(?<![a-z0-9])' + re.escape(alias) + r'(?![a-z0-9])'
        if re.search(pattern, text_lower):
            if canonical not in found:
                found[canonical] = (weight, suggestion, learn_time)
    return found


def compute_skill_score(resume_skills: dict, job_skills: dict) -> float:
    """
    Weighted skill match score: 0.0 – 1.0
    Uses job skill weights as denominators so high-weight skills matter more.
    """
    if not job_skills:
        return 0.0
    total_weight = sum(w for w, _, _ in job_skills.values())
    if total_weight == 0:
        return 0.0
    matched_weight = sum(
        job_skills[s][0] for s in resume_skills if s in job_skills
    )
    return round(min(matched_weight / total_weight, 1.0), 4)


def compute_composite_score(bm25_score: float, skill_score: float, bm25_max: float) -> float:
    """
    Weighted composite:  60% BM25 (normalised) + 40% skill match
    Returns percentage 0–100.
    """
    bm25_norm = min(bm25_score / bm25_max, 1.0) if bm25_max > 0 else 0.0
    raw = 0.60 * bm25_norm + 0.40 * skill_score
    return round(raw * 100, 1)


def estimate_skill_impact(missing_skills: dict, current_skill_score: float, job_skills: dict) -> list[dict]:
    """
    For each missing skill, estimate how much the composite score would
    increase if the candidate added it.
    Returns list sorted by impact descending.
    """
    total_weight = sum(w for w, _, _ in job_skills.values()) if job_skills else 1
    results = []

    for skill, (weight, suggestion, learn_time) in missing_skills.items():
        # Skill-score delta if this skill is added
        delta_skill = weight / total_weight if total_weight > 0 else 0
        # Composite impact: only the 40% skill component changes
        impact_pct = round(delta_skill * 40, 1)   # max contribution is 40 pts
        results.append({
            "skill": skill,
            "impact": impact_pct,
            "weight": weight,
            "suggestion": suggestion,
            "learn_time": learn_time,
        })

    results.sort(key=lambda x: x["impact"], reverse=True)
    return results


def simulate_whatif(
    resume_skills: dict,
    added_skills: list[str],
    job_skills: dict,
    bm25_score: float,
    bm25_max: float,
) -> dict:
    """
    Simulate 'what if I add these skills?'
    Returns new composite score and new skill score.
    """
    simulated = dict(resume_skills)
    for skill_name in added_skills:
        if skill_name in job_skills and skill_name not in simulated:
            simulated[skill_name] = job_skills[skill_name]

    new_skill_score = compute_skill_score(simulated, job_skills)
    new_composite = compute_composite_score(bm25_score, new_skill_score, bm25_max)
    return {
        "new_skill_score": new_skill_score,
        "new_composite_score": new_composite,
        "skills_added": [s for s in added_skills if s in job_skills],
    }


def full_analysis(
    resume_text: str,
    job_text: str,
    bm25_score: float,
    bm25_max: float,
    resume_id: str = "",
) -> dict:
    """
    Run the full feedback pipeline for a single resume against a job.

    Returns a rich analysis dict consumed by the frontend.
    """
    resume_skills = extract_skills(resume_text)
    job_skills    = extract_skills(job_text)

    matched_skills  = {s: v for s, v in resume_skills.items() if s in job_skills}
    missing_skills  = {s: v for s, v in job_skills.items()    if s not in resume_skills}
    bonus_skills    = {s: v for s, v in resume_skills.items() if s not in job_skills}

    skill_score     = compute_skill_score(resume_skills, job_skills)
    composite_score = compute_composite_score(bm25_score, skill_score, bm25_max)

    impact_list = estimate_skill_impact(missing_skills, skill_score, job_skills)

    # Label: Excellent / Good / Fair / Low
    if composite_score >= 75:
        fit_label, fit_color = "Excellent Fit", "green"
    elif composite_score >= 55:
        fit_label, fit_color = "Good Fit", "amber"
    elif composite_score >= 35:
        fit_label, fit_color = "Fair Fit", "orange"
    else:
        fit_label, fit_color = "Low Fit", "red"

    return {
        "id":              resume_id,
        "bm25_score":      round(bm25_score, 4),
        "skill_score":     round(skill_score * 100, 1),     # as %
        "composite_score": composite_score,                  # 0–100
        "fit_label":       fit_label,
        "fit_color":       fit_color,
        "matched_skills":  sorted(matched_skills.keys()),
        "missing_skills":  sorted(missing_skills.keys()),
        "bonus_skills":    sorted(bonus_skills.keys()),
        "impact_list":     impact_list,                      # sorted by impact
        "job_skills_found": sorted(job_skills.keys()),
    }