"""Labelled units for matcher validation (Amendment 4).

    python -m discovery.units build      # new controls + hard-negative candidates + adjudication jobs
    python -m discovery.units collect    # read adjudications -> data/units.json
    python -m discovery.units split      # seeded 60/40 selection/holdout -> data/units_selection.json, data/holdout_sealed/
"""
from __future__ import annotations

import json
import random
import sys
from itertools import combinations

from . import llm
from . import openalex as oa
from .budget import est_tokens
from .corpus import BASE_FILTER, FIELDS
from .study import DATA, engine, jdump, jload, opaque_id, read_jsonl

CTRL2_SEED = 4343
HN_SEED = 4344
SPLIT_SEED = 4345
N_CTRL2_PER_FIELD_WINDOW = 10
N_HARD_NEG = 48
ADJ_BATCH = 10
MAX_JOB_TOKENS = 30_000


def _pair(nodes, g, require_novel, rng):
    pairs = [(a, b) for a, b in combinations(sorted(nodes), 2)
             if a in g.vocab and b in g.vocab and a not in b and b not in a]
    if require_novel:
        pairs = [p for p in pairs if g.cooccur(*p) == 0]
    return rng.choice(pairs) if pairs else None


def build_controls2() -> list[dict]:
    """Same construction as controls.build, new seed, no search at build time."""
    e = engine(); g = e.graph
    rng = random.Random(CTRL2_SEED)
    old = {(c["a"], c["b"], c["window"]) for c in jload(DATA / "controls.json")}
    out = []
    for field in FIELDS:
        docs = [d for d in e.docs if d["field"] == field]
        rng.shuffle(docs)
        n = 0
        for d in docs:
            p = _pair(d["nodes"], g, False, rng)
            if not p or (p[0], p[1], "pre2020") in old:
                continue
            out.append({"window": "pre2020", "field": field, "a": p[0], "b": p[1],
                        "source": {"id": d["id"], "year": d["year"], "title": d["title"], "abstract": d["abstract"][:900]}})
            n += 1
            if n == N_CTRL2_PER_FIELD_WINDOW:
                break
    for field, flt in FIELDS.items():
        works = oa.sample_works(f"{flt},publication_year:2020-2024,{BASE_FILTER}", 400, seed=CTRL2_SEED)
        n = 0
        for w in works:
            nodes = sorted({k["display_name"].lower() for k in (w.get("keywords") or [])})
            p = _pair(nodes, g, True, rng)
            if not p or (p[0], p[1], "post2019") in old:
                continue
            out.append({"window": "post2019", "field": field, "a": p[0], "b": p[1],
                        "source": {"id": w["id"].rsplit("/", 1)[-1], "year": w["publication_year"],
                                   "title": w.get("title") or "",
                                   "abstract": oa.reconstruct_abstract(w.get("abstract_inverted_index"))[:900]}})
            n += 1
            if n == N_CTRL2_PER_FIELD_WINDOW:
                break
    for i, c in enumerate(out):
        c["cid"] = f"D{i:02d}"
    jdump(DATA / "controls2.json", out)
    return out


def hard_negative_candidates() -> list[dict]:
    """Papers returned by the fixed search (contain both phrases) in windows judged 'no match'."""
    from .study import collect_judgments
    store = jload(DATA / "pair_candidates.json")
    J = collect_judgments("judge")
    pool = []
    for key, entry in store.items():
        a, b = key.split(" || ")
        for w in ("pre2020", "post2019"):
            j = J.get(key, {}).get(w)
            if j is None or j["match"]:
                continue
            for c in entry[w]["candidates"]:
                if c.get("abstract"):
                    pool.append({"a": a, "b": b, "window": w, "paper": c, "pair_key": key})
    rng = random.Random(HN_SEED)
    rng.shuffle(pool)
    seen, out = set(), []
    for u in pool:  # at most 2 papers per pair, for diversity
        k = u["pair_key"]
        if sum(1 for x in out if x["pair_key"] == k) >= 2 or (k, u["paper"]["id"]) in seen:
            continue
        seen.add((k, u["paper"]["id"]))
        out.append(u)
        if len(out) == N_HARD_NEG:
            break
    for i, u in enumerate(out):
        u["hid"] = f"H{i:02d}"
    jdump(DATA / "hard_negative_candidates.json", out)
    return out


def _render(items):
    return "\n\n".join(
        f"ITEM {it['item_id']}\nA = {it['A']}\nB = {it['B']}\nPaper [{it['paper']['id']}] ({it['paper']['year']}) "
        f"{it['paper']['title']}. {it['paper']['abstract']}" for it in items)


def adjudication_jobs() -> None:
    old = jload(DATA / "controls.json")
    new = jload(DATA / "controls2.json")
    hn = jload(DATA / "hard_negative_candidates.json")
    items = []
    for c in old + new:
        items.append({"key": f"SRC::{c['cid']}", "A": c["a"], "B": c["b"], "paper": c["source"]})
    for u in hn:
        items.append({"key": f"HN::{u['hid']}", "A": u["a"], "B": u["b"], "paper": u["paper"]})
    for it in items:
        it["item_id"] = opaque_id("adj", it["key"])
    random.Random(SPLIT_SEED + 1).shuffle(items)
    for i in range(0, len(items), ADJ_BATCH):
        batch = items[i:i + ADJ_BATCH]
        prompt = llm.template("adjudicate.md").format(items=_render(batch))
        assert est_tokens(prompt) < MAX_JOB_TOKENS
        llm.write_job("adj", f"adj_{i // ADJ_BATCH:03d}", prompt, {"id_map": {b["item_id"]: b["key"] for b in batch}})
    print(f"{len(items)} adjudication items in {(len(items) + ADJ_BATCH - 1) // ADJ_BATCH} jobs")


def collect() -> dict:
    labels = {}
    d = llm.JOBS / "adj"
    for p in sorted(d.glob("*.json")):
        op = llm.JOBS / "adj_out" / p.name
        if not op.exists():
            continue
        idm = llm.read_meta("adj", p.stem)["id_map"]
        for l in llm.parse_json(op.read_text())["labels"]:
            if l["item_id"] in idm:
                labels[idm[l["item_id"]]] = l
    old = jload(DATA / "controls.json"); new = jload(DATA / "controls2.json")
    hn = jload(DATA / "hard_negative_candidates.json")
    units = {"positive_controls": [], "hard_negatives": [], "classification_positives": [], "audit_pairs": []}
    for c in old + new:
        l = labels.get(f"SRC::{c['cid']}")
        if l and l["label"] == "explicit":
            u = {"uid": f"PC::{c['cid']}", "a": c["a"], "b": c["b"], "window": c["window"], "field": c["field"],
                 "source": c["source"], "quote": l["quote_or_reason"]}
            units["positive_controls"].append(u)
            units["classification_positives"].append({"uid": f"CP::{c['cid']}", "a": c["a"], "b": c["b"],
                                                      "paper": c["source"], "window": c["window"]})
        elif l and l["label"] == "mention_only":  # Amendment 4a: control sources adjudicated mention-only
            units["hard_negatives"].append({"uid": f"HN::SRC::{c['cid']}", "a": c["a"], "b": c["b"],
                                            "paper": c["source"], "window": c["window"], "origin": "control_source"})
    for u in hn:
        l = labels.get(f"HN::{u['hid']}")
        if l and l["label"] == "mention_only":
            units["hard_negatives"].append({"uid": f"HN::{u['hid']}", "a": u["a"], "b": u["b"],
                                            "paper": u["paper"], "window": u["window"], "origin": "fixed_search_no_match"})
    audit = jload(DATA / "search_audit_sample.json")
    for k in audit:
        a, b = k.split(" || ")
        for w in ("pre2020", "post2019"):
            units["audit_pairs"].append({"uid": f"AU::{k}::{w}", "a": a, "b": b, "window": w, "pair_key": k})
    units["label_counts"] = {k: sum(1 for l in labels.values() if l["label"] == k)
                             for k in ("explicit", "mention_only", "not_both", "unclear")}
    units["n_adjudicated"] = len(labels)
    jdump(DATA / "units.json", units)
    print({k: len(v) for k, v in units.items() if isinstance(v, list)}, units["label_counts"])
    return units


def split() -> None:
    units = jload(DATA / "units.json")
    rng = random.Random(SPLIT_SEED)
    sel, hold = {}, {}
    for kind in ("positive_controls", "hard_negatives", "classification_positives", "audit_pairs"):
        groups = {}
        for u in units[kind]:
            groups.setdefault(u["window"], []).append(u)
        sel[kind], hold[kind] = [], []
        for w, us in sorted(groups.items()):
            us = sorted(us, key=lambda x: x["uid"])
            rng.shuffle(us)
            k = round(0.6 * len(us))
            sel[kind] += us[:k]
            hold[kind] += us[k:]
    # keep each positive control and its classification twin on the same side
    sel_cp = {u["uid"].split("::")[1] for u in sel["positive_controls"]}
    allcp = sel["classification_positives"] + hold["classification_positives"]
    sel["classification_positives"] = [u for u in allcp if u["uid"].split("::")[1] in sel_cp]
    hold["classification_positives"] = [u for u in allcp if u["uid"].split("::")[1] not in sel_cp]
    # keep both windows of an audit pair on the same side
    allau = sel["audit_pairs"] + hold["audit_pairs"]
    keys = sorted({u["pair_key"] for u in allau})
    random.Random(SPLIT_SEED + 2).shuffle(keys)
    selk = set(keys[:round(0.6 * len(keys))])
    sel["audit_pairs"] = [u for u in allau if u["pair_key"] in selk]
    hold["audit_pairs"] = [u for u in allau if u["pair_key"] not in selk]
    jdump(DATA / "units_selection.json", sel)
    (DATA / "holdout_sealed").mkdir(exist_ok=True)
    jdump(DATA / "holdout_sealed" / "units_holdout.json", hold)
    print("selection", {k: len(v) for k, v in sel.items()}, "holdout", {k: len(v) for k, v in hold.items()})


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        build_controls2(); hard_negative_candidates(); adjudication_jobs()
    elif cmd == "collect":
        collect()
    elif cmd == "split":
        split()
