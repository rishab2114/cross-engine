"""Judge repair (Amendment 5): build classification jobs for J0/J1 runs and evaluate J0-J3.

    python -m discovery.judge_eval jobs --set selection     # J0 run1/run2 and J1 run1/run2 job files
    python -m discovery.judge_eval eval --set selection     # results/judge_validation_<set>_v2.json
    python -m discovery.judge_eval jobs --set holdout       # only the frozen manifest's judge (C02)
    python -m discovery.judge_eval eval --set holdout

Selection mode compares candidates. Holdout mode accepts only data/run_manifest_v2.json: one judge,
its repetitions, no detectors, no cascade and no re-selection, with Amendment 6's overlap exclusion.
Outputs are parsed strictly (contracts.parse_judgments); invalid outputs are counted as errors and
block the gate.

Note (C04): the selection-v2 job files were written with a process-randomised shuffle seed and are
frozen with their outputs. Regenerating them now raises llm.JobConflict; that is intended.
"""
from __future__ import annotations

import argparse
import json
import random

from . import llm, manifest
from .budget import est_tokens
from .contracts import SchemaError, exclude_overlap, parse_judgments
from .matcher_eval import cp
from .study import DATA, RESULTS, jload, opaque_id, render_items

JUDGES = {"J0": "judge_match.md", "J1": "judge_match_quote.md"}
GATES = {"precision": 0.90, "recall": 0.80}
COST_ORDER = ["J4", "J5", "J0", "J1", "J2", "J3"]  # detectors cost ~$0 per item
PER_JOB = 10
SELECTION_FILE = DATA / "units_v2_selection.json"
HOLDOUT_FILE = DATA / "holdout_sealed_v2" / "units_v2_holdout.json"


def units(which: str) -> dict:
    manifest.check_set(which)
    if which == "selection":
        return jload(SELECTION_FILE)
    manifest.load()  # refuses a missing, edited or incomplete manifest (judge AND matcher required)
    kept, _ = exclude_overlap(jload(HOLDOUT_FILE), jload(SELECTION_FILE))
    return kept


def excluded_holdout_uids() -> list[str]:
    manifest.load()
    return exclude_overlap(jload(HOLDOUT_FILE), jload(SELECTION_FILE))[1]


def items(U: dict) -> list[dict]:
    out = []
    for t in ("positives", "hard_negatives"):
        for u in U[t]:
            out.append({"key": u["uid"], "A": u["a"], "B": u["b"], "windows": {u["window"]: [u["paper"]]},
                        "truth": t == "positives"})
    return out


def plan(which: str) -> dict:
    """Judge -> runs to queue. Holdout: only the frozen judge, only its frozen repetitions."""
    if which == "holdout":
        m = manifest.load()
        return {m["judge"]: tuple(range(1, m["repetitions"] + 1))}
    return {j: (1, 2) for j in JUDGES}


def write_jobs(which: str) -> None:
    its = items(units(which))
    for judge, runs in plan(which).items():
        for run in runs:
            kind = f"cls_{judge}_r{run}_{which}"
            batch_items = [dict(i) for i in its]
            for it in batch_items:
                it["item_id"] = opaque_id(kind, it["key"])
            batch_items.sort(key=lambda x: x["item_id"])
            # stable across processes (C04)
            random.Random(llm.stable_seed(judge, run, which)).shuffle(batch_items)
            for j in range(0, len(batch_items), PER_JOB):
                b = batch_items[j:j + PER_JOB]
                prompt = llm.template(JUDGES[judge]).format(items=render_items(b))
                assert est_tokens(prompt) < 30_000
                llm.write_job(kind, f"{kind}_{j // PER_JOB:02d}", prompt, {"id_map": {x["item_id"]: x["key"] for x in b}})
            print(kind, (len(batch_items) + PER_JOB - 1) // PER_JOB, "jobs")


def verdicts(kind: str, its: dict | None = None) -> tuple[dict, list]:
    """key -> bool for every answered job (strictly validated), plus a list of (job, error) for invalid outputs."""
    out, errors = {}, []
    d = llm.JOBS / kind
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        op = llm.JOBS / f"{kind}_out" / p.name
        if not op.exists():
            continue
        try:
            llm.check_provenance(kind, p.stem)
            r = parse_judgments(op.read_text(), llm.read_meta(kind, p.stem)["id_map"], its,
                                quote_judge=kind.startswith("cls_J1"))
        except (SchemaError, llm.JobConflict) as exc:
            errors.append((p.name, str(exc)))
            continue
        out.update({k: v["match"] for k, v in r.items()})
    return out, errors


def _rates(its: dict, d: dict) -> dict:
    res = {}
    for w in ("all", "pre2020", "post2019"):
        ks = [k for k in its if k in d and (w == "all" or list(its[k]["windows"])[0] == w)]
        tp = sum(1 for k in ks if d[k] and its[k]["truth"]); fp = sum(1 for k in ks if d[k] and not its[k]["truth"])
        fn = sum(1 for k in ks if not d[k] and its[k]["truth"]); tn = sum(1 for k in ks if not d[k] and not its[k]["truth"])
        res[w] = {"precision": cp(tp, tp + fp), "recall": cp(tp, tp + fn), "specificity": cp(tn, tn + fp),
                  "n_judged": len(ks)}
    return res


def evaluate(which: str) -> dict:
    manifest.check_set(which)
    its = {i["key"]: i for i in items(units(which))}
    runs = plan(which)
    v, errs = {}, {}
    for j, rs in runs.items():
        for r in rs:
            v[f"{j}_r{r}"], errs[f"{j}_r{r}"] = verdicts(f"cls_{j}_r{r}_{which}", its)
    if which == "holdout":
        m = manifest.load()
        j, reps = m["judge"], m["repetitions"]
        d = v[f"{j}_r1"] if reps == 1 else {k: all(v[f"{j}_r{r}"].get(k) for r in range(1, reps + 1))
                                              for k in its if all(k in v[f"{j}_r{r}"] for r in range(1, reps + 1))}
        judged = {j: d}
    else:
        judged = {"J0": v["J0_r1"], "J1": v["J1_r1"],
                  "J2": {k: v["J0_r1"][k] and v["J0_r2"][k] for k in v["J0_r1"] if k in v["J0_r2"]},
                  "J3": {k: v["J1_r1"][k] and v["J1_r2"][k] for k in v["J1_r1"] if k in v["J1_r2"]}}
        det_path = DATA / f"detector_predictions_{which}_v2.json"
        if det_path.exists():
            det = jload(det_path)
            for name in ("J4", "J5"):
                judged[name] = {k: x["match"] for k, x in det[name].items()}
            # J6 cascade (exploratory, not selectable): J5 screens at p >= 0.05, then J1 decides
            judged["J6"] = {k: (det["J5"][k]["p"] >= 0.05 and v["J1_r1"][k]) for k in v["J1_r1"] if k in det["J5"]}
    n_err = sum(len(e) for e in errs.values())
    out = {"set": which, "n_items": len(its), "invalid_outputs": {k: e for k, e in errs.items() if e}, "judges": {}}
    if which == "holdout":
        out["frozen_manifest"] = {k: m[k] for k in ("judge", "repetitions", "matcher", "judge_prompt_sha256", "digest")}
        out["amendment6_excluded_uids"] = excluded_holdout_uids()
    for name, d in judged.items():
        res = _rates(its, d)
        a = res["all"]
        res["pending"] = len(its) - a["n_judged"]
        res["pass"] = bool(res["pending"] == 0 and n_err == 0 and (a["precision"]["rate"] or 0) >= GATES["precision"]
                           and (a["recall"]["rate"] or 0) >= GATES["recall"]) if name != "J6" else None
        out["judges"][name] = res
    for j, rs in runs.items():  # run-to-run stability
        if len(rs) >= 2:
            r1, r2 = v[f"{j}_r1"], v[f"{j}_r2"]
            ks = [k for k in r1 if k in r2]
            out["judges"].setdefault(j, {})["run_agreement"] = cp(sum(r1[k] == r2[k] for k in ks), len(ks))
    if which == "selection":  # selection only; holdout never re-selects
        passing = [j for j in COST_ORDER if j in out["judges"] and out["judges"][j].get("pass")]
        out["cheapest_passing"] = passing[0] if passing else None
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"judge_validation_{which}_v2.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["jobs", "eval"])
    ap.add_argument("--set", default="selection", choices=list(manifest.SETS))
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
        print("cheapest passing:", r.get("cheapest_passing"), "invalid outputs:", r["invalid_outputs"] or 0)
