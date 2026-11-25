"""Evaluate matchers on the selection set or (after the committed decision) the holdout. Amendment 4.

    python -m discovery.matcher_eval --set selection
    python -m discovery.matcher_eval --set holdout --matcher X
"""
from __future__ import annotations

import argparse
import json

from scipy import stats

from . import llm
from .matchers import agentic_candidates, units
from .study import DATA, RESULTS, jload

WINDOWS = ("pre2020", "post2019")
GATES = {"recall": 0.80, "precision": 0.90, "audit_miss": 0.20}
SELECTABLE = ("A", "B", "C", "D")


def cp(k: int, n: int) -> dict:
    """Exact Clopper-Pearson 95% interval."""
    if n == 0:
        return {"k": 0, "n": 0, "rate": None, "ci95": [None, None]}
    lo = 0.0 if k == 0 else float(stats.beta.ppf(0.025, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(0.975, k + 1, n - k))
    return {"k": k, "n": n, "rate": k / n, "ci95": [round(lo, 4), round(hi, 4)]}


def judgments(which: str) -> dict:
    kind = f"judge_m_{which}"
    out = {}
    for p in sorted((llm.JOBS / kind).glob("*.json")) if (llm.JOBS / kind).exists() else []:
        op = llm.JOBS / f"{kind}_out" / p.name
        if not op.exists():
            continue
        idm = llm.read_meta(kind, p.stem)["id_map"]
        for j in llm.parse_json(op.read_text())["judgments"]:
            if j["item_id"] in idm:
                out[idm[j["item_id"]]] = j
    return out


ERROR = "error"  # explicit state (C03): a failed search or an invalid judgment never counts as a miss or a pass


def matched(J: dict, m: str, uid: str):
    """True/False if judged; None if not yet judged; ERROR if the judgment is not a JSON boolean."""
    j = J.get(f"RET::{m}::{uid}")
    if j is None:
        return None
    return j["match"] if isinstance(j.get("match"), bool) else ERROR


def evaluate(which: str, only: str | None = None) -> dict:
    U = units(which)
    J = judgments(which)
    store = jload(DATA / f"matcher_candidates_{which}.json") if (DATA / f"matcher_candidates_{which}.json").exists() else {}
    C = agentic_candidates(which)
    audit = {}
    sa = jload(DATA.parent / "results" / "search_audit.json")
    for it in sa["items"]:
        audit[(it["item_id"], "pre2020")] = bool(it["audit_pre"]["found"])
        audit[(it["item_id"], "post2019")] = bool(it["audit_post"]["found"])

    def result(m, uid):
        """True (match), False (completed miss), None (pending) or ERROR."""
        if m == "D":  # C runs only after a *completed* A miss; A pending/error stays pending/error (C03)
            a = result("A", uid)
            return a if a is not False else result("C", uid)
        if m == "C":
            if uid not in C:
                return None
            if not C[uid]["papers"]:
                return False
        else:
            key = f"{m}::{uid}"
            if key not in store:
                return None
            if any("error" in c for c in store[key]):
                return ERROR
            if not store[key]:
                return False
        return matched(J, m, uid)

    def source_found(m, u):
        sid = u["source"]["id"]
        if m == "D":
            return source_found("A", u) or source_found("C", u)
        cands = C.get(u["uid"], {}).get("papers", []) if m == "C" else store.get(f"{m}::{u['uid']}", [])
        return any(c.get("id") == sid for c in cands)

    names = [only] if only else list(SELECTABLE) + ["S"]
    out = {"set": which, "matchers": {}}
    for m in names:
        res = {"retrieval": {}, "retrieval_source_found": {}, "audit": {}, "pending": 0, "errors": 0, "audit_pending": 0}
        for w in WINDOWS:
            pcs = [u for u in U["positive_controls"] if u["window"] == w]
            rs = [result(m, u["uid"]) for u in pcs]
            res["pending"] += sum(r is None for r in rs)
            res["errors"] += sum(r == ERROR for r in rs)
            res["retrieval"][w] = cp(sum(r is True for r in rs), sum(isinstance(r, bool) for r in rs))
            res["retrieval_source_found"][w] = cp(sum(source_found(m, u) for u in pcs), len(pcs))
            aus = [u for u in U["audit_pairs"] if u["window"] == w]
            ars = [result(m, u["uid"]) for u in aus]
            res["audit_pending"] += sum(r is None for r in ars)
            res["errors"] += sum(r == ERROR for r in ars)
            no_match = [u for u in aus if result(m, u["uid"]) is False]
            found_anyway = sum(audit.get((u["pair_key"], w), False) for u in no_match)
            has_ref = [u for u in aus if audit.get((u["pair_key"], w))]
            res["audit"][w] = {"miss_rate_among_matcher_no_match": cp(found_anyway, len(no_match)),
                               "recall_vs_audit": cp(sum(result(m, u["uid"]) is True for u in has_ref), len(has_ref))}
        out["matchers"][m] = res
    # classification (production judge; matcher-independent)
    pos = [J.get(f"CLS::{u['uid']}") for u in U["classification_positives"]]
    neg = [J.get(f"CLS::{u['uid']}") for u in U["hard_negatives"]]
    bad = sum(1 for j in pos + neg if j is not None and not isinstance(j.get("match"), bool))
    pos = [j if j is None or isinstance(j.get("match"), bool) else None for j in pos]
    neg = [j if j is None or isinstance(j.get("match"), bool) else None for j in neg]
    tp = sum(1 for j in pos if j and j["match"]); fn = sum(1 for j in pos if j and not j["match"])
    fp = sum(1 for j in neg if j and j["match"]); tn = sum(1 for j in neg if j and not j["match"])
    out["classification"] = {"precision": cp(tp, tp + fp), "recall": cp(tp, tp + fn),
                             "specificity_on_hard_negatives": cp(tn, tn + fp),
                             "pending": sum(j is None for j in pos + neg) - bad, "errors": bad}
    # gates
    cl = out["classification"]
    prec_ok = (cl["precision"]["rate"] or 0) >= GATES["precision"] and cl["pending"] == 0 and cl["errors"] == 0
    for m, res in out["matchers"].items():
        rec_ok = all((res["retrieval"][w]["rate"] or 0) >= GATES["recall"] for w in WINDOWS)
        miss = [res["audit"][w]["miss_rate_among_matcher_no_match"]["rate"] for w in WINDOWS]
        # declared rule: an undefined miss rate (the matcher left no audit pair unmatched) passes only when
        # every audit unit is complete; unfinished audit work never passes (C03)
        audit_ok = res["audit_pending"] == 0 and all(x is None or x <= GATES["audit_miss"] for x in miss)
        complete = res["pending"] == 0 and res["errors"] == 0
        binding_audit = m in ("A", "B")
        res["gates"] = {"recall": rec_ok, "precision": prec_ok, "audit_miss": audit_ok, "complete": complete,
                        "audit_binding": binding_audit,
                        "pass": bool(complete and rec_ok and prec_ok and (audit_ok or not binding_audit))
                        if m != "S" else None}
    out["costs"] = costs(which)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"matcher_validation_{which}.json").write_text(json.dumps(out, indent=1))
    return out


def costs(which: str) -> dict:
    """Per-matcher OpenAlex requests and recorded subagent tokens (results/subagent_usage.json)."""
    store = jload(DATA / f"matcher_candidates_{which}.json") if (DATA / f"matcher_candidates_{which}.json").exists() else {}
    C = agentic_candidates(which)
    n_units = len({k.split("::", 1)[1] for k in store}) or len(C) or 1
    usage = jload(RESULTS / "subagent_usage.json") if (RESULTS / "subagent_usage.json").exists() else {}
    u = usage.get(which, {})
    c_queries = sum(len(v.get("queries", [])) for v in C.values())
    out = {}
    for m in ("A", "B", "S"):
        out[m] = {"openalex_usd_per_unit": 0.001, "judge_tokens_per_unit": u.get("judge_tokens_per_item")}
    out["C"] = {"openalex_usd_per_unit": round(0.001 * c_queries / max(1, len(C)), 5),
                "search_tokens_per_unit": (u.get("agentic_tokens", 0) / max(1, len(C))) if u.get("agentic_tokens") else None,
                "judge_tokens_per_unit": u.get("judge_tokens_per_item"), "mean_queries_per_unit": c_queries / max(1, len(C))}
    out["D"] = {"note": "A cost for every unit + C cost for units where A found no judged match"}
    out["n_units"] = n_units
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="selection", choices=["selection", "holdout"])
    ap.add_argument("--matcher")
    a = ap.parse_args()
    r = evaluate(a.set, a.matcher)
    for m, res in r["matchers"].items():
        print(m, {w: (res["retrieval"][w]["k"], res["retrieval"][w]["n"]) for w in WINDOWS}, res["gates"], "pending", res["pending"])
    print("classification", r["classification"])
