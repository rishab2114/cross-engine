"""Known-match controls for validating the fixed literature search (Amendment 1).

Each control is a concept pair with a known source paper in one window:
  - pre2020: a keyword pair tagged on a corpus paper (source = that paper)
  - post2019: a keyword pair tagged on a seeded-sample 2020-2024 paper in the same fields
    whose pair never co-occurs in the corpus (source = that paper)

Two judge items are made per control, under opaque ids, mixed blind among pilot items:
  - confirm: the source paper alone. Is it an explicit study of the A-B link?
  - recall:  the fixed search's top-5 for that window. Does it contain a match?
Recall = share of confirmed controls whose recall item is judged a match.

    python -m discovery.controls build
"""
from __future__ import annotations

import json
import random
import sys
from itertools import combinations

from . import openalex as oa
from .corpus import BASE_FILTER, FIELDS
from .study import DATA, engine, jdump, search_pair

N_PER_FIELD_WINDOW = 5
SEED = 4242


def _pair_from(nodes: list[str], g, require_novel: bool, rng: random.Random):
    pairs = [(a, b) for a, b in combinations(sorted(nodes), 2)
             if a in g.vocab and b in g.vocab and a not in b and b not in a]
    if require_novel:
        pairs = [p for p in pairs if g.cooccur(*p) == 0]
    return rng.choice(pairs) if pairs else None


def build() -> list[dict]:
    e = engine()
    g = e.graph
    rng = random.Random(SEED)
    controls = []
    # pre2020: from corpus papers
    for field in FIELDS:
        docs = [d for d in e.docs if d["field"] == field]
        rng.shuffle(docs)
        n = 0
        for d in docs:
            p = _pair_from(d["nodes"], g, require_novel=False, rng=rng)
            if not p:
                continue
            controls.append({"window": "pre2020", "field": field, "a": p[0], "b": p[1],
                             "source": {"id": d["id"], "year": d["year"], "title": d["title"],
                                        "abstract": d["abstract"][:900]}})
            n += 1
            if n == N_PER_FIELD_WINDOW:
                break
    # post2019: from a seeded sample of 2020-2024 papers
    for field, flt in FIELDS.items():
        works = oa.sample_works(f"{flt},publication_year:2020-2024,{BASE_FILTER}", 300, seed=SEED)
        n = 0
        for w in works:
            nodes = sorted({k["display_name"].lower() for k in (w.get("keywords") or [])})
            p = _pair_from(nodes, g, require_novel=True, rng=rng)
            if not p:
                continue
            controls.append({"window": "post2019", "field": field, "a": p[0], "b": p[1],
                             "source": {"id": w["id"].rsplit("/", 1)[-1], "year": w["publication_year"],
                                        "title": w.get("title") or "",
                                        "abstract": oa.reconstruct_abstract(w.get("abstract_inverted_index"))[:900]}})
            n += 1
            if n == N_PER_FIELD_WINDOW:
                break
    for i, c in enumerate(controls):
        c["cid"] = f"C{i:02d}"
        _, res = search_pair(c["a"], c["b"], c["window"])
        c["search_candidates"] = res
        c["source_in_top5"] = any(r["id"] == c["source"]["id"] for r in res)
    jdump(DATA / "controls.json", controls)
    print(f"built {len(controls)} controls; source in top-5: {sum(c['source_in_top5'] for c in controls)}")
    return controls


def judge_items() -> list[dict]:
    """Control items in the same format as pilot items (keyed internally, opaque to the judge)."""
    p = DATA / "controls.json"
    if not p.exists():
        return []
    items = []
    for c in json.loads(p.read_text()):
        items.append({"key": f"CTRL::{c['cid']}::confirm", "A": c["a"], "B": c["b"],
                      "windows": {c["window"]: [c["source"]]}})
        if c["search_candidates"]:
            items.append({"key": f"CTRL::{c['cid']}::recall", "A": c["a"], "B": c["b"],
                          "windows": {c["window"]: c["search_candidates"]}})
    return items


def recall(J: dict) -> dict:
    """J maps internal key -> {window: judgment}."""
    controls = json.loads((DATA / "controls.json").read_text())
    out = {"pre2020": {"n_controls": 0, "confirmed": 0, "recalled": 0},
           "post2019": {"n_controls": 0, "confirmed": 0, "recalled": 0}, "items": []}
    for c in controls:
        w = c["window"]
        out[w]["n_controls"] += 1
        conf = J.get(f"CTRL::{c['cid']}::confirm", {}).get(w)
        rec = J.get(f"CTRL::{c['cid']}::recall", {}).get(w)
        confirmed = bool(conf and conf["match"])
        recalled = bool(rec and rec["match"]) if c["search_candidates"] else False
        if confirmed:
            out[w]["confirmed"] += 1
            out[w]["recalled"] += recalled
        out["items"].append({"cid": c["cid"], "window": w, "a": c["a"], "b": c["b"],
                             "confirmed": confirmed, "recalled": recalled,
                             "source_in_top5": c["source_in_top5"]})
    for w in ("pre2020", "post2019"):
        k = out[w]["confirmed"]
        out[w]["recall"] = out[w]["recalled"] / k if k else None
    return out


if __name__ == "__main__":
    {"build": build}[sys.argv[1]]()
