"""
services/embedding_service.py
──────────────────────────────
Semantic similarity using OpenAI text-embedding-3-small.
Falls back to TF-IDF cosine similarity if no API key.
"""

import os
import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False
    logger.warning("openai package not installed — falling back to TF-IDF similarity.")

_client = None

def _get_client():
    global _client
    if _client is None and _OPENAI_AVAILABLE:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            _client = OpenAI(api_key=api_key)
    return _client


def _tokenize(text: str) -> list:
    import re
    tokens = re.findall(r'[a-z0-9]+', text.lower())
    stopwords = {'the','a','an','in','on','at','to','for','of','and','or',
                 'is','are','was','were','be','been','with','that','this',
                 'it','as','by','from','have'}
    return [t for t in tokens if len(t) > 1 and t not in stopwords]


def get_tfidf_similarity(text1: str, text2: str) -> float:
    """Offline cosine similarity using TF-IDF. Returns 0.0–1.0."""
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
        dot  += v1 * v2
        norm1 += v1 * v1
        norm2 += v2 * v2

    if norm1 == 0 or norm2 == 0:
        return 0.0
    return round(min(max(math.sqrt(dot * dot / (norm1 * norm2)), 0.0), 1.0), 4)


def get_embedding(text: str):
    client = _get_client()
    if client is None:
        return None
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:12000],
        )
        return response.data[0].embedding
    except Exception as e:
        logger.warning(f"OpenAI embedding failed: {e}")
        return None


def _cosine(vec1: list, vec2: list) -> float:
    dot  = sum(a * b for a, b in zip(vec1, vec2))
    n1   = math.sqrt(sum(a * a for a in vec1))
    n2   = math.sqrt(sum(b * b for b in vec2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def get_similarity(text1: str, text2: str) -> float:
    """
    Semantic similarity between two texts. Returns 0.0–1.0.
    Uses OpenAI embeddings if API key is set, otherwise TF-IDF.
    """
    emb1 = get_embedding(text1)
    emb2 = get_embedding(text2)
    if emb1 is not None and emb2 is not None:
        raw = _cosine(emb1, emb2)
        normalised = (raw - 0.5) / 0.5
        return round(min(max(normalised, 0.0), 1.0), 4)
    logger.debug("Using TF-IDF fallback for similarity")
    return get_tfidf_similarity(text1, text2)