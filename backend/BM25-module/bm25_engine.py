# bm25_engine.py
from rank_bm25 import BM25Okapi
from utils import preprocess_text

class BM25Engine:
    def __init__(self, documents):
        self.raw_docs = documents
        
        # Remove empty documents
        self.tokenized_docs = []
        for doc in documents:
            tokens = preprocess_text(doc)
            if tokens:   # only keep non-empty
                self.tokenized_docs.append(tokens)

        if not self.tokenized_docs:
            raise ValueError("No valid documents found after preprocessing!")

        self.bm25 = BM25Okapi(self.tokenized_docs)

    def search(self, query, top_k=5):
        tokenized_query = preprocess_text(query)
        scores = self.bm25.get_scores(tokenized_query)
        
        ranked = sorted(
            list(enumerate(scores)), 
            key=lambda x: x[1], 
            reverse=True
        )

        return ranked[:top_k]