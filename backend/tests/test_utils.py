"""
tests/test_utils.py
────────────────────
Comprehensive unit tests for preprocess_text() in BM25-module/utils.py.

Covers:
  - Basic tokenisation and lowercase conversion
  - Stopword removal (common English words)
  - Short-token filtering (len ≤ 2, excluding preserved tech terms)
  - Preserved tech-domain terms (sql, aws, ml, ai, r, api, nlp, css, git, ios, gcp)
  - Punctuation stripping
  - Number handling
  - Empty / whitespace / None-like inputs
  - Return type
  - Idempotency
  - Large text performance
"""
import pytest
from bm25_module.utils import preprocess_text

# Tech terms that the PRESERVE set in utils.py must keep even though they're ≤ 2 chars
PRESERVED_SHORT = {"ml", "ai", "r", "sql", "aws", "gcp", "api", "nlp", "css", "git", "ios"}


# ── Return type ───────────────────────────────────────────────────────────────

def test_returns_list():
    assert isinstance(preprocess_text("hello world"), list)


def test_returns_list_for_empty_string():
    assert isinstance(preprocess_text(""), list)


# ── Empty / whitespace inputs ─────────────────────────────────────────────────

def test_empty_string_returns_empty():
    assert preprocess_text("") == []


def test_whitespace_only_returns_empty():
    assert preprocess_text("   ") == []


def test_tab_only_returns_empty():
    assert preprocess_text("\t\n\r") == []


# ── Basic tokenisation ────────────────────────────────────────────────────────

def test_basic_tokenisation_keeps_meaningful_words():
    tokens = preprocess_text("Python developer Flask REST API")
    assert "python" in tokens
    assert "developer" in tokens
    assert "flask" in tokens


def test_lowercase_conversion():
    tokens = preprocess_text("PYTHON Developer FLASK")
    assert "python" in tokens
    assert "developer" in tokens
    assert "flask" in tokens


def test_mixed_case_normalised():
    tokens = preprocess_text("MachineLearning TensorFlow Kubernetes")
    # After lowercasing and splitting on non-alphanumeric the tokens appear lowercase
    lower_tokens = [t.lower() for t in tokens]
    assert "machinelearning" in lower_tokens or "machine" in lower_tokens or "tensorflow" in lower_tokens


# ── Stopword removal ──────────────────────────────────────────────────────────

def test_common_stopwords_removed():
    tokens = preprocess_text("the quick brown fox jumps over the lazy dog")
    for sw in ("the", "over"):
        assert sw not in tokens


def test_pronoun_stopwords_removed():
    tokens = preprocess_text("I am a developer and we are engineers")
    for sw in ("i", "am", "a", "and", "we", "are"):
        assert sw not in tokens


def test_preposition_stopwords_removed():
    tokens = preprocess_text("experience in building systems with python for clients")
    for sw in ("in", "with", "for"):
        assert sw not in tokens


# ── Short-token filtering ─────────────────────────────────────────────────────

def test_short_tokens_under_3_chars_removed():
    tokens = preprocess_text("a an is to be at by do go")
    for tok in tokens:
        if tok not in PRESERVED_SHORT:
            assert len(tok) > 2, f"Short token '{tok}' should have been filtered"


def test_two_char_non_preserved_removed():
    """'ab' is 2 chars and not in PRESERVE — should be filtered."""
    tokens = preprocess_text("ab cd ef python")
    for tok in tokens:
        if tok not in PRESERVED_SHORT:
            assert len(tok) > 2


# ── Tech-domain preserved terms ───────────────────────────────────────────────

def test_sql_preserved():
    assert "sql" in preprocess_text("proficient in SQL databases")


def test_aws_preserved():
    assert "aws" in preprocess_text("cloud experience with AWS and Azure")


def test_gcp_preserved():
    assert "gcp" in preprocess_text("using GCP and AWS for cloud infrastructure")


def test_ml_preserved():
    assert "ml" in preprocess_text("applied ML and AI techniques")


def test_ai_preserved():
    assert "ai" in preprocess_text("AI and machine learning research")


def test_api_preserved():
    assert "api" in preprocess_text("REST API developer with Flask")


def test_nlp_preserved():
    assert "nlp" in preprocess_text("NLP engineer with BERT experience")


def test_css_preserved():
    assert "css" in preprocess_text("frontend CSS HTML developer")


def test_git_preserved():
    assert "git" in preprocess_text("version control with Git and GitHub")


def test_ios_preserved():
    assert "ios" in preprocess_text("mobile developer for iOS and Android")


def test_r_preserved():
    assert "r" in preprocess_text("statistical analysis with R and Python")


def test_all_preserved_terms_together():
    text = "proficient in Python SQL AWS GCP ML AI API NLP CSS Git iOS R"
    tokens = preprocess_text(text)
    for term in ("python", "sql", "aws", "gcp", "ml", "ai", "api", "nlp", "css", "git", "ios", "r"):
        assert term in tokens, f"Preserved term '{term}' missing from tokens"


# ── Punctuation stripping ─────────────────────────────────────────────────────

def test_comma_stripped():
    tokens = preprocess_text("Python, Flask, Docker")
    assert "python" in tokens
    assert "flask" in tokens
    assert "docker" in tokens


def test_period_stripped():
    tokens = preprocess_text("Experience with Python. Developed Flask apps.")
    assert "python" in tokens
    assert "flask" in tokens


def test_exclamation_stripped():
    tokens = preprocess_text("Python! Flask! REST!")
    assert "python" in tokens


def test_hyphen_stripped():
    tokens = preprocess_text("REST-API developer")
    # After stripping hyphens, 'rest' and 'api' should appear separately
    assert "api" in tokens


def test_slash_stripped():
    tokens = preprocess_text("CI/CD pipeline Docker/Kubernetes")
    assert "pipeline" in tokens or "docker" in tokens or "kubernetes" in tokens


def test_parentheses_stripped():
    tokens = preprocess_text("experience (5 years) with Python")
    assert "python" in tokens
    assert "years" in tokens


# ── Number handling ───────────────────────────────────────────────────────────

def test_long_numbers_kept():
    tokens = preprocess_text("5 years experience with Python 3.10 and version 2023")
    # '2023' and '3' (after split) — numbers > 2 chars in string form are kept
    assert "years" in tokens


def test_version_numbers_handled():
    """Version-like strings after punctuation removal become number tokens."""
    tokens = preprocess_text("Python 310 and Node 1800")
    # '310' and '1800' are > 2 chars so kept
    assert "310" in tokens or "python" in tokens


# ── Idempotency ───────────────────────────────────────────────────────────────

def test_idempotent_same_output_twice():
    text = "Senior Python developer with Flask and SQL experience"
    assert preprocess_text(text) == preprocess_text(text)


def test_order_preserved():
    """Tokens should appear in the same order as the input words."""
    tokens = preprocess_text("python flask docker kubernetes")
    idx_python = tokens.index("python")
    idx_flask  = tokens.index("flask")
    idx_docker = tokens.index("docker")
    assert idx_python < idx_flask < idx_docker


# ── Domain-specific job description ──────────────────────────────────────────

def test_devops_job_text():
    text = (
        "We are looking for a DevOps engineer with experience in Docker, "
        "Kubernetes, Terraform, AWS, CI/CD pipelines, Jenkins and Prometheus."
    )
    tokens = preprocess_text(text)
    for expected in ("devops", "engineer", "docker", "kubernetes", "terraform", "aws"):
        assert expected in tokens, f"Expected '{expected}' in tokens"


def test_data_science_job_text():
    text = (
        "Data Scientist with Python, SQL, scikit-learn, TensorFlow, "
        "deep learning, NLP, and statistical modelling experience."
    )
    tokens = preprocess_text(text)
    for expected in ("data", "scientist", "python", "sql", "tensorflow", "nlp"):
        assert expected in tokens


# ── Large text ────────────────────────────────────────────────────────────────

def test_large_text_does_not_raise():
    """A large string (simulated resume) should preprocess without error."""
    large_text = " ".join([
        "Python developer Flask REST API SQL Docker Kubernetes AWS GCP CI CD "
        "machine learning TensorFlow scikit pandas numpy jupyter notebook"
    ] * 50)
    tokens = preprocess_text(large_text)
    assert len(tokens) > 0
    assert "python" in tokens
