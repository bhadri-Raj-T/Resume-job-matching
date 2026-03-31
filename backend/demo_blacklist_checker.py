import os
import json
import fitz  # PyMuPDF
from difflib import SequenceMatcher

RESUME_FOLDER = "backend/data/resumes"
JOBS_PATH = "backend/data/jobs/jobs.json"

MIN_FONT_SIZE = 6
SIMILARITY_THRESHOLD = 0.90


def load_jobs():
    with open(JOBS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def check_resume(resume_path, jobs_data):
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
                    color = span["color"]

                    full_text += text + " "

                    # 1️⃣ Small Font Detection
                    if font_size < MIN_FONT_SIZE and len(text) > 20:
                        issues.append("Very small hidden text detected")

                    # 2️⃣ White Text Detection
                    if color == 16777215:
                        issues.append("Invisible white text detected")

    doc.close()

    # 3️⃣ Job Description Copy Detection
    for job in jobs_data:
        job_text = job["text"]
        sim = similarity(full_text.lower(), job_text.lower())
        if sim > SIMILARITY_THRESHOLD:
            issues.append(f"Copied job description (Job ID: {job['id']})")
            break

    if not full_text.strip():
        issues.append("No readable text (Scanned PDF)")

    return list(set(issues))


def run_demo():
    jobs_data = load_jobs()
    report = {}

    print("\n==============================")
    print(" BLACKLIST DETECTION DEMO ")
    print("==============================\n")

    for file in os.listdir(RESUME_FOLDER):
        if file.endswith(".pdf"):
            path = os.path.join(RESUME_FOLDER, file)
            issues = check_resume(path, jobs_data)

            print(f"Checking: {file}")

            if issues:
                print("  ❌ BLACKLISTED")
                for issue in issues:
                    print("     -", issue)
                report[file] = {"status": "BLACKLISTED", "issues": issues}
            else:
                print("  ✅ CLEAN")
                report[file] = {"status": "CLEAN", "issues": []}

            print()

    # Save report for demo
    with open("backend/demo_blacklist_report.json", "w") as f:
        json.dump(report, f, indent=4)

    print("Demo report saved to demo_blacklist_report.json")


if __name__ == "__main__":
    run_demo()