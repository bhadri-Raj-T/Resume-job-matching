# utils.py
"""
Text preprocessing for BM25 indexing and querying.

FIX (db_matcher_ready: false on Render):
  Root cause: nltk.download() was called at import time with quiet=True.
  On Render free tier the download silently fails (or downloads to a path
  not searched by nltk.data.find). The very next line then calls
  stopwords.words("english") at MODULE LEVEL — which raises LookupError.
  That exception propagates all the way up through matcher -> bm25_engine ->
  app._rebuild_db_matcher(), which catches it and leaves db_matcher = None.

  Fix 1: Hardcoded fallback stopword list — no network download required.
          NLTK stopwords are still used when available (better coverage),
          but the module never crashes if NLTK data is missing.

  Fix 2: word_tokenize falls back to simple regex split if punkt is absent,
          so the module is fully self-contained even with zero NLTK data.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── NLTK — load opportunistically, never crash ────────────────────────────────

_nltk_tokenize = None   # set to word_tokenize if available
_nltk_stopwords = None  # set to frozenset if available

try:
    import nltk

    # Attempt downloads silently; failures are non-fatal
    for _pkg, _path in [
        ("punkt",     "tokenizers/punkt"),
        ("punkt_tab", "tokenizers/punkt_tab"),
        ("stopwords", "corpora/stopwords"),
    ]:
        try:
            nltk.data.find(_path)
        except LookupError:
            try:
                nltk.download(_pkg, quiet=True)
            except Exception:
                pass  # network blocked on Render free tier — that's OK

    # Try to load word_tokenize
    try:
        from nltk.tokenize import word_tokenize
        word_tokenize("test sentence")   # smoke-test: confirm punkt data usable
        _nltk_tokenize = word_tokenize
        logger.debug("NLTK word_tokenize available")
    except Exception as e:
        logger.warning(f"NLTK tokenizer not available ({e}), using regex fallback")

    # Try to load stopwords
    try:
        from nltk.corpus import stopwords as _sw_corpus
        _nltk_stopwords = frozenset(_sw_corpus.words("english"))
        logger.debug(f"NLTK stopwords loaded ({len(_nltk_stopwords)} words)")
    except Exception as e:
        logger.warning(f"NLTK stopwords not available ({e}), using built-in fallback")

except ImportError:
    logger.warning("nltk not installed — using built-in fallbacks")


# ── Built-in fallback stopword list (matches NLTK english stopwords) ──────────
# Makes the module self-contained: zero network dependency at runtime.
_BUILTIN_STOPWORDS = frozenset({
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you",
    "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself",
    "she", "her", "hers", "herself", "it", "its", "itself", "they", "them",
    "their", "theirs", "themselves", "what", "which", "who", "whom", "this",
    "that", "these", "those", "am", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "having", "do", "does", "did", "doing",
    "a", "an", "the", "and", "but", "if", "or", "because", "as", "until",
    "while", "of", "at", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below", "to",
    "from", "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why", "how",
    "all", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "s", "t", "can", "will", "just", "don", "should", "now", "d", "ll", "m",
    "o", "re", "ve", "y", "ain", "aren", "couldn", "didn", "doesn", "hadn",
    "hasn", "haven", "isn", "ma", "mightn", "mustn", "needn", "shan",
    "shouldn", "wasn", "weren", "won", "wouldn",
})

_STOP_WORDS = _nltk_stopwords if _nltk_stopwords is not None else _BUILTIN_STOPWORDS

# Tech-domain words that should never be treated as stop words
_PRESERVE = {
    "python", "java", "sql", "aws", "gcp", "api", "ml", "ai",
    "nlp", "css", "git", "ios", "r"
}


# ── Tokenizer ─────────────────────────────────────────────────────────────────

def _regex_tokenize(text: str) -> list:
    """Simple whitespace + punctuation tokenizer — no NLTK required."""
    return re.findall(r"[a-z0-9]+", text)


def preprocess_text(text: str) -> list:
    """
    Lowercase, strip punctuation, tokenize, remove stop words and short tokens.
    Returns a list of meaningful tokens.

    Uses NLTK word_tokenize when available; falls back to regex split otherwise.
    Uses NLTK stopwords when available; falls back to built-in list otherwise.
    Never raises — safe to call even with zero NLTK data installed.
    """
    if not text:
        return []

    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if _nltk_tokenize is not None:
        try:
            tokens = _nltk_tokenize(text)
        except Exception:
            tokens = _regex_tokenize(text)
    else:
        tokens = _regex_tokenize(text)

    result = []
    for word in tokens:
        if word in _PRESERVE:
            result.append(word)
        elif word not in _STOP_WORDS and len(word) > 2:
            result.append(word)

    return result
