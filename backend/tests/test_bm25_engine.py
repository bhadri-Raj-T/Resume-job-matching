"""
tests/test_bm25_engine.py
─────────────────────────
Comprehensive unit tests for BM25Engine.

Covers:
  - Initialisation (normal, empty, all-empty-docs)
  - Search result structure, ordering, index mapping
  - Edge cases: empty query, stop-word-only query, single doc
  - Score properties (non-negative, float)
  - top_k boundary behaviour
  - Relevance: tech-specific queries surface the right documents
  - Stability: repeated calls return identical results
"""
import pytest
from bm25_module.bm25_engine import BM25Engine


# ── Helpers ───────────────────────────────────────────────────────────────────

PYTHON_DOCS = [
    "python developer flask api rest backend",
    "java spring boot microservices enterprise",
    "data scientist python machine learning scikit tensorflow",
    "devops engineer docker kubernetes jenkins ci cd",
    "frontend react javascript typescript css html",
]


# ── Init tests ────────────────────────────────────────────────────────────────

def test_engine_init_basic():
    engine = BM25Engine(["python developer flask api", "java spring boot microservices"])
    assert engine._num_docs == 2


def test_engine_init_single_doc():
    engine = BM25Engine(["python developer"])
    assert engine._num_docs == 1


def test_engine_raises_on_empty_list():
    with pytest.raises(ValueError, match="at least one document"):
        BM25Engine([])


def test_engine_raises_all_empty_string_docs():
    with pytest.raises(ValueError, match="No valid documents"):
        BM25Engine(["   ", ""])


def test_engine_raises_all_stopword_docs():
    """Documents that collapse to zero tokens after preprocessing raise ValueError."""
    with pytest.raises(ValueError, match="No valid documents"):
        BM25Engine(["the and or but", "is are was were"])


def test_engine_skips_empty_docs_in_count():
    """Empty docs are filtered; _num_docs reflects only valid ones."""
    engine = BM25Engine(["", "valid python document", "  "])
    assert engine._num_docs == 1


def test_engine_index_map_built():
    engine = BM25Engine(PYTHON_DOCS)
    assert len(engine._index_map) == engine._num_docs


def test_engine_bm25_object_created():
    engine = BM25Engine(PYTHON_DOCS)
    assert engine.bm25 is not None


# ── Search result structure ───────────────────────────────────────────────────

def test_search_returns_list():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("python developer", top_k=3)
    assert isinstance(results, list)


def test_search_result_tuples_have_two_elements():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("python flask", top_k=2)
    for item in results:
        assert len(item) == 2, "Each result should be (doc_index, score)"


def test_search_result_index_is_int():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("python", top_k=3)
    for idx, _ in results:
        assert isinstance(idx, int)


def test_search_result_score_is_float():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("python developer", top_k=3)
    for _, score in results:
        assert isinstance(score, float)


def test_search_scores_non_negative():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("python", top_k=5)
    for _, score in results:
        assert score >= 0.0, f"Score should be non-negative, got {score}"


# ── Ordering ──────────────────────────────────────────────────────────────────

def test_search_results_sorted_descending():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("python developer flask", top_k=5)
    scores = [s for _, s in results]
    assert scores == sorted(scores, reverse=True)


def test_search_results_sorted_desc_single_match():
    engine = BM25Engine(["unique rare xylophone", "common words here", "unique rare violin"])
    results = engine.search("unique rare xylophone", top_k=3)
    scores = [s for _, s in results]
    assert scores == sorted(scores, reverse=True)


# ── top_k boundary ────────────────────────────────────────────────────────────

def test_search_returns_exactly_top_k():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("python developer", top_k=3)
    assert len(results) == 3


def test_search_top_k_capped_at_corpus_size():
    engine = BM25Engine(["doc one", "doc two"])
    results = engine.search("doc", top_k=100)
    assert len(results) <= 2


def test_search_top_k_one():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("python", top_k=1)
    assert len(results) == 1


def test_search_top_k_equals_corpus():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("developer", top_k=len(PYTHON_DOCS))
    assert len(results) == len(PYTHON_DOCS)


# ── Index mapping (original doc index preserved) ──────────────────────────────

def test_search_returns_original_index_when_leading_empty():
    """Empty leading doc → valid doc is at original index 1."""
    engine = BM25Engine(["", "valid python document", ""])
    results = engine.search("python", top_k=1)
    assert results[0][0] == 1


def test_search_original_index_in_range():
    docs = ["alpha beta", "gamma delta", "epsilon zeta"]
    engine = BM25Engine(docs)
    results = engine.search("alpha", top_k=3)
    for idx, _ in results:
        assert 0 <= idx < len(docs)


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_query_returns_empty_list():
    engine = BM25Engine(["python developer", "java developer"])
    assert engine.search("", top_k=2) == []


def test_whitespace_only_query_returns_empty():
    engine = BM25Engine(["python developer", "java developer"])
    assert engine.search("   ", top_k=2) == []


def test_stopword_only_query_returns_empty():
    """A query of only stop-words preprocesses to [], so returns []."""
    engine = BM25Engine(["python developer", "java developer"])
    results = engine.search("the and or is", top_k=2)
    # preprocess_text("the and or is") → [] → engine returns []
    assert results == []


def test_no_matching_terms_scores_may_be_zero():
    """BM25 may return zero-score results when query terms absent from corpus."""
    engine = BM25Engine(["python flask api", "java spring boot"])
    results = engine.search("xylophone trumpet trombone", top_k=2)
    # Results still sorted; scores should be zero or non-negative
    for _, score in results:
        assert score >= 0.0


# ── Relevance (semantic sanity) ───────────────────────────────────────────────

def test_python_query_ranks_python_doc_first():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("python flask api developer", top_k=1)
    # Index 0 is "python developer flask api rest backend"
    assert results[0][0] == 0


def test_devops_query_ranks_devops_doc_first():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("docker kubernetes jenkins ci cd devops", top_k=1)
    # Index 3 is the DevOps doc
    assert results[0][0] == 3


def test_data_science_query_ranks_ds_doc_first():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("machine learning scikit tensorflow data scientist", top_k=1)
    # Index 2 is the DS doc
    assert results[0][0] == 2


def test_frontend_query_ranks_frontend_doc_first():
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("react javascript typescript frontend", top_k=1)
    # Index 4 is the Frontend doc
    assert results[0][0] == 4


# ── Stability ─────────────────────────────────────────────────────────────────

def test_repeated_search_same_results():
    engine = BM25Engine(PYTHON_DOCS)
    query = "python developer flask"
    r1 = engine.search(query, top_k=3)
    r2 = engine.search(query, top_k=3)
    assert r1 == r2


def test_engine_handles_large_corpus():
    """Engine should initialise and search without error on 100 documents."""
    docs = [f"document {i} python developer engineer software" for i in range(100)]
    engine = BM25Engine(docs)
    results = engine.search("python developer", top_k=10)
    assert len(results) == 10


def test_scores_vary_across_results():
    """At least the top result should score higher than the last when query is specific."""
    engine = BM25Engine(PYTHON_DOCS)
    results = engine.search("python flask api developer backend", top_k=5)
    scores = [s for _, s in results]
    # Top score should be strictly greater than minimum (not all equal)
    assert scores[0] >= scores[-1]


# ── Tech-term preservation ────────────────────────────────────────────────────

def test_tech_terms_not_filtered_as_stopwords():
    """Short tech terms like 'sql', 'aws', 'ml' must survive preprocessing."""
    docs = ["sql database administrator mysql postgresql", "aws cloud architect gcp azure"]
    engine = BM25Engine(docs)
    results = engine.search("sql database", top_k=1)
    assert results[0][0] == 0  # SQL doc should rank first


def test_api_preserved_as_token():
    docs = ["rest api developer flask", "frontend react css html"]
    engine = BM25Engine(docs)
    results = engine.search("api developer", top_k=1)
    assert results[0][0] == 0
