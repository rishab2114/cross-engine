"""Keyword (BM25) + semantic (TF-IDF -> LSA) retrieval over the frozen corpus."""
from __future__ import annotations

import re

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

TOKEN = re.compile(r"[a-z][a-z0-9\-]+")
STOP = set("""a an the of and or in on for to with by from as at is are was were be been this that these
those we our their its it which using use used based study paper results show find also between into than
can may more most such not no""".split())


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


class Retriever:
    def __init__(self, corpus: list[dict], n_components: int = 256, seed: int = 0):
        self.docs = corpus
        texts = [f"{p['title']}. {p['abstract']}" for p in corpus]
        self.bm25 = BM25Okapi([tokenize(t) for t in texts])
        self.tfidf = TfidfVectorizer(min_df=3, max_df=0.3, sublinear_tf=True,
                                     stop_words="english", ngram_range=(1, 2), max_features=200_000)
        X = self.tfidf.fit_transform(texts)
        self.svd = TruncatedSVD(n_components=n_components, random_state=seed)
        self.Z = normalize(self.svd.fit_transform(X))

    def embed(self, text: str) -> np.ndarray:
        return normalize(self.svd.transform(self.tfidf.transform([text])))[0]

    def search(self, query: str, k: int = 30, fields: list[str] | None = None) -> list[dict]:
        """Hybrid ranking: reciprocal-rank fusion of BM25 and LSA cosine."""
        bm = self.bm25.get_scores(tokenize(query))
        sem = self.Z @ self.embed(query)
        mask = np.ones(len(self.docs), bool)
        if fields:
            mask = np.array([d["field"] in fields for d in self.docs])
        rrf = np.zeros(len(self.docs))
        for scores in (bm, sem):
            s = np.where(mask, scores, -np.inf)
            order = np.argsort(-s)
            ranks = np.empty_like(order)
            ranks[order] = np.arange(len(order))
            rrf += 1.0 / (60 + ranks)
        rrf[~mask] = -np.inf
        top = np.argsort(-rrf)[:k]
        return [self.docs[i] for i in top]
