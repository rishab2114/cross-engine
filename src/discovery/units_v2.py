"""Fresh labelled set for judge repair (Amendment 5).

    python -m discovery.units_v2 build     # candidates + two independent adjudication orderings
    python -m discovery.units_v2 collect   # agreement, agreed units, contested set, human sheet
    python -m discovery.units_v2 split     # seeded 60/40 -> data/units_v2_selection.json, data/holdout_sealed_v2/
"""
from __future__ import annotations

import csv
import random
import sys
from itertools import combinations

from . import llm
from . import openalex as oa
from .budget import est_tokens
from .corpus import BASE_FILTER, FIELDS
from .matchers import search_A
from .study import DATA, RESULTS, engine, jdump, jload, opaque_id

POS_SEED, HN_SEED, SPLIT_SEED = 5151, 5152, 5153
N_POS_PER_FIELD_WINDOW = 30      # 30 x 2 fields x 2 windows = 120
N_HN_PAIRS = 60                  # pairs searched; up to 2 papers each -> ~120 papers
ADJ_BATCH = 10


def _used() -> tuple[set, set]:
    """Pairs and paper ids already used in Amendment 4 units (must not reappear)."""
    pairs, papers = set(), set()
    for f in ("controls.json", "controls2.json"):
        for c in jload(DATA / f):
            pairs.add(tuple(sorted((c["a"], c["b"]))))
            papers.add(c["source"]["id"])
    for u in jload(DATA / "hard_negative_candidates.json"):
        pairs.add(tuple(sorted((u["a"], u["b"]))))
        papers.add(u["paper"]["id"])
    for k in jload(DATA / "search_audit_sample.json"):
        pairs.add(tuple(sorted(k.split(" || "))))
    return pairs, papers


def _pairs_of(nodes, g, novel):
    ps = [(a, b) for a, b in combinations(sorted(nodes), 2)
          if a in g.vocab and b in g.vocab and a not in b and b not in a]
    return [p for p in ps if g.cooccur(*p) == 0] if novel else ps


def build_positive_candidates() -> list[dict]:
    e = engine(); g = e.graph
    rng = random.Random(POS_SEED)
    used_pairs, used_papers = _used()
    out = []
    for field in FIELDS:
        docs = [d for d in e.docs if d["field"] == field]
        rng.shuffle(docs)
        n = 0
        for d in docs:
            if d["id"] in used_papers:
                continue
            ps = [p for p in _pairs_of(d["nodes"], g, False) if p not in used_pairs]
            if not ps:
                continue
            p = rng.choice(ps)
            used_pairs.add(p); used_papers.add(d["id"])
            out.append({"window": "pre2020", "field": field, "a": p[0], "b": p[1],
                        "paper": {"id": d["id"], "year": d["year"], "title": d["title"], "abstract": d["abstract"][:900]}})
            n += 1
            if n == N_POS_PER_FIELD_WINDOW:
                break
    for field, flt in FIELDS.items():
        works = oa.sample_works(f"{flt},publication_year:2020-2024,{BASE_FILTER}", 600, seed=POS_SEED)
        n = 0
        for w in works:
            wid = w["id"].rsplit("/", 1)[-1]
            if wid in used_papers:
                continue
            nodes = sorted({k["display_name"].lower() for k in (w.get("keywords") or [])})
            ps = [p for p in _pairs_of(nodes, g, True) if p not in used_pairs]
            abstract = oa.reconstruct_abstract(w.get("abstract_inverted_index"))
            if not ps or not abstract:
                continue
            p = rng.choice(ps)
            used_pairs.add(p); used_papers.add(wid)
            out.append({"window": "post2019", "field": field, "a": p[0], "b": p[1],
                        "paper": {"id": wid, "year": w["publication_year"], "title": w.get("title") or "",
                                  "abstract": abstract[:900]}})
            n += 1
            if n == N_POS_PER_FIELD_WINDOW:
                break
    for i, c in enumerate(out):
        c["vid"] = f"P{i:03d}"
    jdump(DATA / "v2_positive_candidates.json", out)
    return out


def build_hard_negative_candidates(pos: list[dict]) -> list[dict]:
    """Papers returned by word-level search A for new pairs; all contain both concepts' words."""
    e = engine(); g = e.graph
    rng = random.Random(HN_SEED)
    used_pairs, used_papers = _used()
    used_pairs |= {tuple(sorted((c["a"], c["b"]))) for c in pos}
    used_papers |= {c["paper"]["id"] for c in pos}
    docs = list(e.docs)
    rng.shuffle(docs)
    out, n_pairs = [], 0
    for d in docs:
        ps = [p for p in _pairs_of(d["nodes"], g, False) if p not in used_pairs]
        if not ps:
            continue
        p = rng.choice(ps)
        used_pairs.add(p)
        w = "pre2020" if rng.random() < 0.5 else "post2019"
        res = [r for r in search_A(p[0], p[1], w) if r.get("abstract") and r["id"] not in used_papers]
        if not res:
            continue
        n_pairs += 1
        for r in res[:2]:
            used_papers.add(r["id"])
            out.append({"window": w, "a": p[0], "b": p[1], "paper": r})
        if n_pairs == N_HN_PAIRS:
            break
    for i, u in enumerate(out):
        u["vid"] = f"N{i:03d}"
    jdump(DATA / "v2_hard_negative_candidates.json", out)
    return out


def _render(items):
    return "\n\n".join(
        f"ITEM {it['item_id']}\nA = {it['A']}\nB = {it['B']}\nPaper [{it['paper']['id']}] ({it['paper']['year']}) "
        f"{it['paper']['title']}. {it['paper']['abstract']}" for it in items)


def adjudication_jobs() -> None:
    pos = jload(DATA / "v2_positive_candidates.json")
    hn = jload(DATA / "v2_hard_negative_candidates.json")
    base = [{"key": c["vid"], "A": c["a"], "B": c["b"], "paper": c["paper"]} for c in pos + hn]
    for tag, seed in (("adj_v2a", 1), ("adj_v2b", 2)):
        items = [dict(b) for b in base]
        for it in items:
            it["item_id"] = opaque_id(tag, it["key"])
        random.Random(SPLIT_SEED + seed).shuffle(items)
        for i in range(0, len(items), ADJ_BATCH):
            batch = items[i:i + ADJ_BATCH]
            prompt = llm.template("adjudicate.md").format(items=_render(batch))
            assert est_tokens(prompt) < 30_000
            llm.write_job(tag, f"{tag}_{i // ADJ_BATCH:03d}", prompt,
                          {"id_map": {b["item_id"]: b["key"] for b in batch}})
    print(f"{len(base)} items x 2 orderings, {(len(base) + ADJ_BATCH - 1) // ADJ_BATCH} jobs each")


def _labels(tag: str) -> dict:
    out = {}
    for p in sorted((llm.JOBS / tag).glob("*.json")):
        op = llm.JOBS / f"{tag}_out" / p.name
        if not op.exists():
            continue
        idm = llm.read_meta(tag, p.stem)["id_map"]
        for l in llm.parse_json(op.read_text())["labels"]:
            if l["item_id"] in idm:
                out[idm[l["item_id"]]] = l
    return out


def collect() -> dict:
    pos = {c["vid"]: c for c in jload(DATA / "v2_positive_candidates.json")}
    hn = {u["vid"]: u for u in jload(DATA / "v2_hard_negative_candidates.json")}
    la, lb = _labels("adj_v2a"), _labels("adj_v2b")
    both = sorted(set(la) & set(lb))
    agree = sum(la[k]["label"] == lb[k]["label"] for k in both)
    cats = ["explicit", "mention_only", "not_both", "unclear"]
    n = len(both)
    po = agree / n if n else None
    pe = sum((sum(la[k]["label"] == c for k in both) / n) * (sum(lb[k]["label"] == c for k in both) / n)
             for c in cats) if n else None
    kappa = (po - pe) / (1 - pe) if n and pe < 1 else None
    units = {"positives": [], "hard_negatives": [], "contested": []}
    for k in both:
        x = pos.get(k) or hn[k]
        a, b = la[k]["label"], lb[k]["label"]
        rec = {"uid": f"V2::{k}", "a": x["a"], "b": x["b"], "window": x["window"], "paper": x["paper"],
               "origin": "control_source" if k in pos else "searchA_result", "labels": [a, b]}
        if a == b == "explicit":
            units["positives"].append(rec)
        elif a == b == "mention_only":
            units["hard_negatives"].append(rec)
        elif a != b:
            units["contested"].append(rec)
    units["agreement"] = {"n_both_labelled": n, "raw_agreement": po, "cohen_kappa": kappa,
                          "missing_a": len(set(pos) | set(hn)) - len(la), "missing_b": len(set(pos) | set(hn)) - len(lb)}
    units["counts"] = {t: {w: sum(u["window"] == w for u in units[t]) for w in ("pre2020", "post2019")}
                       for t in ("positives", "hard_negatives", "contested")}
    jdump(DATA / "units_v2.json", units)
    with (RESULTS / "fresh_human_sheet.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["unit_id", "concept_A", "concept_B", "window", "paper_id", "paper_title", "paper_abstract",
                    "human_label (explicit / mention_only / not_both / unclear)", "supporting_quote", "annotator"])
        for u in units["positives"] + units["hard_negatives"] + units["contested"]:
            p = u["paper"]
            w.writerow([u["uid"], u["a"], u["b"], u["window"], p["id"], p["title"], p["abstract"], "", "", ""])
    print(units["agreement"], units["counts"])
    return units


def split() -> None:
    U = jload(DATA / "units_v2.json")
    rng = random.Random(SPLIT_SEED)
    sel, hold = {}, {}
    for t in ("positives", "hard_negatives"):
        sel[t], hold[t] = [], []
        for w in ("pre2020", "post2019"):
            us = sorted([u for u in U[t] if u["window"] == w], key=lambda x: x["uid"])
            rng.shuffle(us)
            k = round(0.6 * len(us))
            sel[t] += us[:k]
            hold[t] += us[k:]
    jdump(DATA / "units_v2_selection.json", sel)
    (DATA / "holdout_sealed_v2").mkdir(exist_ok=True)
    jdump(DATA / "holdout_sealed_v2" / "units_v2_holdout.json", hold)
    print("selection", {t: len(v) for t, v in sel.items()}, "holdout", {t: len(v) for t, v in hold.items()})


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        p = build_positive_candidates(); h = build_hard_negative_candidates(p); adjudication_jobs()
        print(len(p), "positive candidates;", len(h), "hard-negative candidates")
    elif cmd == "collect":
        collect()
    elif cmd == "split":
        split()
