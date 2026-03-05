# utils.py
"""
Text preprocessing for BM25 indexing and querying.
"""

import re
import nltk

# Download required NLTK data silently if not already present
for _pkg in ("punkt", "punkt_tab", "stopwords"):
    try:
        nltk.data.find(f"tokenizers/{_pkg}" if "punkt" in _pkg else f"corpora/{_pkg}")
    except LookupError:
        nltk.download(_pkg, quiet=True)

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

_STOP_WORDS = set(stopwords.words("english"))

# Tech-domain words that should never be treated as stop words
_PRESERVE = {
    "python", "java", "sql", "aws", "gcp", "api", "ml", "ai",
    "nlp", "css", "git", "ios", "r"
}


def preprocess_text(text: str) -> list:
    """
    Lowercase, strip punctuation, tokenize, remove stop words and short tokens.
    Returns a list of meaningful tokens.
    """
    if not text:
        return []

    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    tokens = word_tokenize(text)

    result = []
    for word in tokens:
        if word in _PRESERVE:
            result.append(word)
        elif word not in _STOP_WORDS and len(word) > 2:
            result.append(word)

    return result