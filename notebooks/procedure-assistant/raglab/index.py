"""Two ways to turn a question and a passage into numbers, and compare them.

**TF-IDF** counts words. A passage is a long sparse vector of word counts,
weighted so that rare words matter more than common ones, and similarity is the
overlap of those weighted counts. It knows nothing about meaning: "de-energize"
and "shut off the power" share no tokens at all.

**MiniLM** is a small transformer trained so that sentences meaning the same
thing land near each other in a 384-dimensional space. What is *learned* is the
mapping from wordpieces to that space; what is *configured* is everything else -
the 256-token window, the cosine similarity, the float16 storage.

Both produce one vector per chunk. Neither reads the question and the passage
together, and neither knows whether the passage answers the question. They only
place things near each other.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from . import chunking, config


def indexed_texts(chunks: pd.DataFrame) -> list[str]:
    return [chunking.indexed_text(title, text)
            for title, text in zip(chunks["source_title"].fillna(""), chunks["text"])]


class TfidfRetriever:
    """Word counting, as the comparison. Fast to build, no model download."""

    name = "tfidf"
    display = "TF-IDF word counts"

    def __init__(self, chunks: pd.DataFrame):
        self.chunks = chunks.reset_index(drop=True)
        self.vectorizer = TfidfVectorizer(**config.TFIDF_PARAMS)
        started = time.perf_counter()
        self.matrix = normalize(self.vectorizer.fit_transform(indexed_texts(self.chunks)))
        self.build_seconds = time.perf_counter() - started

    def scores(self, question: str) -> np.ndarray:
        query = normalize(self.vectorizer.transform([question]))
        return (query @ self.matrix.T).toarray()[0]

    def search(self, question: str, k: int = config.TOP_K_SCORED) -> list[tuple[int, float]]:
        scores = self.scores(question)
        order = np.argsort(-scores)[:k]
        return [(int(i), float(scores[i])) for i in order]


class EmbedRetriever:
    """The deployed retriever: MiniLM sentence embeddings, cosine, float16."""

    name = "minilm"
    display = "MiniLM sentence embeddings"
    _model = None

    def __init__(self, chunks: pd.DataFrame, vectors: np.ndarray | None = None):
        self.chunks = chunks.reset_index(drop=True)
        self.model = self.load_model()
        if vectors is None:
            started = time.perf_counter()
            vectors = self.model.encode(indexed_texts(self.chunks), batch_size=64,
                                        normalize_embeddings=True,
                                        show_progress_bar=False)
            self.build_seconds = time.perf_counter() - started
        else:
            self.build_seconds = 0.0
        self.vectors = np.asarray(vectors, dtype=np.float32)
        self.vectors /= np.linalg.norm(self.vectors, axis=1, keepdims=True)

    @classmethod
    def load_model(cls):
        """Load once per process. A cold start is ~16 s; a query is ~3 ms."""
        if cls._model is None:
            from sentence_transformers import SentenceTransformer
            started = time.perf_counter()
            cls._model = SentenceTransformer(config.EMBEDDER_SHORT, device="cpu")
            cls.model_load_seconds = time.perf_counter() - started
        return cls._model

    def encode_query(self, question: str) -> np.ndarray:
        return self.model.encode([question], normalize_embeddings=True)[0]

    def scores(self, question: str) -> np.ndarray:
        return self.vectors @ self.encode_query(question)

    def search(self, question: str, k: int = config.TOP_K_SCORED) -> list[tuple[int, float]]:
        scores = self.scores(question)
        order = np.argsort(-scores)[:k]
        return [(int(i), float(scores[i])) for i in order]

    def extend(self, extra_chunks: pd.DataFrame) -> "EmbedRetriever":
        """Encode only the new chunks and index the union.

        Used by the duplicate-corpus experiment so adding 30 CFR 57 costs four
        seconds rather than a second full encode.
        """
        extra_vectors = self.model.encode(indexed_texts(extra_chunks), batch_size=64,
                                          normalize_embeddings=True,
                                          show_progress_bar=False)
        combined_chunks = pd.concat([self.chunks, extra_chunks], ignore_index=True)
        combined = np.vstack([self.vectors, np.asarray(extra_vectors, np.float32)])
        return EmbedRetriever(combined_chunks, vectors=combined)


def build(chunks: pd.DataFrame) -> dict:
    """Fit both retrievers on the same chunk table and report the cost of each."""
    tfidf = TfidfRetriever(chunks)
    minilm = EmbedRetriever(chunks)
    return {"tfidf": tfidf, "minilm": minilm}


def build_report(retrievers: dict, chunks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for retriever in retrievers.values():
        vector_bytes = (retriever.matrix.data.nbytes
                        if retriever.name == "tfidf"
                        else retriever.vectors.astype(np.float16).nbytes)
        rows.append({
            "Retriever": retriever.display,
            "Chunks indexed": f"{len(chunks):,}",
            "Vector width": (f"{retriever.matrix.shape[1]:,} vocabulary terms"
                             if retriever.name == "tfidf"
                             else f"{retriever.vectors.shape[1]} dimensions"),
            "Build time": f"{retriever.build_seconds:.1f} s",
            "Index size": f"{vector_bytes / 1e6:.2f} MB",
        })
    return pd.DataFrame(rows)
