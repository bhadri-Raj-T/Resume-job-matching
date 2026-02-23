# main.py
from parser import extract_resume_text
from matcher import ResumeMatcher
import os
import json

# ---- Load Resumes ----
resumes = []
resume_folder = "backend/data/resumes"

for file in os.listdir(resume_folder):
    path = os.path.join(resume_folder, file)
    text = extract_resume_text(path)
    resumes.append({
        "id": file,
        "text": text
    })

# ---- Load Jobs ----
with open("backend/data/jobs/jobs.json", "r") as f:
    jobs = json.load(f)

for r in resumes:
    print(r["id"], len(r["text"]))

# ---- Initialize Matcher ----
matcher = ResumeMatcher(resumes, jobs)

# ---- Example: Job → Candidates ----
job_description = jobs[0]["text"]

results = matcher.match_job_to_candidates(job_description, top_k=3)

print("\nTop Candidates:\n")
for r in results:
    print(r)

# ---- Example2: Job → Candidates ----
job_description = jobs[1]["text"]

results = matcher.match_job_to_candidates(job_description, top_k=3)

print("\nTop Candidates:\n")
for r in results:
    print(r)