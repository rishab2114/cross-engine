"""Deployment-sample validation of the judges (review finding C01; Amendment 6, part 6). Descriptive, not a gate.

    python -m discovery.deploy_sample build   # stratified sample of actual pilot A candidate lists + all jobs
    python -m discovery.deploy_sample eval    # results/deployment_validation_c01.json

Population: the matcher-A candidate lists of the 100 pilot ideas (data/pair_candidates_A.json), i.e. the
lists the production pipeline actually judged. Stratified by window x generating method, 4 lists per stratum
(seed 6161). Every paper in a sampled list is included with the same text the judges saw.
Reference: two independent adjudication orderings (prompts/adjudicate.md); agreed labels only.
Judgments: J0 and J1 per paper (new jobs); per list, J0 from the committed pilot rescoring (same prompt)
and J1 from new list jobs. Reported with Clopper-Pearson intervals and the observed prevalence.
"""
from __future__ import annotations

import argparse
import json
import random

from . import llm
from .budget import est_tokens
from .contracts import SchemaError, parse_judgments
from .matcher_eval import cp
from .study import DATA, RESULTS, jdump, jload, opaque_id, read_jsonl, render_items

SEED = 6161
PER_STRATUM = 4
WINDOWS = ("pre2020", "post2019")
METHODS = ("G", "P", "R", "RN", "B")
SAMPLE = DATA / "deploy_sample_c01.json"
ADJ_TAGS = {"dep_adj_a": 1, "dep_adj_b": 2}
CLS = {"J0": "judge_match.md", "J1": "judge_match_quote.md"}
PER_JOB = 12


def sample() -> dict:
    if SAMPLE.exists():
        return jload(SAMPLE)
    rows = read_jsonl(DATA / "labelled_pilot_A.jsonl")
    pc = jload(DATA / "pair_candidates_A.json")
    rng = random.Random(SEED)
    lists = []
    for m in METHODS:
        for w in WINDOWS:
            pool = sorted((r for r in rows if r["method"] == m and pc.get(r["pair_key"], {}).get(w, {}).get("count", 0) > 0),
                          key=lambda r: r["idea_id"])
            for r in rng.sample(pool, min(PER_STRATUM, len(pool))):
                lists.append({"lid": f"{r['idea_id']}::{w}", "idea_id": r["idea_id"], "method": m, "window": w,
                              "a": r["a"], "b": r["b"], "pair_key": r["pair_key"],
                              "papers": pc[r["pair_key"]][w]["candidates"],
                              "J0_list_match": r[f"{w}_match"], "J0_list_judged": r[f"{w}_judged"]})
    s = {"seed": SEED, "per_stratum": PER_STRATUM, "population_lists": sum(
        1 for r in rows for w in WINDOWS if pc.get(r["pair_key"], {}).get(w, {}).get("count", 0) > 0),
        "lists": lists}
    jdump(SAMPLE, s)
    return s


def paper_items(s: dict) -> list[dict]:
    return [{"key": f"{l['lid']}::{p['id']}", "A": l["a"], "B": l["b"], "paper": p, "window": l["window"]}
            for l in s["lists"] for p in l["papers"]]


def _render_adj(items):
    return "\n\n".join(
        f"ITEM {it['item_id']}\nA = {it['A']}\nB = {it['B']}\nPaper [{it['paper']['id']}] ({it['paper']['year']}) "
        f"{it['paper']['title']}. {it['paper']['abstract']}" for it in items)


def _write(kind: str, items: list[dict], render, template: str, per_job: int = PER_JOB) -> int:
    items = sorted(items, key=lambda x: x["item_id"])
    random.Random(llm.stable_seed(kind)).shuffle(items)
    n, i = 0, 0
    while i < len(items):
        batch = items[i:i + per_job]
        prompt = llm.template(template).format(items=render(batch))
        while est_tokens(prompt) >= 30_000 and len(batch) > 1:
            batch = batch[:-1]
            prompt = llm.template(template).format(items=render(batch))
        llm.write_job(kind, f"{kind}_{n:02d}", prompt, {"id_map": {b["item_id"]: b["key"] for b in batch}})
        n += 1
        i += len(batch)
    return n


def build() -> None:
    s = sample()
    P = paper_items(s)
    for tag in ADJ_TAGS:
        its = [{**p, "item_id": opaque_id(tag, p["key"])} for p in P]
        print(tag, _write(tag, its, _render_adj, "adjudicate.md"), "jobs")
    for j, tmpl in CLS.items():
        kind = f"dep_cls_{j}"
        its = [{"key": p["key"], "item_id": opaque_id(kind, p["key"]), "A": p["A"], "B": p["B"],
                "windows": {p["window"]: [p["paper"]]}} for p in P]
        print(kind, _write(kind, its, render_items, tmpl), "jobs")
    kind = "dep_list_J1"
    its = [{"key": l["lid"], "item_id": opaque_id(kind, l["lid"]), "A": l["a"], "B": l["b"],
            "windows": {l["window"]: l["papers"]}} for l in s["lists"]]
    print(kind, _write(kind, its, render_items, CLS["J1"], per_job=8), "jobs")
    print(len(s["lists"]), "lists,", len(P), "papers")


def _adj(tag: str) -> dict:
    out = {}
    for p in sorted((llm.JOBS / tag).glob("*.json")) if (llm.JOBS / tag).exists() else []:
        op = llm.JOBS / f"{tag}_out" / p.name
        if not op.exists():
            continue
        idm = llm.read_meta(tag, p.stem)["id_map"]
        for l in llm.parse_json(op.read_text())["labels"]:
            if l.get("item_id") in idm and l.get("label") in ("explicit", "mention_only", "not_both", "unclear"):
                out[idm[l["item_id"]]] = l["label"]
    return out


def _judged(kind: str, items: dict, quote: bool) -> tuple[dict, list]:
    out, errs = {}, []
    for p in sorted((llm.JOBS / kind).glob("*.json")) if (llm.JOBS / kind).exists() else []:
        op = llm.JOBS / f"{kind}_out" / p.name
        if not op.exists():
            continue
        try:
            llm.check_provenance(kind, p.stem)
            r = parse_judgments(op.read_text(), llm.read_meta(kind, p.stem)["id_map"], items, quote_judge=quote)
        except (SchemaError, llm.JobConflict) as exc:
            errs.append((p.name, str(exc)))
            continue
        out.update({k: v["match"] for k, v in r.items()})
    return out, errs


def _metrics(pred: dict, truth: dict) -> dict:
    ks = [k for k in truth if k in pred]
    tp = sum(pred[k] and truth[k] for k in ks); fp = sum(pred[k] and not truth[k] for k in ks)
    fn = sum(not pred[k] and truth[k] for k in ks); tn = sum(not pred[k] and not truth[k] for k in ks)
    return {"n": len(ks), "precision": cp(tp, tp + fp), "sensitivity": cp(tp, tp + fn),
            "specificity": cp(tn, tn + fp), "pending": len(truth) - len(ks)}


def evaluate() -> dict:
    s = sample()
    P = paper_items(s)
    la, lb = _adj("dep_adj_a"), _adj("dep_adj_b")
    both = [p["key"] for p in P if p["key"] in la and p["key"] in lb]
    agreed = {k: la[k] == "explicit" for k in both
              if la[k] == lb[k] and la[k] != "unclear" or ({la[k], lb[k]} <= {"mention_only", "not_both"})}
    contested = [k for k in both if k not in agreed]
    cats = ("explicit", "mention_only", "not_both", "unclear")
    n = len(both)
    po = sum(la[k] == lb[k] for k in both) / n if n else None
    pe = sum((sum(la[k] == c for k in both) / n) * (sum(lb[k] == c for k in both) / n) for c in cats) if n else None
    items = {p["key"]: {"windows": {p["window"]: [p["paper"]]}} for p in P}
    out = {"n_lists": len(s["lists"]), "n_papers": len(P), "population_lists": s["population_lists"],
           "adjudication": {"both_labelled": n, "raw_agreement": po,
                            "cohen_kappa": (po - pe) / (1 - pe) if n and pe < 1 else None,
                            "agreed": len(agreed), "contested": len(contested),
                            "agreed_explicit": sum(agreed.values()),
                            "paper_prevalence": cp(sum(agreed.values()), len(agreed))},
           "paper_level": {}, "pair_window": {}, "invalid_outputs": {}}
    for j in CLS:
        pred, errs = _judged(f"dep_cls_{j}", items, quote=(j == "J1"))
        out["paper_level"][j] = _metrics(pred, agreed)
        if errs:
            out["invalid_outputs"][f"dep_cls_{j}"] = errs
        out["paper_level"][j]["by_window"] = {w: _metrics(pred, {k: v for k, v in agreed.items()
                                                                 if k.split("::")[1] == w}) for w in WINDOWS}
    # pair-window reference: explicit if any agreed-explicit paper; negative only if every paper is agreed non-explicit
    ref = {}
    for l in s["lists"]:
        ks = [f"{l['lid']}::{p['id']}" for p in l["papers"]]
        if any(agreed.get(k) for k in ks):
            ref[l["lid"]] = True
        elif all(k in agreed for k in ks):
            ref[l["lid"]] = False
    j0 = {l["lid"]: bool(l["J0_list_match"]) for l in s["lists"] if l["J0_list_judged"]}
    litems = {l["lid"]: {"windows": {l["window"]: l["papers"]}} for l in s["lists"]}
    j1, errs = _judged("dep_list_J1", litems, quote=True)
    if errs:
        out["invalid_outputs"]["dep_list_J1"] = errs
    both_j = {k: j0[k] and j1[k] for k in j0 if k in j1}
    out["pair_window"] = {"reference_defined": len(ref), "reference_contested": len(s["lists"]) - len(ref),
                          "prevalence": cp(sum(ref.values()), len(ref)),
                          "J0": _metrics(j0, ref), "J1": _metrics(j1, ref), "J0_and_J1": _metrics(both_j, ref)}
    out["pair_window"]["by_method_J0"] = {m: _metrics(j0, {k: v for k, v in ref.items()
                                                          if next(l["method"] for l in s["lists"] if l["lid"] == k) == m})
                                          for m in METHODS}
    p0 = out["pair_window"]["J0"]["precision"]["rate"]
    out["prefixed_interpretation"] = (None if p0 is None else "J0 supported for deployment use" if p0 >= 0.90 else
                                      "borderline" if p0 >= 0.80 else
                                      "J0 alone not adequate for main-run claims; stricter rule recommended")
    out["label"] = "model-referenced (same-family adjudicators): repeatability evidence, not independent validation"
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "deployment_validation_c01.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "eval"])
    a = ap.parse_args()
    build() if a.cmd == "build" else print(json.dumps(evaluate(), indent=1)[:3000])
