"""Candidate matchers A-D (Amendment 4) and their blind judge jobs.

    python -m discovery.matchers search  --set selection      # A, B (+ exploratory semantic) candidate retrieval
    python -m discovery.matchers agentic --set selection      # write C job files (searcher subagents fill them)
    python -m discovery.matchers judge   --set selection      # blind judge jobs for all candidate lists + classification
"""
from __future__ import annotations

import argparse
import random
import re

import numpy as np

from . import llm
from . import openalex as oa
from .budget import est_tokens
from .study import (DATA, WINDOWS, clean_concept, engine, jdump, jload, opaque_id, render_items)

TOPK = 5
JUDGE_ITEMS = 10
MAX_JOB_TOKENS = 30_000
NEAR_SYN_COS = 0.85
NEAR_SYN_K = 2
AGENTIC_PER_JOB = 8
STOP = set("of and the in on for to a an with by from as at".split())
SEED = 4346
_unit_window: dict = {}


def units(which: str) -> dict:
    if which == "selection":
        return jload(DATA / "units_selection.json")
    if which == "holdout":
        dec = DATA / "matcher_selection_decision.json"
        if not dec.exists():
            raise SystemExit("Holdout is sealed until data/matcher_selection_decision.json is committed.")
        return jload(DATA / "holdout_sealed" / "units_holdout.json")
    raise ValueError(which)


def retrieval_units(u: dict) -> list[dict]:
    return u["positive_controls"] + u["audit_pairs"]


def _words(c: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9][a-z0-9\-]*", clean_concept(c).lower()) if w not in STOP]


def _fmt(works: list[dict]) -> list[dict]:
    return [{"id": w["id"].rsplit("/", 1)[-1], "year": w.get("publication_year"), "title": w.get("title") or "",
             "abstract": oa.reconstruct_abstract(w.get("abstract_inverted_index"))[:700]} for w in works]


SEL = "id,title,publication_year,abstract_inverted_index"


def search_A(a: str, b: str, window: str) -> list[dict]:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return []
    q = "(" + " AND ".join(wa) + ") AND (" + " AND ".join(wb) + ")"
    d = oa.get("works", {"filter": f"title_and_abstract.search:{q},{WINDOWS[window]}", "per_page": TOPK,
                         "sort": "relevance_score:desc", "select": SEL})
    return _fmt(d.get("results", []))


def near_synonyms(c: str) -> list[str]:
    e = engine()
    if c not in e.cidx:
        return []
    v = e.C[e.cidx[c]]
    sims = e.C @ v
    cw = set(_words(c))
    out = []
    for j in np.argsort(-sims):
        t = e.concepts[j]
        if t == c or sims[j] < NEAR_SYN_COS:
            if sims[j] < NEAR_SYN_COS:
                break
            continue
        if cw & set(_words(t)) and t not in c and c not in t:
            out.append(t)
        if len(out) == NEAR_SYN_K:
            break
    return out


def search_B(a: str, b: str, window: str) -> list[dict]:
    def grp(c):
        terms = [clean_concept(t).replace('"', "") for t in [c] + near_synonyms(c)]
        return "(" + " OR ".join(f'"{t}"' for t in dict.fromkeys(terms) if t) + ")"
    d = oa.get("works", {"filter": f"title_and_abstract.search:{grp(a)} AND {grp(b)},{WINDOWS[window]}",
                         "per_page": TOPK, "sort": "relevance_score:desc", "select": SEL})
    return _fmt(d.get("results", []))


def search_semantic(a: str, b: str, window: str) -> list[dict]:
    """Exploratory only (not eligible for selection)."""
    try:
        d = oa.get("works", {"search.semantic": f"relationship between {clean_concept(a)} and {clean_concept(b)}",
                             "filter": WINDOWS[window], "per_page": TOPK, "select": SEL})
        return _fmt(d.get("results", []))
    except Exception as exc:  # endpoint/param may differ; record and move on
        return [{"error": str(exc)}]


def run_search(which: str) -> None:
    U = retrieval_units(units(which))
    path = DATA / f"matcher_candidates_{which}.json"
    store = jload(path) if path.exists() else {}
    for u in U:
        for name, fn in (("A", search_A), ("B", search_B), ("S", search_semantic)):
            k = f"{name}::{u['uid']}"
            if k not in store:
                store[k] = fn(u["a"], u["b"], u["window"])
        jdump(path, store)
    print(f"searched {len(U)} units x 3 matchers")


def agentic_jobs(which: str, uids: list[str] | None = None, tag: str = "C") -> None:
    U = retrieval_units(units(which))
    if uids is not None:
        U = [u for u in U if u["uid"] in uids]
    rng = random.Random(SEED)
    U = sorted(U, key=lambda x: x["uid"]); rng.shuffle(U)
    kind = f"match_{tag}_{which}"
    for i in range(0, len(U), AGENTIC_PER_JOB):
        part = U[i:i + AGENTIC_PER_JOB]
        idm = {f"M{i + j:03d}": u["uid"] for j, u in enumerate(part)}
        text = "\n".join(f"- item_id: {o}\n  A = {u['a']}\n  B = {u['b']}\n  window = {u['window']}"
                         for o, u in zip(idm, part))
        llm.write_job(kind, f"{kind}_{i // AGENTIC_PER_JOB:02d}",
                      llm.template("match_agentic.md").format(items=text), {"id_map": idm})
    print(f"{len(U)} agentic items in {(len(U) + AGENTIC_PER_JOB - 1) // AGENTIC_PER_JOB} jobs ({kind})")


def agentic_candidates(which: str, tag: str = "C") -> dict:
    """uid -> list of candidate papers (fetched by id: singleton lookups are free)."""
    global _unit_window
    _unit_window = {u["uid"]: u["window"] for u in retrieval_units(units(which))}
    kind = f"match_{tag}_{which}"
    out = {}
    for p in sorted((llm.JOBS / kind).glob("*.json")) if (llm.JOBS / kind).exists() else []:
        op = llm.JOBS / f"{kind}_out" / p.name
        if not op.exists():
            continue
        idm = llm.read_meta(kind, p.stem)["id_map"]
        for r in llm.parse_json(op.read_text())["results"]:
            if r["item_id"] not in idm:
                continue
            papers = []
            for wid in (r.get("candidates") or [])[:3]:
                wid = str(wid).rsplit("/", 1)[-1]
                try:
                    w = oa.get(f"works/{wid}", {"select": SEL})
                    papers.extend(_fmt([w]))
                except Exception:
                    pass
            uid = idm[r["item_id"]]
            w = uid.rsplit("::", 1)[-1] if uid.startswith("AU::") else None
            if w is None:  # positive controls carry their window in the unit; look it up
                w = _unit_window.get(uid)
            if w:  # enforce the window: drop any candidate outside it
                papers = [p for p in papers if p.get("year") and
                          ((p["year"] <= 2019) if w == "pre2020" else (2020 <= p["year"] <= 2024))]
            out[uid] = {"papers": papers, "queries": r.get("queries", [])}
    return out


def judge_jobs(which: str, matchers=("A", "B", "S", "C")) -> None:
    """Blind production-judge jobs: retrieval candidate lists for each matcher + classification units."""
    U = units(which)
    store = jload(DATA / f"matcher_candidates_{which}.json")
    agentic = agentic_candidates(which) if "C" in matchers else {}
    by_uid = {u["uid"]: u for u in retrieval_units(U)}
    kind = f"judge_m_{which}"
    done = set()
    for p in (llm.JOBS / kind).glob("*.json") if (llm.JOBS / kind).exists() else []:
        done |= set(llm.read_meta(kind, p.stem)["id_map"].values())
    items = []
    for uid, u in by_uid.items():
        for m in matchers:
            cands = agentic.get(uid, {}).get("papers", []) if m == "C" else store.get(f"{m}::{uid}", [])
            cands = [c for c in cands if "error" not in c]
            key = f"RET::{m}::{uid}"
            if cands and key not in done:
                items.append({"key": key, "A": u["a"], "B": u["b"], "windows": {u["window"]: cands}})
    for u in U["classification_positives"] + U["hard_negatives"]:
        key = f"CLS::{u['uid']}"
        if key not in done:
            items.append({"key": key, "A": u["a"], "B": u["b"], "windows": {u["window"]: [u["paper"]]}})
    for it in items:
        it["item_id"] = opaque_id(kind, it["key"])
    random.Random(SEED + 1).shuffle(items)
    start = len(list((llm.JOBS / kind).glob("*.json"))) if (llm.JOBS / kind).exists() else 0
    n_jobs, i = 0, 0
    while i < len(items):
        batch = items[i:i + JUDGE_ITEMS]
        prompt = llm.template("judge_match.md").format(items=render_items(batch))
        while est_tokens(prompt) >= MAX_JOB_TOKENS and len(batch) > 1:
            batch = batch[:-1]
            prompt = llm.template("judge_match.md").format(items=render_items(batch))
        llm.write_job(kind, f"{kind}_{start + n_jobs:03d}", prompt, {"id_map": {b["item_id"]: b["key"] for b in batch}})
        n_jobs += 1
        i += len(batch)
    print(f"{len(items)} judge items in {n_jobs} jobs ({kind})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["search", "agentic", "judge", "judge_noC"])
    ap.add_argument("--set", default="selection")
    a = ap.parse_args()
    if a.stage == "search":
        run_search(a.set)
    elif a.stage == "agentic":
        agentic_jobs(a.set)
    elif a.stage == "judge":
        judge_jobs(a.set)
    elif a.stage == "judge_noC":
        judge_jobs(a.set, matchers=("A", "B", "S"))
