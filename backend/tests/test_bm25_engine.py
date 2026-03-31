"""Unit tests for BM25Engine"""
import pytest
from bm25_module.bm25_engine import BM25Engine

def test_engine_init_basic():
    engine = BM25Engine(["python developer flask api", "java spring boot microservices"])
    assert engine._num_docs == 2

def test_engine_raises_on_empty():
    with pytest.raises(ValueError):
        BM25Engine([])

def test_engine_raises_all_empty_docs():
    with pytest.raises(ValueError):
        BM25Engine(["   ", ""])

def test_search_returns_top_k():
    docs = ["python developer", "java developer", "data scientist python", "devops engineer docker"]
    engine = BM25Engine(docs)
    results = engine.search("python developer", top_k=2)
    assert len(results) == 2

def test_search_results_sorted_desc():
    docs = ["python flask api developer", "java spring", "python machine learning data"]
    engine = BM25Engine(docs)
    results = engine.search("python developer flask", top_k=3)
    scores = [s for _, s in results]
    assert scores == sorted(scores, reverse=True)

def test_search_returns_original_index():
    docs = ["", "valid python document", ""]
    engine = BM25Engine(docs)
    results = engine.search("python", top_k=1)
    assert results[0][0] == 1  # original index of valid doc

def test_empty_query_returns_empty():
    engine = BM25Engine(["python developer", "java developer"])
    results = engine.search("", top_k=2)
    assert results == []

def test_search_top_k_capped():
    engine = BM25Engine(["doc one", "doc two"])
    results = engine.search("doc", top_k=100)
    assert len(results) <= 2
