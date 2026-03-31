"""
services/embedding_service.py
──────────────────────────────
Semantic similarity using Groq Python SDK.

Priority:
  1. Groq (llama-3.3-70b-versatile) → AI semantic score   ← PRIMARY
  2. TF-IDF cosine fallback (if no key / package missing)

Install: pip install groq
Set key:  GROQ_API_KEY = "gsk_xxxx..."  on line 22 below
"""

import os
import re
import math
import json
import logging

logger = logging.getLogger(__name__)

# ── ✅ PUT YOUR GROQ API KEY HERE ─────────────────────────────────────────────
GROQ_API_KEY = "Your api key"  # ← replace with gsk_xxxx
# ─────────────────────────────────────────────────────────────────────────────

# Allow env var to override
_GROQ_KEY = os.getenv("GROQ_API_KEY", GROQ_API_KEY).strip()

try:
    from groq import Groq as _GroqClient
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False
    logger.warning("groq package not installed — run: pip install groq")


# ─────────────────────────────────────────────────────────────────────────────
#  TF-IDF fallback (zero dependencies)
# ─────────────────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list:
    tokens = re.findall(r'[a-z0-9]+', text.lower())
    stopwords = {'the','a','an','in','on','at','to','for','of','and','or',
                 'is','are','was','were','be','been','with','that','this',
                 'it','as','by','from','have'}
    return [t for t in tokens if len(t) > 1 and t not in stopwords]


def get_tfidf_similarity(text1: str, text2: str) -> float:
    """Offline cosine similarity using TF-IDF. Returns 0.0-1.0."""
    tokens1 = _tokenize(text1)
    tokens2 = _tokenize(text2)
    if not tokens1 or not tokens2:
        return 0.0

    vocab = set(tokens1) | set(tokens2)

    def tf_vector(tokens):
        count = {}
        for t in tokens:
            count[t] = count.get(t, 0) + 1
        total = len(tokens)
        return {t: c / total for t, c in count.items()}

    tf1 = tf_vector(tokens1)
    tf2 = tf_vector(tokens2)

    idf = {}
    for term in vocab:
        df = (term in tf1) + (term in tf2)
        idf[term] = math.log((2 + 1) / (df + 1)) + 1

    dot = norm1 = norm2 = 0.0
    for term in vocab:
        v1 = tf1.get(term, 0.0) * idf[term]
        v2 = tf2.get(term, 0.0) * idf[term]
        dot   += v1 * v2
        norm1 += v1 * v1
        norm2 += v2 * v2

    if norm1 == 0 or norm2 == 0:
        return 0.0
    return round(min(max(math.sqrt(dot * dot / (norm1 * norm2)), 0.0), 1.0), 4)


# ─────────────────────────────────────────────────────────────────────────────
#  Groq semantic scoring  (uses groq Python SDK with streaming)
# ─────────────────────────────────────────────────────────────────────────────

def _groq_semantic_score(resume_text: str, job_text: str):
    """
    Use Groq to score semantic similarity between a resume and a JD.
    Returns float 0.0-1.0, or None if unavailable/failed.
    """
    if not _GROQ_AVAILABLE:
        return None
    if not _GROQ_KEY or _GROQ_KEY == "your-groq-api-key-here":
        return None

    try:
        client = _GroqClient(api_key=_GROQ_KEY)

        prompt = f"""You are a professional resume evaluator.
Score the semantic relevance between the RESUME and the JOB DESCRIPTION.

Output ONLY a JSON object exactly like this (no extra text, no markdown):
{{"score": 0.75, "reason": "one sentence"}}

Score guide:
0.90-1.00 = Excellent match (almost all required skills and context present)
0.70-0.89 = Good match (most skills present, minor gaps)
0.50-0.69 = Fair match (some skills present, notable gaps)
0.20-0.49 = Weak match (few required skills)
0.00-0.19 = Poor match (wrong domain entirely)

--- JOB DESCRIPTION (first 1500 chars) ---
{job_text[:1500]}

--- RESUME (first 1500 chars) ---
{resume_text[:1500]}"""

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a resume scoring expert. Respond only with valid JSON."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.1,
            max_completion_tokens=120,
            top_p=1,
            stream=True,
            stop=None,
        )

        # Collect streamed chunks
        response_text = ""
        for chunk in completion:
            response_text += chunk.choices[0].delta.content or ""

        # Strip markdown fences if model added them
        response_text = re.sub(r"```json\s*", "", response_text).strip()
        response_text = re.sub(r"```\s*",     "", response_text).strip()

        parsed = json.loads(response_text)
        score  = float(parsed.get("score", 0.5))
        reason = parsed.get("reason", "")
        logger.info(f"Groq semantic score: {score:.2f} - {reason}")
        return round(min(max(score, 0.0), 1.0), 4)

    except Exception as e:
        logger.warning(f"Groq semantic score failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def get_similarity(text1: str, text2: str) -> float:
    """
    Returns semantic similarity 0.0-1.0.
    Uses Groq if key is set, otherwise falls back to TF-IDF.
    """
    score = _groq_semantic_score(text1, text2)
    if score is not None:
        return score

    logger.debug("Falling back to TF-IDF similarity (Groq unavailable or key not set)")
    return get_tfidf_similarity(text1, text2)


# Kept for backward compatibility
def get_embedding(text: str):
    return None