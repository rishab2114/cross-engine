"""Engine state: corpus + concept graph + retrieval index + concept relevance."""
from __future__ import annotations

import pickle
import time
from pathlib import Path

import numpy as np

from . import corpus as corpus_mod
from .graph import ConceptGraph
from .retrieval import Retriever

STATE = corpus_mod.DATA / "engine.pkl"


class Engine:
    def __init__(self, docs: list[dict]):
        t0 = time.time()
        # Graph nodes are OpenAlex keywords (lower-cased); they name research
        # problems, methods and settings far more precisely than legacy concepts.
        for d in docs:
            d["nodes"] = sorted({k.lower() for k in d["keywords"]})
        self.docs = docs
        self.by_id = {d["id"]: d for d in docs}
        self.graph = ConceptGraph(docs, key="nodes")
        t1 = time.time()
        self.retriever = Retriever(docs)
        t2 = time.time()
        # concept centroid in LSA space = mean of its papers' vectors
        idx = {d["id"]: i for i, d in enumerate(docs)}
        self.concepts = sorted(self.graph.vocab)
        C = np.zeros((len(self.concepts), self.retriever.Z.shape[1]))
        for j, c in enumerate(self.concepts):
            rows = [idx[p] for p in self.graph.concept_papers[c]]
            v = self.retriever.Z[rows].mean(0)
            C[j] = v / (np.linalg.norm(v) + 1e-12)
        self.C = C
        self.cidx = {c: j for j, c in enumerate(self.concepts)}
        self.setup_seconds = {"graph": t1 - t0, "retrieval_index": t2 - t1,
                              "concept_centroids": time.time() - t2}

    def relevance(self, text: str) -> dict[str, float]:
        q = self.retriever.embed(text)
        s = self.C @ q
        return dict(zip(self.concepts, s.tolist()))

    def top_concepts(self, text: str, k: int, fields: list[str] | None = None) -> list[tuple[str, float]]:
        rel = self.relevance(text)
        items = sorted(rel.items(), key=lambda t: -t[1])
        if fields:
            items = [t for t in items if self.graph.home_field(t[0]) in fields]
        return items[:k]

    def best_paper(self, concept: str, query: str) -> dict:
        """Most question-relevant corpus paper tagged with concept."""
        q = self.retriever.embed(query)
        ids = self.graph.concept_papers[concept]
        idx = {d["id"]: i for i, d in enumerate(self.docs)} if not hasattr(self, "_idx") else self._idx
        self._idx = idx
        rows = [idx[p] for p in ids]
        best = rows[int(np.argmax(self.retriever.Z[rows] @ q))]
        return self.docs[best]

    def save(self, path: Path = STATE) -> None:
        with path.open("wb") as fh:
            pickle.dump(self, fh)

    @staticmethod
    def load(path: Path = STATE) -> "Engine":
        # Pickle is used only for this project's own locally built cache (data/engine.pkl,
        # gitignored). Never load an engine file obtained from elsewhere.
        with path.open("rb") as fh:
            return pickle.load(fh)


def build(path: Path = STATE) -> Engine:
    e = Engine(corpus_mod.load())
    e.save(path)
    return e
