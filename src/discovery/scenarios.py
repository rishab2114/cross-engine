"""Zero-LLM scenario layer for training a link detector (Amendment 5b).

(a) Template scenarios: synthetic abstracts in 5 classes, built by code from hand-written
    sentence templates plus filler sentences taken from real corpus abstracts.
(b) Weak labels: real corpus abstracts for keyword pairs tagged on the same paper, weakly
    labelled "explicit" when one sentence contains both concepts with a relation cue between
    them, and "mention_only" when both appear but never in the same sentence.

All pairs and papers used in validation (Amendment 4 units and Amendment 5 candidates) are excluded.

    python -m discovery.scenarios build
"""
from __future__ import annotations

import json
import random
import re
from itertools import combinations

from .study import DATA, engine, jdump, jload

SEED = 5154
N_PAIRS = 600
CLASSES = ["explicit_effect", "explicit_method", "mention_same", "mention_separate", "not_both"]

T_EFFECT = [
    "We estimate the effect of {A} on {B}.",
    "The results show that {A} significantly affects {B}.",
    "This study examines how {A} influences {B}.",
    "We find that higher {A} is associated with lower {B}.",
    "{B} responds strongly to changes in {A}.",
    "Our estimates indicate a positive relationship between {A} and {B}.",
    "We investigate whether {A} explains variation in {B}.",
    "Using panel data, we show that {A} increases {B}.",
    "The impact of {A} on {B} is found to be heterogeneous across regions.",
    "We provide evidence that {A} is a key determinant of {B}.",
    "{A} reduces {B}, particularly in the short run.",
    "The paper tests the hypothesis that {A} drives {B}.",
    "We document a causal link from {A} to {B}.",
    "Changes in {A} predict subsequent changes in {B}.",
    "We analyse the relationship between {A} and {B} using a difference-in-differences design.",
    "The link between {A} and {B} is mediated by institutional factors.",
    "Results suggest that {B} is sensitive to {A}.",
    "We quantify how much {A} contributes to {B}.",
]
T_METHOD = [
    "We use {B} to model {A}.",
    "{A} is estimated using {B}.",
    "We apply {B} to analyse {A}.",
    "A {B} approach is developed to forecast {A}.",
    "We propose a {B}-based framework for measuring {A}.",
    "{B} is employed to optimise {A}.",
    "The study applies {B} to the problem of {A}.",
    "We formulate {A} as a {B} problem and solve it.",
    "Using {B}, we evaluate {A} across several case studies.",
    "We measure {A} with {B}.",
    "A {B} model is calibrated to reproduce observed {A}.",
    "{A} is simulated with {B} under alternative scenarios.",
]
T_MENTION_SAME = [
    "This paper discusses {A}, {B} and related policy issues.",
    "Topics covered include {A} and {B}.",
    "Previous work has studied {A} and {B}, but rarely in developing countries.",
    "Both {A} and {B} have received attention in the literature.",
    "We review recent developments in {A}, {B}, and regulation.",
    "The survey asked respondents about {A} and {B}.",
    "Keywords: {A}; {B}; policy evaluation.",
    "Issues such as {A} and {B} are outside the scope of this study.",
    "The dataset contains information on {A}, {B} and household income.",
    "{A} and {B} are treated as control variables.",
    "Our sample covers firms active in {A} and {B}.",
    "Although {A} and {B} are often discussed together, this paper focuses on neither.",
]
T_A_ONLY = [
    "This paper studies {A} in detail.",
    "We examine recent trends in {A}.",
    "The analysis focuses on {A} and its determinants.",
    "We provide new evidence on {A}.",
    "{A} has become an important topic for policymakers.",
]
T_B_ONLY = [
    "We also report descriptive statistics on {B}.",
    "A separate section describes {B}.",
    "Finally, we discuss {B} briefly.",
    "{B} is documented in an appendix.",
    "Some implications for {B} are noted.",
]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) >= 6]


def excluded() -> tuple[set, set]:
    pairs, papers = set(), set()
    for f in ("controls.json", "controls2.json"):
        for c in jload(DATA / f):
            pairs.add(tuple(sorted((c["a"], c["b"])))); papers.add(c["source"]["id"])
    for f, key in (("hard_negative_candidates.json", "paper"), ("v2_positive_candidates.json", "paper"),
                   ("v2_hard_negative_candidates.json", "paper")):
        p = DATA / f
        if p.exists():
            for u in jload(p):
                pairs.add(tuple(sorted((u["a"], u["b"])))); papers.add(u[key]["id"])
    for k in jload(DATA / "search_audit_sample.json"):
        pairs.add(tuple(sorted(k.split(" || "))))
    return pairs, papers


def _pairs(rng, docs, g, ex_pairs, n):
    out, seen = [], set(ex_pairs)
    for d in docs:
        ps = [(a, b) for a, b in combinations(sorted(d["nodes"]), 2)
              if a in g.vocab and b in g.vocab and a not in b and b not in a and (a, b) not in seen]
        if ps:
            p = rng.choice(ps); seen.add(p); out.append((p, d))
        if len(out) == n:
            break
    return out


def template_scenarios() -> list[dict]:
    e = engine(); g = e.graph
    rng = random.Random(SEED)
    ex_pairs, ex_papers = excluded()
    docs = [d for d in e.docs if d["id"] not in ex_papers]
    rng.shuffle(docs)
    pairs = _pairs(rng, docs, g, ex_pairs, N_PAIRS)
    fillers = [s for d in docs[:5000] for s in _sentences(d["abstract"])]
    out = []
    for (a, b), _ in pairs:
        if rng.random() < 0.5:
            a, b = b, a
        def fill(k):
            return [f for f in rng.sample(fillers, k) if a not in f.lower() and b not in f.lower()]
        for cls in CLASSES:
            if cls == "explicit_effect":
                core = [rng.choice(T_EFFECT)]
            elif cls == "explicit_method":
                core = [rng.choice(T_METHOD)]
            elif cls == "mention_same":
                core = [rng.choice(T_MENTION_SAME)]
            elif cls == "mention_separate":
                core = [rng.choice(T_A_ONLY), "__FILL__", rng.choice(T_B_ONLY)]
            else:
                core = [rng.choice(T_A_ONLY)]
            sents = fill(rng.randint(1, 2)) + [c if c == "__FILL__" else c.format(A=a, B=b) for c in core] + fill(rng.randint(1, 3))
            sents = [fill(1)[0] if s == "__FILL__" and fill(1) else s for s in sents if s != "__FILL__" or True]
            sents = [s for s in sents if s != "__FILL__"]
            out.append({"a": a, "b": b, "text": " ".join(sents), "cls": cls,
                        "label": int(cls.startswith("explicit")), "source": "template"})
    return out


CUES = re.compile(r"\b(effect|effects|impact|impacts|affect|affects|influenc\w*|determin\w*|predict\w*|associat\w*|"
                  r"relationship|relation|link\w*|caus\w*|increas\w*|decreas\w*|reduc\w*|lead\w* to|driv\w*|"
                  r"explain\w*|using|use[sd]?|appl\w*|model\w*|measur\w*|estimat\w*|forecast\w*|optimi[sz]\w*)\b", re.I)


def weak_labels(n_max: int = 3000) -> list[dict]:
    from .link_detector import find_mentions
    e = engine(); g = e.graph
    rng = random.Random(SEED + 1)
    ex_pairs, ex_papers = excluded()
    docs = [d for d in e.docs if d["id"] not in ex_papers]
    rng.shuffle(docs)
    out, n_pos, n_neg = [], 0, 0
    for d in docs:
        ps = [(a, b) for a, b in combinations(sorted(d["nodes"]), 2)
              if a in g.vocab and b in g.vocab and a not in b and b not in a and (a, b) not in ex_pairs]
        if not ps:
            continue
        a, b = rng.choice(ps)
        text = f"{d['title']}. {d['abstract']}"
        sents = re.split(r"(?<=[.!?])\s+", text)
        both_any = any(find_mentions(s, a) for s in sents) and any(find_mentions(s, b) for s in sents)
        if not both_any:
            continue
        same = [s for s in sents if find_mentions(s, a) and find_mentions(s, b)]
        if same and any(CUES.search(s) for s in same):
            if n_pos >= n_max // 2:
                continue
            lab, n_pos = 1, n_pos + 1
        elif not same:
            if n_neg >= n_max // 2:
                continue
            lab, n_neg = 0, n_neg + 1
        else:
            continue
        out.append({"a": a, "b": b, "text": text, "cls": "weak", "label": lab, "source": "weak", "paper_id": d["id"]})
        if n_pos >= n_max // 2 and n_neg >= n_max // 2:
            break
    return out


def build() -> None:
    t = template_scenarios()
    w = weak_labels()
    jdump(DATA / "scenarios_template.json", t)
    jdump(DATA / "scenarios_weak.json", w)
    print(f"templates: {len(t)} ({sum(x['label'] for x in t)} explicit); weak: {len(w)} ({sum(x['label'] for x in w)} explicit)")


if __name__ == "__main__":
    import sys
    {"build": build}[sys.argv[1]]()
