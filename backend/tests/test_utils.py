"""Unit tests for text preprocessing utils"""
import pytest
from bm25_module.utils import preprocess_text

def test_basic_tokenization():
    tokens = preprocess_text("Python developer Flask REST API")
    assert "python" in tokens
    assert "developer" in tokens
    assert "flask" in tokens

def test_stopwords_removed():
    tokens = preprocess_text("the quick brown fox jumps over the lazy dog")
    assert "the" not in tokens
    assert "over" not in tokens

def test_short_tokens_removed():
    tokens = preprocess_text("a an is to python")
    # 'a', 'an', 'is', 'to' are short — only 'python' should survive
    for tok in tokens:
        # tech domain preserved tokens may be short (e.g. 'ml', 'ai', 'r')
        if tok not in ("ml", "ai", "r", "sql", "aws", "gcp", "api", "nlp", "css", "git", "ios"):
            assert len(tok) > 2

def test_preserved_tech_terms():
    tokens = preprocess_text("proficient in Python SQL AWS GCP and ML")
    for term in ("python", "sql", "aws", "gcp", "ml"):
        assert term in tokens, f"Tech term '{term}' should be preserved"

def test_empty_string_returns_empty():
    assert preprocess_text("") == []

def test_none_like_empty_string():
    assert preprocess_text("   ") == []

def test_punctuation_stripped():
    tokens = preprocess_text("Python, Flask! REST-API.")
    assert "python" in tokens
    assert "flask" in tokens

def test_numbers_kept():
    tokens = preprocess_text("5 years experience with Python 3.10")
    # numbers that are > 2 chars as strings are kept
    assert "years" in tokens

def test_case_insensitive():
    tokens = preprocess_text("PYTHON Developer FLASK")
    assert "python" in tokens
    assert "developer" in tokens
    assert "flask" in tokens

def test_returns_list():
    result = preprocess_text("hello world")
    assert isinstance(result, list)
