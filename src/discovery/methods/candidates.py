"""Candidate concept pairs for the graph (G), pairwise (P) and popularity (B) methods.

All three obey the same novelty rule: the two concepts never co-occur on any
corpus paper (all corpus papers are published 2000-2019).
"""
from __future__ import annotations

import math

from ..engine import Engine

N_ANCHORS = 15      # concepts most relevant to the question
N_TARGETS = 1000    # wider pool of relevant concepts to connect to
SHORTLIST = 10
MAX_PER_CONCEPT = 2  # diversity: a concept may appear in at most 2 shortlisted pairs


def _pool(engine: Engine, question: str):
    ranked = engine.top_concepts(question, N_TARGETS)
    anchors = [c for c, _ in ranked[:N_ANCHORS]]
    rel = dict(ranked)
    return anchors, [c for c, _ in ranked], rel


def _novel_pairs(engine: Engine, anchors, targets):
    g = engine.graph
    seen = set()
    for a in anchors:
        for b in targets:
            if a == b:
                continue
            k = g.key(a, b)
            if k in seen or not g.is_novel_pair(a, b):
                continue
            seen.add(k)
            yield k


def _diverse_top(scored: list[tuple[float, tuple, dict]], n: int = SHORTLIST):
    out, uses = [], {}
    for s, (a, b), info in sorted(scored, key=lambda t: -t[0]):
        if uses.get(a, 0) >= MAX_PER_CONCEPT or uses.get(b, 0) >= MAX_PER_CONCEPT:
            continue
        out.append({"a": a, "b": b, "score": s, **info})
        uses[a] = uses.get(a, 0) + 1
        uses[b] = uses.get(b, 0) + 1
        if len(out) == n:
            break
    return out


def dissimilarity(engine: Engine, a: str, b: str) -> float:
    """1 - cosine between the two concepts' content centroids (higher = less obvious pairing)."""
    return float(1.0 - engine.C[engine.cidx[a]] @ engine.C[engine.cidx[b]])


def direct_score(engine: Engine, a: str, b: str, rel: dict) -> float:
    """Features of the two concepts themselves: relevance to the question x dissimilarity."""
    return max(rel[a], 1e-6) * max(rel[b], 1e-6) * dissimilarity(engine, a, b)


def graph_paths(engine: Engine, question: str, n_candidates: int = SHORTLIST) -> list[dict]:
    """G: direct score x multi-hop path strength (connected through intermediates, yet not obvious)."""
    anchors, targets, rel = _pool(engine, question)
    scored = []
    for a, b in _novel_pairs(engine, anchors, targets):
        ps, paths = engine.graph.path_score(a, b)
        if ps <= 0:
            continue
        s = ps * direct_score(engine, a, b, rel)
        scored.append((s, (a, b), {"paths": [list(p) for p in paths]}))
    top = _diverse_top(scored, n_candidates)
    for c in top:
        attach_evidence(engine, c, question)
    return top


def attach_evidence(engine: Engine, c: dict, question: str) -> None:
    """Shared evidence procedure for G and P (Amendment 1).

    If the pair has any 2- or 3-hop path, the evidence is the support papers of its two
    strongest paths (at most 5). Otherwise it is the most question-relevant paper for
    each concept. Path information is used here only to choose evidence.
    """
    if "paths" not in c:
        _, paths = engine.graph.path_score(c["a"], c["b"])
        c["paths"] = [list(p) for p in paths]
    c["has_path"] = bool(c["paths"])
    if c["paths"]:
        ids = []
        for p in c["paths"][:2]:
            ids.extend(engine.graph.support_papers(tuple(p)))
        c["evidence_ids"] = list(dict.fromkeys(ids))[:5]
    else:
        c["evidence_ids"] = list(dict.fromkeys([engine.best_paper(c["a"], question)["id"],
                                                engine.best_paper(c["b"], question)["id"]]))


def pairwise(engine: Engine, question: str, n_candidates: int = SHORTLIST) -> list[dict]:
    """P: rank novel pairs by the same direct features as G, without any path information."""
    anchors, targets, rel = _pool(engine, question)
    scored = [(direct_score(engine, a, b, rel), (a, b), {}) for a, b in _novel_pairs(engine, anchors, targets)]
    top = _diverse_top(scored, n_candidates)
    for c in top:
        attach_evidence(engine, c, question)
    return top


def popularity(engine: Engine, question: str, n_candidates: int = SHORTLIST) -> list[dict]:
    """B: no LLM. Among question-relevant concepts, pair the most frequent and fastest-growing."""
    g = engine.graph
    ranked = engine.top_concepts(question, 60)
    pool = [c for c, _ in ranked]
    pop = {c: math.log(g.df[c]) + g.growth(c) for c in pool}
    scored = []
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            if g.is_novel_pair(a, b):
                scored.append((pop[a] + pop[b], g.key(a, b), {}))
    top = _diverse_top(scored, n_candidates)
    for c in top:
        c["hypothesis"] = f"{c['a']} is associated with {c['b']}."
    return top
