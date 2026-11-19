"""Pre-registered analysis. Rebuilds every number in results/ from committed outputs.

    python -m discovery.analysis --set main
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

from . import llm
from .budget import Ledger
from .study import DATA, METHODS, RESULTS, SHORTLIST, collect_judgments, jload, read_jsonl

ALPHA = 0.05
PRIMARY = ("G", "R")                     # practical workflow comparison
KEY_SECONDARY = [("G", "P"), ("G", "RN")]  # path-ranking ablation; comparison under a shared filter
OTHER_SECONDARY = [("G", "B"), ("R", "B"), ("RN", "B")]
BOOT = 10_000
SEED = 11


def per_question_rates(rows, qids, metric="hit"):
    """Hit rate per (question, method) with a fixed denominator of SHORTLIST slots."""
    rate = {m: {} for m in METHODS}
    for q in qids:
        for m in METHODS:
            rs = [r for r in rows if r["qid"] == q and r["method"] == m]
            rate[m][q] = sum(1 for r in rs if r.get(metric) is True) / SHORTLIST
    return rate


def paired_test(x: np.ndarray, y: np.ndarray) -> dict:
    d = x - y
    rng = np.random.default_rng(SEED)
    boots = rng.choice(d, size=(BOOT, len(d)), replace=True).mean(1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    nz = d[d != 0]
    if len(nz) == 0:
        p, rbc = 1.0, 0.0
    else:
        res = stats.wilcoxon(x, y, zero_method="pratt", alternative="two-sided")
        p = float(res.pvalue)
        ranks = stats.rankdata(np.abs(nz))
        rbc = float((ranks[nz > 0].sum() - ranks[nz < 0].sum()) / ranks.sum())
    return {"mean_a": float(x.mean()), "mean_b": float(y.mean()), "mean_diff": float(d.mean()),
            "ci95": [float(lo), float(hi)], "p": p, "rank_biserial": rbc,
            "n_questions": int(len(d)), "n_nonzero": int(len(nz)),
            "wins_a": int((d > 0).sum()), "wins_b": int((d < 0).sum()), "ties": int((d == 0).sum())}


def holm(ps: list[float]) -> list[float]:
    order = np.argsort(ps)
    adj = [0.0] * len(ps)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj


def verdict(t: dict, a: str, b: str) -> str:
    if t["p"] < ALPHA:
        return f"{a} beats {b}" if t["mean_diff"] > 0 else f"{b} beats {a}"
    return "no detectable difference"


def descriptives(rows, engine_df=None):
    out = {}
    for m in METHODS:
        rs = [r for r in rows if r["method"] == m]
        n = len(rs)
        if not n:
            continue
        pre = [r for r in rs if r.get("pre2020_match") is True]
        noearlier = [r for r in rs if r.get("pre2020_match") is False]
        post_any = [r for r in rs if r.get("post2019_match") is True]
        hits = [r for r in rs if r.get("hit") is True]
        cross = [r for r in rs if r.get("cross_field") is True]
        within = [r for r in rs if r.get("cross_field") is False]
        concepts = [c for r in rs for c in (r["a"], r["b"]) if c]
        pop = [math.log(engine_df[c]) for c in concepts if engine_df and c in engine_df]
        out[m] = {
            "n_ideas": n,
            "mean_ideas_per_question": n / len({r["qid"] for r in rs}),
            "shortlist_fill_rate": n / (SHORTLIST * len({r["qid"] for r in rs})),
            "share_with_graph_path": (sum(1 for r in rs if r.get("has_path")) / n) if m in ("G", "P") else None,
            "share_studied_by_2019": len(pre) / n,
            "share_no_earlier_match": len(noearlier) / n,
            "share_later_match_any": len(post_any) / n,
            "hit_share_of_ideas": len(hits) / n,
            "hit_rate_among_no_earlier_match": (sum(1 for r in noearlier if r.get("hit")) / len(noearlier)) if noearlier else None,
            "share_cooccur_zero_in_corpus": sum(1 for r in rs if r.get("cooccur_pre2020") == 0) / n,
            "share_unmapped_concepts": sum(1 for r in rs if not (r["a"] and r["b"])) / n,
            "mean_log_concept_freq_pre2020": float(np.mean(pop)) if pop else None,
            "share_cross_field": len(cross) / n,
            "hit_rate_cross_field": (sum(1 for r in cross if r.get("hit")) / len(cross)) if cross else None,
            "hit_rate_within_field": (sum(1 for r in within if r.get("hit")) / len(within)) if within else None,
            "distinct_concepts_per_idea": len(set(concepts)) / max(1, n),
            "mean_post2019_comention_count": float(np.mean([r.get("post2019_count", 0) for r in rs])),
            "mean_pre2020_comention_count": float(np.mean([r.get("pre2020_count", 0) for r in rs])),
        }
    return out


def judge_agreement() -> dict | None:
    j1, j2 = collect_judgments("judge"), collect_judgments("judge2")
    pairs = [(j1[k][w]["match"], j2[k][w]["match"]) for k in j2 for w in j2[k] if k in j1 and w in j1[k]]
    if not pairs:
        return None
    agree = sum(1 for a, b in pairs if bool(a) == bool(b))
    a = np.array([bool(x) for x, _ in pairs]); b = np.array([bool(y) for _, y in pairs])
    po = agree / len(pairs)
    pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    return {"n": len(pairs), "agreement": po, "cohen_kappa": float(kappa)}


def leakage(rows) -> dict | None:
    d = llm.JOBS / "leak_out"
    if not d.exists():
        return None
    ans = {}
    for p in d.glob("*.json"):
        for a in llm.parse_json(p.read_text())["answers"]:
            ans[a["item_id"]] = a
    if not ans:
        return None
    truth = {}
    for r in rows:
        if r.get("pair_key") and r["method"] != "B" and r.get("hit") is not None:
            truth[r["pair_key"]] = (r["pre2020_match"], r["post2019_match"])
    res = {}
    for i, key in enumerate(["before_2020", "in_2020_2024"]):
        tp = fp = fn = tn = unsure = 0
        for k, t in truth.items():
            if k not in ans:
                continue
            g = ans[k][key]
            if g == "unsure":
                unsure += 1
                continue
            y, pred = t[i], g == "yes"
            tp += y and pred; fp += (not y) and pred; fn += y and not pred; tn += (not y) and not pred
        n = tp + fp + fn + tn
        res[key] = {"n_answered": n, "n_unsure": unsure, "accuracy": (tp + tn) / n if n else None,
                    "recall_of_true_matches": tp / (tp + fn) if tp + fn else None,
                    "precision": tp / (tp + fp) if tp + fp else None,
                    "base_rate_true": (tp + fn) / n if n else None}
    # Among hits specifically: did the model 'know' about the later study?
    hits = [k for k, t in truth.items() if t == (False, True) and k in ans]
    res["hits_model_says_studied_2020_2024"] = (
        sum(1 for k in hits if ans[k]["in_2020_2024"] == "yes") / len(hits) if hits else None)
    res["n_hits_probed"] = len(hits)
    return res


def citation_accuracy() -> dict | None:
    d = llm.JOBS / "cite_out"
    if not d.exists():
        return None
    meta = {}
    for p in (llm.JOBS / "cite").glob("*.json"):
        meta.update(llm.read_meta("cite", p.stem)["methods"])
    by = defaultdict(lambda: defaultdict(int))
    for p in d.glob("*.json"):
        for j in llm.parse_json(p.read_text())["judgments"]:
            m = meta.get(j["item_id"])
            if m:
                by[m][j["supported"]] += 1
    return {m: {k: v / sum(c.values()) for k, v in c.items()} | {"n": sum(c.values())} for m, c in by.items()}


def cost() -> dict:
    led = Ledger(DATA / "budget_ledger.json")
    s = led.summary()
    setup_path = DATA / "setup_cost.json"
    if setup_path.exists():
        s["_setup"] = jload(setup_path)
    return s


def figures(rates, qids, out: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rng = np.random.default_rng(SEED)
    means, los, his = [], [], []
    for m in METHODS:
        x = np.array([rates[m][q] for q in qids])
        b = rng.choice(x, size=(BOOT, len(x)), replace=True).mean(1)
        means.append(x.mean()); los.append(x.mean() - np.percentile(b, 2.5)); his.append(np.percentile(b, 97.5) - x.mean())
    labels = {"G": "Graph paths", "P": "Pairwise graph", "R": "Retrieval +\nbrainstorm",
              "RN": "Retrieval +\nnovelty filter", "B": "Popularity\n(no LLM)"}
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([labels[m] for m in METHODS], means, yerr=[los, his], capsize=4, color="#4C72B0")
    ax.set_ylabel("Retrospective match rate (of 10 slots)")
    ax.set_title("No earlier match found, later match found (2020–2024)")
    fig.tight_layout(); fig.savefig(out / "hit_rate_by_method.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for a, b, col in [("G", "R", "#C44E52"), ("G", "RN", "#55A868")]:
        d = np.array([rates[a][q] - rates[b][q] for q in qids])
        ax.scatter(range(len(d)), sorted(d), s=14, label=f"{a} − {b}", color=col)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("Questions (sorted by difference)"); ax.set_ylabel("Difference in retrospective match rate")
    ax.legend(); fig.tight_layout(); fig.savefig(out / "paired_differences.png", dpi=150); plt.close(fig)


def run(qset: str = "main") -> dict:
    rows = read_jsonl(DATA / f"labelled_{qset}.jsonl")
    qids = [q["qid"] for q in jload(DATA / "questions.json")[qset]]
    unjudged = sum(1 for r in rows if r.get("hit") is None)
    try:
        from .engine import Engine
        df = Engine.load().graph.df
    except Exception:
        df = None
    rates = per_question_rates(rows, qids)
    arr = {m: np.array([rates[m][q] for q in qids]) for m in METHODS}
    primary = paired_test(arr[PRIMARY[0]], arr[PRIMARY[1]])
    primary["verdict"] = verdict(primary, *PRIMARY)
    key = {}
    for a, b in KEY_SECONDARY:
        t = paired_test(arr[a], arr[b])
        t["verdict"] = verdict(t, a, b)
        key[f"{a}_vs_{b}"] = t
    others = {f"{a}_vs_{b}": paired_test(arr[a], arr[b]) for a, b in OTHER_SECONDARY}
    adj = holm([t["p"] for t in others.values()])
    for (k, t), pa in zip(others.items(), adj):
        t["p_holm"] = pa
        a, b = k.split("_vs_")
        t["verdict"] = verdict({**t, "p": pa}, a, b)
    by_field = {}
    for f in ("econ", "tran"):
        fq = [q for q in qids if q.startswith(f)]
        by_field[f] = {f"{a}_vs_{b}": paired_test(np.array([rates[a][q] for q in fq]),
                                                  np.array([rates[b][q] for q in fq]))
                       for a, b in [PRIMARY, *KEY_SECONDARY]}
    out = {
        "qset": qset, "n_ideas": len(rows), "n_unjudged": unjudged,
        "mean_hit_rate": {m: float(arr[m].mean()) for m in METHODS},
        "outcome_name": "retrospective match rate", "primary_G_vs_R": primary, "key_secondary": key, "other_secondary": others,
        "by_field": by_field, "descriptives": descriptives(rows, df),
        "judge_agreement": judge_agreement(), "leakage": leakage(rows),
        "citation_accuracy": citation_accuracy(), "cost": cost(),
        "per_question": {m: rates[m] for m in METHODS},
    }
    try:
        from . import controls
        if (DATA / "controls.json").exists():
            out["control_recall"] = controls.recall(collect_judgments("judge"))
    except Exception as exc:  # controls exist only for the pilot
        out["control_recall_error"] = str(exc)
    sa = RESULTS / "search_audit.json"
    if sa.exists():
        out["search_audit"] = jload(sa)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"analysis_{qset}.json").write_text(json.dumps(out, indent=1))
    figures(rates, qids, RESULTS)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="main")
    a = ap.parse_args()
    res = run(a.set)
    print(json.dumps({k: res[k] for k in ["mean_hit_rate", "primary_G_vs_R", "key_secondary"]}, indent=1))
