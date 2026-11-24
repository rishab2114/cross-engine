"""Judge repair (Amendment 5): build classification jobs for J0/J1 runs and evaluate J0-J3.

    python -m discovery.judge_eval jobs --set selection     # J0 run1/run2 and J1 run1/run2 job files
    python -m discovery.judge_eval eval --set selection     # results/judge_validation_<set>_v2.json
"""
from __future__ import annotations

import argparse
import json
import random

from . import llm
from .budget import est_tokens
from .matcher_eval import cp
from .study import DATA, RESULTS, jload, opaque_id, render_items

JUDGES = {"J0": "judge_match.md", "J1": "judge_match_quote.md"}
GATES = {"precision": 0.90, "recall": 0.80}
COST_ORDER = ["J4", "J5", "J0", "J1", "J2", "J3"]  # detectors cost ~$0 per item
PER_JOB = 10


def units(which: str) -> dict:
    if which == "selection":
        return jload(DATA / "units_v2_selection.json")
    dec = DATA / "judge_selection_decision_v2.json"
    if not dec.exists() or jload(dec).get("chosen_judge") is None:
        raise SystemExit("Holdout v2 is sealed: no committed judge decision with a chosen judge.")
    return jload(DATA / "holdout_sealed_v2" / "units_v2_holdout.json")


def items(U: dict) -> list[dict]:
    out = []
    for t in ("positives", "hard_negatives"):
        for u in U[t]:
            out.append({"key": u["uid"], "A": u["a"], "B": u["b"], "windows": {u["window"]: [u["paper"]]},
                        "truth": t == "positives"})
    return out


def write_jobs(which: str) -> None:
    its = items(units(which))
    for judge, tmpl in JUDGES.items():
        for run in (1, 2):
            kind = f"cls_{judge}_r{run}_{which}"
            batch_items = [dict(i) for i in its]
            for it in batch_items:
                it["item_id"] = opaque_id(kind, it["key"])
            random.Random(hash((judge, run)) & 0xFFFF).shuffle(batch_items)
            for j in range(0, len(batch_items), PER_JOB):
                b = batch_items[j:j + PER_JOB]
                prompt = llm.template(tmpl).format(items=render_items(b))
                assert est_tokens(prompt) < 30_000
                llm.write_job(kind, f"{kind}_{j // PER_JOB:02d}", prompt, {"id_map": {x["item_id"]: x["key"] for x in b}})
            print(kind, (len(batch_items) + PER_JOB - 1) // PER_JOB, "jobs")


def verdicts(kind: str) -> dict:
    out = {}
    d = llm.JOBS / kind
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        op = llm.JOBS / f"{kind}_out" / p.name
        if not op.exists():
            continue
        idm = llm.read_meta(kind, p.stem)["id_map"]
        for j in llm.parse_json(op.read_text())["judgments"]:
            if j["item_id"] in idm:
                m = bool(j.get("match"))
                if kind.startswith("cls_J1") and m and not (j.get("quote") or "").strip():
                    m = False  # quote-anchored rule: no quote, no match
                out[idm[j["item_id"]]] = m
    return out


def evaluate(which: str) -> dict:
    its = {i["key"]: i for i in items(units(which))}
    v = {f"{j}_r{r}": verdicts(f"cls_{j}_r{r}_{which}") for j in JUDGES for r in (1, 2)}
    judged = {"J0": v["J0_r1"], "J1": v["J1_r1"],
              "J2": {k: v["J0_r1"][k] and v["J0_r2"][k] for k in v["J0_r1"] if k in v["J0_r2"]},
              "J3": {k: v["J1_r1"][k] and v["J1_r2"][k] for k in v["J1_r1"] if k in v["J1_r2"]}}
    det_path = DATA / f"detector_predictions_{which}_v2.json"
    if det_path.exists():
        det = jload(det_path)
        for name in ("J4", "J5"):
            judged[name] = {k: bool(x["match"]) for k, x in det[name].items()}
        # J6 cascade (exploratory, not selectable): J5 screens at p >= 0.05, then J1 decides
        judged["J6"] = {k: (det["J5"][k]["p"] >= 0.05 and v["J1_r1"][k]) for k in v["J1_r1"] if k in det["J5"]}
    out = {"set": which, "n_items": len(its), "judges": {}}
    for name, d in judged.items():
        res = {}
        for w in ("all", "pre2020", "post2019"):
            ks = [k for k in its if k in d and (w == "all" or list(its[k]["windows"])[0] == w)]
            tp = sum(1 for k in ks if d[k] and its[k]["truth"]); fp = sum(1 for k in ks if d[k] and not its[k]["truth"])
            fn = sum(1 for k in ks if not d[k] and its[k]["truth"]); tn = sum(1 for k in ks if not d[k] and not its[k]["truth"])
            res[w] = {"precision": cp(tp, tp + fp), "recall": cp(tp, tp + fn), "specificity": cp(tn, tn + fp),
                      "n_judged": len(ks)}
        a = res["all"]
        res["pending"] = len(its) - res["all"]["n_judged"]
        res["pass"] = bool(res["pending"] == 0 and (a["precision"]["rate"] or 0) >= GATES["precision"]
                           and (a["recall"]["rate"] or 0) >= GATES["recall"]) if name != "J6" else None
        out["judges"][name] = res
    # run-to-run stability
    for j in JUDGES:
        r1, r2 = v[f"{j}_r1"], v[f"{j}_r2"]
        ks = [k for k in r1 if k in r2]
        out["judges"].setdefault(j, {})["run_agreement"] = cp(sum(r1[k] == r2[k] for k in ks), len(ks))
    passing = [j for j in COST_ORDER if j in out["judges"] and out["judges"][j].get("pass")]
    out["cheapest_passing"] = passing[0] if passing else None
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"judge_validation_{which}_v2.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["jobs", "eval"])
    ap.add_argument("--set", default="selection")
    a = ap.parse_args()
    if a.cmd == "jobs":
        write_jobs(a.set)
    else:
        r = evaluate(a.set)
        for j, res in r["judges"].items():
            al = res.get("all", {})
            if al:
                print(j, "P", al["precision"]["k"], "/", al["precision"]["n"], al["precision"]["ci95"],
                      "R", al["recall"]["k"], "/", al["recall"]["n"], "pass", res["pass"], "pending", res["pending"])
        print("cheapest passing:", r["cheapest_passing"])
