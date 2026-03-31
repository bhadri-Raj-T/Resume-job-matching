"""
services/scoring_service.py
────────────────────────────
Pure scoring functions for the INDIVIDUAL FLOW.
All scores are bounded [0.0, 1.0]. No BM25 anywhere.
"""

import re
import math
import logging

logger = logging.getLogger(__name__)

WEIGHT_SEMANTIC   = 0.50
WEIGHT_SKILL      = 0.30
WEIGHT_EXPERIENCE = 0.10
WEIGHT_EDUCATION  = 0.10

_EDU_TIERS = {
    "phd": 5, "ph.d": 5, "doctorate": 5, "doctoral": 5,
    "master": 4, "msc": 4, "mba": 4, "m.s": 4,
    "bachelor": 3, "bsc": 3, "b.s": 3, "b.e": 3, "undergraduate": 3,
    "associate": 2, "diploma": 2,
    "bootcamp": 1, "certification": 1, "course": 1,
}

_YEAR_PATTERN = re.compile(
    r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)?',
    re.IGNORECASE
)
_DATE_RANGE_PATTERN = re.compile(
    r'\b(20\d{2}|19\d{2})\s*[-–]\s*(20\d{2}|19\d{2}|present|current)\b',
    re.IGNORECASE
)


def skill_score(resume_skills: dict, job_skills: dict) -> float:
    """Weighted skill overlap. Returns 0.0–1.0."""
    if not job_skills:
        return 0.0
    total_weight = sum(v[0] for v in job_skills.values())
    if total_weight == 0:
        return 0.0
    matched_weight = sum(
        job_skills[s][0] for s in resume_skills if s in job_skills
    )
    return round(min(max(matched_weight / total_weight, 0.0), 1.0), 4)


def _extract_years(text: str) -> int:
    matches = _YEAR_PATTERN.findall(text)
    if matches:
        return max(int(m) for m in matches)
    date_ranges = _DATE_RANGE_PATTERN.findall(text)
    if date_ranges:
        years_set = set()
        for start, end in date_ranges:
            try:
                s = int(start)
                e = 2024 if end.lower() in ('present', 'current') else int(end)
                years_set.update(range(s, e + 1))
            except ValueError:
                pass
        return max(len(years_set), 1)
    return 0


def experience_score(resume_text: str, job_text: str) -> float:
    """Years-of-experience ratio. Returns 0.0–1.0."""
    job_years    = _extract_years(job_text)
    resume_years = _extract_years(resume_text)

    if job_years == 0:
        if resume_years >= 3:  return 1.0
        if resume_years >= 1:  return 0.7
        return 0.5

    if resume_years == 0:
        senior_terms = ['senior','lead','principal','staff','head','director','manager']
        if any(t in resume_text.lower() for t in senior_terms):
            return 0.75
        return 0.4

    ratio = resume_years / job_years
    return round(min(ratio, 1.0), 4)


def _edu_tier(text: str) -> int:
    text_lower = text.lower()
    highest = 0
    for keyword, tier in _EDU_TIERS.items():
        if keyword in text_lower:
            highest = max(highest, tier)
    return highest


def education_score(resume_text: str, job_text: str) -> float:
    """Education tier comparison. Returns 0.0–1.0."""
    resume_tier = _edu_tier(resume_text)
    job_tier    = _edu_tier(job_text)

    if job_tier == 0:
        if resume_tier >= 3:  return 0.9
        if resume_tier >= 1:  return 0.7
        return 0.6

    if resume_tier >= job_tier:      return 1.0
    if resume_tier == job_tier - 1:  return 0.7
    return max(0.3, resume_tier / job_tier)


def final_score(semantic: float, skill: float, exp: float, edu: float) -> float:
    """
    Weighted composite → 0.0–100.0 percentage.
    Guaranteed non-negative and clamped at 100.
    """
    s  = min(max(float(semantic), 0.0), 1.0)
    sk = min(max(float(skill),    0.0), 1.0)
    e  = min(max(float(exp),      0.0), 1.0)
    ed = min(max(float(edu),      0.0), 1.0)

    raw = (WEIGHT_SEMANTIC   * s  +
           WEIGHT_SKILL      * sk +
           WEIGHT_EXPERIENCE * e  +
           WEIGHT_EDUCATION  * ed)

    return round(min(max(raw, 0.0), 1.0) * 100, 1)


def compute_whatif_score(
    resume_skills: dict,
    added_skills: list,
    job_skills: dict,
    current_semantic: float,
    current_exp: float,
    current_edu: float,
) -> dict:
    """
    What-if simulation. Only skill_score changes.
    All returned scores are guaranteed >= 0.
    """
    current_skill = skill_score(resume_skills, job_skills)
    current_total = final_score(current_semantic, current_skill, current_exp, current_edu)

    simulated = dict(resume_skills)
    skills_effective = []
    for skill_name in added_skills:
        if skill_name in job_skills and skill_name not in simulated:
            simulated[skill_name] = job_skills[skill_name]
            skills_effective.append(skill_name)

    new_skill = skill_score(simulated, job_skills)
    new_total = final_score(current_semantic, new_skill, current_exp, current_edu)
    delta     = round(new_total - current_total, 1)

    return {
        "current_score":    round(current_total, 1),
        "simulated_score":  round(new_total, 1),
        "delta":            max(delta, 0.0),
        "new_skill_score":  round(new_skill, 4),
        "skills_effective": skills_effective,
        "skills_not_in_jd": [s for s in added_skills if s not in job_skills],
    }