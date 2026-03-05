import os
import json
import fitz  # PyMuPDF
from difflib import SequenceMatcher

# -------- CONFIG --------
MIN_FONT_SIZE = 6        # Below this is suspicious
SIMILARITY_THRESHOLD = 0.90

# -------- LOAD JOB DESCRIPTIONS --------
def load_jobs(jobs_path):
    with open(jobs_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# -------- TEXT SIMILARITY --------
def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

# -------- VALIDATE SINGLE RESUME --------
def validate_resume(resume_path, jobs_data):
    doc = fitz.open(resume_path)
    full_text = ""
    issues = []

    for page in doc:
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue

            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    font_size = span["size"]
                    color = span["color"]  # RGB integer

                    full_text += text + " "

                    # 1️⃣ Detect Very Small Font
                    if font_size < MIN_FONT_SIZE and len(text) > 20:
                        issues.append("Very small font detected")

                    # 2️⃣ Detect White/Invisible Text
                    # white color = 16777215
                    if color == 16777215:
                        issues.append("Invisible/white colored text detected")

    doc.close()

    # 3️⃣ Detect Job Description Copy
    for job in jobs_data:
        job_text = job["text"]
        sim = similarity(full_text.lower(), job_text.lower())
        if sim > SIMILARITY_THRESHOLD:
            issues.append(f"Copied job description from job id {job['id']}")
            break

    if not full_text.strip():
        issues.append("No extractable text (possibly scanned PDF)")

    return list(set(issues))  # remove duplicates

# -------- VALIDATE ALL RESUMES --------
def validate_all_resumes(resume_folder, jobs_path):
    jobs_data = load_jobs(jobs_path)

    results = {}

    for file in os.listdir(resume_folder):
        if file.endswith(".pdf"):
            path = os.path.join(resume_folder, file)
            issues = validate_resume(path, jobs_data)

            if issues:
                results[file] = {
                    "status": "BLACKLISTED",
                    "issues": issues
                }
            else:
                results[file] = {
                    "status": "CLEAN",
                    "issues": []
                }

    return results


# -------- RUN DIRECTLY --------
if __name__ == "__main__":
    resume_folder = "backend/data/resumes"
    jobs_path = "backend/data/jobs/jobs.json"

    report = validate_all_resumes(resume_folder, jobs_path)

    with open("backend/data/blacklist_report.json", "w") as f:
        json.dump(report, f, indent=4)

    print("Validation complete. Report saved to blacklist_report.json")