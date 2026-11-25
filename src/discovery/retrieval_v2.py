"""Retrieval re-test on the v2 units (Amendment 5, step 5), with the review's C03 fixes.

    python -m discovery.retrieval_v2 search  --set selection             # matcher A candidate lists
    python -m discovery.retrieval_v2 jobs    --set selection --judge J0  # blind judge jobs for A lists
    python -m discovery.retrieval_v2 agentic --set selection --judges J0 J1   # C searches: completed A misses only
    python -m discovery.retrieval_v2 jobs    --set selection --judge J0 --matcher C
    python -m discovery.retrieval_v2 eval    --set selection

Every unit has an explicit state per (judge, matcher): match, no_match, no_candidates, pending or error.
Recall uses completed units only (match / no_match / no_candidates). A gate passes only when nothing is
pending or in error. D runs C only after a *completed* A miss. Holdout mode accepts only the frozen
manifest's judge and matcher (manifest.py) and excludes Amendment 6's overlapping pairs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess

from . import llm, manifest
from . import openalex as oa
from .budget import est_tokens
from .contracts import SchemaError, exclude_overlap, parse_judgments
from .matcher_eval import cp
from .matchers import SEL, _fmt, search_A
from .study import DATA, RESULTS, jdump, jload, opaque_id, render_items

JUDGES = {"J0": "judge_match.md", "J1": "judge_match_quote.md"}
WINDOWS = ("pre2020", "post2019")
RECALL_GATE = 0.80
PER_JOB = 10
AGENTIC_PER_JOB = 8
MAX_JOB_TOKENS = 30_000
COMPLETE = ("match", "no_match", "no_candidates")
SELECTION_FILE = DATA / "units_v2_selection.json"
HOLDOUT_FILE = DATA / "holdout_sealed_v2" / "units_v2_holdout.json"


def _store_path(which: str):
    return DATA / f"retrieval_v2_candidates_{which}.json"


def units(which: str) -> list[dict]:
    """Positive units (pair x window with a known explicit source paper)."""
    manifest.check_set(which)
    if which == "selection":
        return jload(SELECTION_FILE)["positives"]
    manifest.load()
    return exclude_overlap(jload(HOLDOUT_FILE), jload(SELECTION_FILE))[0]["positives"]


def _allowed(which: str, judge: str | None = None, matcher: str | None = None) -> None:
    """Holdout: only the frozen judge; only the matcher's components (A for A; A and C for D)."""
    if which != "holdout":
        return
    m = manifest.load()
    if judge is not None and judge != m["judge"]:
        raise manifest.ManifestError(f"holdout mode accepts only the frozen judge {m['judge']}, not {judge}")
    parts = {"A": {"A"}, "D": {"A", "C", "D"}}[m["matcher"]]
    if matcher is not None and matcher not in parts:
        raise manifest.ManifestError(f"holdout mode accepts only matcher {m['matcher']} (components {sorted(parts)})")


# ---------------------------------------------------------------- candidate retrieval
def search(which: str, matcher: str = "A") -> dict:
    assert matcher == "A", "C candidates come from agentic searcher jobs"
    _allowed(which, matcher="A")
    path = _store_path(which)
    store = jload(path) if path.exists() else {}
    n_new = 0
    for u in units(which):
        k = f"A::{u['uid']}"
        if k in store and store[k]["status"] == "ok":
            continue
        try:
            store[k] = {"status": "ok", "papers": search_A(u["a"], u["b"], u["window"])}
        except oa.BudgetExceeded:
            jdump(path, store)
            raise  # leave the rest pending; never record a budget stop as a miss
        except Exception as exc:  # recorded as an explicit error state, never as "no candidates"
            store[k] = {"status": "error", "error": str(exc)[:300]}
        n_new += 1
        jdump(path, store)
    jdump(path, store)
    print(f"A searched {n_new} new units ({which}); {len(units(which))} units total")
    return store


def agentic_kind(which: str) -> str:
    return f"ret_C_{which}"


def agentic_candidates(which: str) -> dict:
    """uid -> {"status": ok|error, "papers": [...]} from completed C searcher outputs (window enforced)."""
    win = {u["uid"]: u["window"] for u in units(which)}
    kind = agentic_kind(which)
    cache = _store_path(which)
    store = jload(cache) if cache.exists() else {}
    out = {}
    for p in sorted((llm.JOBS / kind).glob("*.json")) if (llm.JOBS / kind).exists() else []:
        op = llm.JOBS / f"{kind}_out" / p.name
        if not op.exists():
            continue
        idm = llm.read_meta(kind, p.stem)["id_map"]
        try:
            llm.check_provenance(kind, p.stem)
            res = llm.parse_json(op.read_text())["results"]
        except Exception as exc:
            for uid in idm.values():
                out[uid] = {"status": "error", "error": f"invalid searcher output: {exc}"[:300]}
            continue
        seen = set()
        for r in res:
            if r.get("item_id") not in idm or r["item_id"] in seen:
                continue
            seen.add(r["item_id"])
            uid = idm[r["item_id"]]
            k = f"C::{uid}"
            if k not in store:
                papers = []
                for wid in (r.get("candidates") or [])[:3]:
                    wid = str(wid).rsplit("/", 1)[-1]
                    try:
                        papers.extend(_fmt([oa.get(f"works/{wid}", {"select": SEL})]))  # singleton lookups are free
                    except Exception:
                        pass
                w = win.get(uid)
                papers = [x for x in papers if x.get("year") and
                          ((x["year"] <= 2019) if w == "pre2020" else (2020 <= x["year"] <= 2024))]
                store[k] = {"status": "ok", "papers": papers, "queries": r.get("queries", [])}
            out[uid] = store[k]
        for iid, uid in idm.items():
            if iid not in seen:
                out[uid] = {"status": "error", "error": "searcher output omitted this item"}
    jdump(cache, store)
    return out


def agentic_jobs(which: str, judges: tuple[str, ...]) -> list[str]:
    """C searcher jobs only for units whose A result is a *completed* miss under any of the given judges."""
    for j in judges:
        _allowed(which, judge=j, matcher="C")
    misses = set()
    for j in judges:
        st = states(which, j, "A")
        pend = [u for u, s in st.items() if s in ("pending", "error")]
        if pend:
            raise RuntimeError(f"A is incomplete under {j} ({len(pend)} pending/error units); C runs only after completed A misses")
        misses |= {u for u, s in st.items() if s in ("no_match", "no_candidates")}
    kind = agentic_kind(which)
    queued = set()
    for p in (llm.JOBS / kind).glob("*.json") if (llm.JOBS / kind).exists() else []:
        queued |= set(llm.read_meta(kind, p.stem)["id_map"].values())
    todo = sorted(misses - queued)
    U = {u["uid"]: u for u in units(which)}
    random.Random(llm.stable_seed("C", which)).shuffle(todo)
    start = len(list((llm.JOBS / kind).glob("*.json"))) if (llm.JOBS / kind).exists() else 0
    for i in range(0, len(todo), AGENTIC_PER_JOB):
        part = todo[i:i + AGENTIC_PER_JOB]
        idm = {opaque_id(kind, uid): uid for uid in part}
        text = "\n".join(f"- item_id: {o}\n  A = {U[uid]['a']}\n  B = {U[uid]['b']}\n  window = {U[uid]['window']}"
                         for o, uid in idm.items())
        llm.write_job(kind, f"{kind}_{start + i // AGENTIC_PER_JOB:02d}",
                      llm.template("match_agentic.md").format(items=text), {"id_map": idm})
    print(f"C: {len(todo)} completed A misses queued in {(len(todo) + AGENTIC_PER_JOB - 1) // AGENTIC_PER_JOB} jobs ({kind})")
    return todo


# ---------------------------------------------------------------- judging
def judge_kind(which: str, judge: str, matcher: str) -> str:
    return f"ret_{judge}_{matcher}_{which}"


def candidate_lists(which: str, matcher: str) -> dict:
    if matcher == "A":
        store = jload(_store_path(which)) if _store_path(which).exists() else {}
        return {k.split("::", 1)[1]: v for k, v in store.items() if k.startswith("A::")}
    return agentic_candidates(which)


def judge_jobs(which: str, judge: str, matcher: str = "A") -> None:
    _allowed(which, judge=judge, matcher=matcher)
    lists = candidate_lists(which, matcher)
    U = {u["uid"]: u for u in units(which)}
    kind = judge_kind(which, judge, matcher)
    queued = set()
    for p in (llm.JOBS / kind).glob("*.json") if (llm.JOBS / kind).exists() else []:
        queued |= set(llm.read_meta(kind, p.stem)["id_map"].values())
    items = []
    for uid, u in U.items():
        c = lists.get(uid)
        if not c or c["status"] != "ok" or not c["papers"] or uid in queued:
            continue
        items.append({"key": uid, "item_id": opaque_id(kind, uid), "A": u["a"], "B": u["b"],
                      "windows": {u["window"]: c["papers"]}})
    items.sort(key=lambda x: x["item_id"])
    random.Random(llm.stable_seed(judge, matcher, which)).shuffle(items)
    start = len(list((llm.JOBS / kind).glob("*.json"))) if (llm.JOBS / kind).exists() else 0
    n, i = 0, 0
    while i < len(items):
        batch = items[i:i + PER_JOB]
        prompt = llm.template(JUDGES[judge]).format(items=render_items(batch))
        while est_tokens(prompt) >= MAX_JOB_TOKENS and len(batch) > 1:
            batch = batch[:-1]
            prompt = llm.template(JUDGES[judge]).format(items=render_items(batch))
        llm.write_job(kind, f"{kind}_{start + n:02d}", prompt, {"id_map": {b["item_id"]: b["key"] for b in batch}})
        n += 1
        i += len(batch)
    print(f"{kind}: {len(items)} items in {n} new jobs")


def judgments(which: str, judge: str, matcher: str) -> tuple[dict, list]:
    kind = judge_kind(which, judge, matcher)
    lists = candidate_lists(which, matcher)
    U = {u["uid"]: u for u in units(which)}
    out, errors = {}, []
    for p in sorted((llm.JOBS / kind).glob("*.json")) if (llm.JOBS / kind).exists() else []:
        op = llm.JOBS / f"{kind}_out" / p.name
        if not op.exists():
            continue
        idm = llm.read_meta(kind, p.stem)["id_map"]
        its = {uid: {"windows": {U[uid]["window"]: lists[uid]["papers"]}} for uid in idm.values()}
        try:
            llm.check_provenance(kind, p.stem)
            out.update(parse_judgments(op.read_text(), idm, its, quote_judge=(judge == "J1")))
        except (SchemaError, llm.JobConflict) as exc:
            errors.append((p.name, str(exc)))
            for uid in idm.values():
                out[uid] = None  # invalid output -> error state
    return out, errors


def states(which: str, judge: str, matcher: str) -> dict:
    """uid -> match | no_match | no_candidates | pending | error."""
    if matcher == "D":
        a = states(which, judge, "A")
        c = states(which, judge, "C")
        return {u: (s if s in ("match", "pending", "error") else c.get(u, "pending")) for u, s in a.items()}
    lists = candidate_lists(which, matcher)
    J, _ = judgments(which, judge, matcher)
    out = {}
    for u in units(which):
        uid = u["uid"]
        c = lists.get(uid)
        if c is None:
            out[uid] = "pending"
        elif c["status"] != "ok":
            out[uid] = "error"
        elif not c["papers"]:
            out[uid] = "no_candidates"
        elif uid not in J:
            out[uid] = "pending"
        elif J[uid] is None:
            out[uid] = "error"
        else:
            out[uid] = "match" if J[uid]["match"] else "no_match"
    return out


# ---------------------------------------------------------------- evaluation
def _sha(path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def evaluate(which: str, judges: tuple[str, ...] | None = None, matchers: tuple[str, ...] = ("A", "D")) -> dict:
    manifest.check_set(which)
    if which == "holdout":
        m = manifest.load()
        judges, matchers = (m["judge"],), (m["matcher"],)
    judges = judges or tuple(JUDGES)
    U = units(which)
    lists_A = candidate_lists(which, "A")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=DATA.parent, text=True).strip()
    except Exception:
        commit = None
    out = {"set": which, "n_units": len(U), "by_window": {w: sum(u["window"] == w for u in U) for w in WINDOWS},
           "result_manifest": {"units_file_sha256": _sha(SELECTION_FILE if which == "selection" else HOLDOUT_FILE),
                               "judge_prompt_sha256": {j: llm.prompt_hashes().get(JUDGES[j]) for j in judges},
                               "commit": commit, "unit_ids": sorted(u["uid"] for u in U)},
           "results": {}}
    if which == "holdout":
        out["frozen_manifest_digest"] = manifest.load()["digest"]
        out["amendment6_excluded_uids"] = exclude_overlap(jload(HOLDOUT_FILE), jload(SELECTION_FILE))[1]
    out["source_found_by_A"] = {w: cp(sum(any(p.get("id") == u["paper"]["id"] for p in lists_A.get(u["uid"], {}).get("papers", []))
                                          for u in U if u["window"] == w), sum(u["window"] == w for u in U)) for w in WINDOWS}
    for j in judges:
        errs = {m: judgments(which, j, m)[1] for m in ("A", "C")}
        for mt in matchers:
            st = states(which, j, mt)
            res = {"states": {s: sum(v == s for v in st.values()) for s in COMPLETE + ("pending", "error")},
                   "recall": {}}
            for w in WINDOWS:
                ws = [st[u["uid"]] for u in U if u["window"] == w]
                res["recall"][w] = cp(sum(s == "match" for s in ws), sum(s in COMPLETE for s in ws))
            comp = res["states"]["pending"] == 0 and res["states"]["error"] == 0 and not errs["A"] and \
                (mt == "A" or not errs["C"])
            res["complete"] = comp
            res["recall_gate"] = all((res["recall"][w]["rate"] or 0) >= RECALL_GATE for w in WINDOWS)
            res["pass_recall_gate"] = bool(comp and res["recall_gate"])
            res["invalid_outputs"] = errs["A"] + (errs["C"] if mt == "D" else [])
            out["results"][f"{j}/{mt}"] = res
    oa_n = sum(1 for v in lists_A.values() if v["status"] == "ok")
    c_lists = agentic_candidates(which) if (llm.JOBS / agentic_kind(which)).exists() else {}
    out["costs"] = {"A_searches": oa_n, "A_usd_at_list_price": round(0.001 * oa_n, 4),
                    "C_units": len(c_lists), "C_queries": sum(len(v.get("queries", [])) for v in c_lists.values())}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"retrieval_v2_{which}.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["search", "jobs", "agentic", "eval"])
    ap.add_argument("--set", default="selection", choices=list(manifest.SETS))
    ap.add_argument("--judge", choices=list(JUDGES))
    ap.add_argument("--judges", nargs="+", choices=list(JUDGES))
    ap.add_argument("--matcher", default="A", choices=["A", "C"])
    a = ap.parse_args()
    if a.cmd == "search":
        search(a.set)
    elif a.cmd == "jobs":
        judge_jobs(a.set, a.judge, a.matcher)
    elif a.cmd == "agentic":
        agentic_jobs(a.set, tuple(a.judges or ["J0"]))
    else:
        r = evaluate(a.set, tuple(a.judges) if a.judges else None)
        for k, res in r["results"].items():
            print(k, {w: (res["recall"][w]["k"], res["recall"][w]["n"]) for w in WINDOWS}, res["states"],
                  "pass", res["pass_recall_gate"])
