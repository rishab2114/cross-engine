"""Concept co-occurrence graph built from the frozen pre-2020 corpus.

Nodes are OpenAlex concepts; an edge (a, b) exists when at least one corpus paper
is tagged with both. Every edge keeps the ids of the papers that support it.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from itertools import combinations

# Concepts that appear in a very large share of papers carry little information.
MAX_DOC_SHARE = 0.05
MIN_DOC_FREQ = 5


class ConceptGraph:
    def __init__(self, corpus: list[dict], max_doc_share: float = MAX_DOC_SHARE,
                 min_doc_freq: int = MIN_DOC_FREQ, key: str = "concepts"):
        self.papers = {p["id"]: p for p in corpus}
        df = Counter(c for p in corpus for c in set(p[key]))
        n = len(corpus)
        self.vocab = {c for c, k in df.items() if k >= min_doc_freq and k / n <= max_doc_share}
        self.df = {c: df[c] for c in self.vocab}
        self.n_docs = n
        self.edge_papers: dict[tuple[str, str], list[str]] = defaultdict(list)
        self.concept_papers: dict[str, list[str]] = defaultdict(list)
        self.field_counts: dict[str, Counter] = defaultdict(Counter)
        self.year_counts: dict[str, Counter] = defaultdict(Counter)
        for p in corpus:
            cs = sorted(c for c in set(p[key]) if c in self.vocab)
            for c in cs:
                self.concept_papers[c].append(p["id"])
                self.field_counts[c][p["field"]] += 1
                self.year_counts[c][p["year"]] += 1
            for a, b in combinations(cs, 2):
                self.edge_papers[(a, b)].append(p["id"])
        self.adj: dict[str, dict[str, int]] = defaultdict(dict)
        for (a, b), ps in self.edge_papers.items():
            self.adj[a][b] = len(ps)
            self.adj[b][a] = len(ps)

    # ---- basic queries -------------------------------------------------
    @staticmethod
    def key(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a < b else (b, a)

    def cooccur(self, a: str, b: str) -> int:
        return len(self.edge_papers.get(self.key(a, b), []))

    def is_novel_pair(self, a: str, b: str) -> bool:
        """Novelty rule: the pair never appears together on a corpus paper, and neither
        name contains the other (e.g. 'urbanism' / 'new urbanism' is not a new connection)."""
        if a == b or a in b or b in a:
            return False
        return self.cooccur(a, b) == 0

    def home_field(self, c: str) -> str:
        fc = self.field_counts[c]
        return fc.most_common(1)[0][0] if fc else "unknown"

    def growth(self, c: str) -> float:
        """Share of a concept's papers in 2015-2019 vs 2010-2014 (smoothed log ratio)."""
        yc = self.year_counts[c]
        late = sum(v for y, v in yc.items() if 2015 <= y <= 2019)
        early = sum(v for y, v in yc.items() if 2010 <= y <= 2014)
        return math.log((late + 1) / (early + 1))

    # ---- path scoring --------------------------------------------------
    def edge_weight(self, a: str, b: str) -> float:
        """Normalised association strength (cosine-like) between two concepts."""
        k = self.adj[a].get(b, 0)
        if not k:
            return 0.0
        return k / math.sqrt(self.df[a] * self.df[b])

    def path_score(self, a: str, b: str, max_mid: int = 50) -> tuple[float, list[tuple]]:
        """Score unconnected pair (a, b) by 2- and 3-hop paths through intermediates.

        Returns total score and the strongest paths as tuples of concepts.
        """
        paths: list[tuple[float, tuple]] = []
        na, nb = self.adj[a], self.adj[b]
        # 2-hop: a - m - b
        for m in set(na) & set(nb):
            s = self.edge_weight(a, m) * self.edge_weight(m, b)
            paths.append((s, (a, m, b)))
        # 3-hop: a - m1 - m2 - b (restricted to strongest neighbours for tractability)
        top_a = sorted(na, key=lambda m: -self.edge_weight(a, m))[:max_mid]
        top_b = set(sorted(nb, key=lambda m: -self.edge_weight(b, m))[:max_mid])
        for m1 in top_a:
            if m1 == b:
                continue
            w1 = self.edge_weight(a, m1)
            for m2 in set(self.adj[m1]) & top_b:
                if m2 in (a, m1):
                    continue
                s = 0.5 * w1 * self.edge_weight(m1, m2) * self.edge_weight(m2, b)
                paths.append((s, (a, m1, m2, b)))
        paths.sort(key=lambda t: -t[0])
        return sum(s for s, _ in paths), [p for _, p in paths[:3]]

    def support_papers(self, path: tuple, per_edge: int = 1) -> list[str]:
        """Pick supporting paper ids for each edge along a path (earliest-id first, deterministic)."""
        ids = []
        for u, v in zip(path, path[1:]):
            ps = sorted(self.edge_papers.get(self.key(u, v), []))[:per_edge]
            ids.extend(ps)
        return list(dict.fromkeys(ids))
