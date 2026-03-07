# bm25_engine.py
from rank_bm25 import BM25Okapi
from .utils import preprocess_text


class BM25Engine:
    """
    Wraps rank_bm25's BM25Okapi to handle empty documents safely.

    Key fix: tracks a mapping from internal BM25 index → original document index,
    so results always refer back to the correct document even when empty docs
    are filtered out.
    """

    def __init__(self, documents: list):
        if not documents:
            raise ValueError("BM25Engine requires at least one document.")

        self._index_map = []        # internal_idx → original_idx
        tokenized_docs = []

        for original_idx, doc in enumerate(documents):
            tokens = preprocess_text(doc)
            if tokens:
                tokenized_docs.append(tokens)
                self._index_map.append(original_idx)

        if not tokenized_docs:
            raise ValueError(
                "No valid documents found after preprocessing. "
                "Check that your PDFs contain readable text."
            )

        self.bm25 = BM25Okapi(tokenized_docs)
        self._num_docs = len(tokenized_docs)

    def search(self, query: str, top_k: int = 5):
        """
        Returns list of (original_doc_index, score) sorted by score descending.
        """
        tokens = preprocess_text(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)

        ranked = sorted(
            [(self._index_map[i], float(scores[i])) for i in range(self._num_docs)],
            key=lambda x: x[1],
            reverse=True
        )

        return ranked[:top_k]