"""Measurement-sensitivity analysis: how the estimated method differences change with the matcher.

Each measurement method is a labelled-ideas file for the 100 pilot ideas (or main set):
    fixed    -> data/labelled_pilot.jsonl          (preregistered fixed search)
    widened  -> data/labelled_pilot_widened.jsonl  (Amendment 1 widening rule)
    <name>   -> data/labelled_pilot_<name>.jsonl   (any later validated matcher)

    python -m discovery.sensitivity --set pilot
    python -m discovery.sensitivity hyp-jobs       # hypothesis-level judge jobs for pair-level later matches
"""
from __future__ import annotations

import argparse
import json
import random

import numpy as np

from . import llm
from .budget import est_tokens
from .study import DATA, METHODS, RESULTS, SHORTLIST, jload, opaque_id, read_jsonl

COMPARISONS = [("G", "R"), ("G", "P"), ("G", "RN"), ("G", "B"), ("R", "B")]
BOOT = 10_000
SEED = 17


def measurement_files(qset: str) -> dict[str, str]:
    out = {}
    for p in sorted(DATA.glob(f"labelled_{qset}*.jsonl")):
        name = p.stem.replace(f"labelled_{qset}", "").lstrip("_") or "fixed"
        out[name] = p
    return out


def rates(rows, qids, field="hit"):
    return {m: np.array([sum(1 for r in rows if r["qid"] == q and r["method"] == m and r.get(field) is True) / SHORTLIST
                         for q in qids]) for m in METHODS}


def boot_diff(x, y, rng):
    d = x - y
    if len(d) == 0:
        return None, [None, None]
    b = rng.choice(d, size=(BOOT, len(d)), replace=True).mean(1)
    return float(d.mean()), [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def idea_level_diff(rows, a, b, rng, field="hit"):
    """Pooled idea-level difference with an idea-level bootstrap (informative when questions are few)."""
    xa = np.array([r.get(field) is True for r in rows if r["method"] == a], float)
    xb = np.array([r.get(field) is True for r in rows if r["method"] == b], float)
    if not len(xa) or not len(xb):
        return None, [None, None]
    ba = rng.choice(xa, size=(BOOT, len(xa))).mean(1); bb = rng.choice(xb, size=(BOOT, len(xb))).mean(1)
    d = ba - bb
    return float(xa.mean() - xb.mean()), [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]


def run(qset: str = "pilot") -> dict:
    qids = [q["qid"] for q in jload(DATA / "questions.json")[qset]]
    files = measurement_files(qset)
    out = {"qset": qset, "n_questions": len(qids), "measurements": {}}
    for name, path in files.items():
        rows = read_jsonl(path)
        rng = np.random.default_rng(SEED)
        R = rates(rows, qids)
        meas = {"match_rate": {m: float(R[m].mean()) for m in METHODS},
                "studied_by_2019": {m: float(np.mean([r.get("pre2020_match") is True for r in rows if r["method"] == m]))
                                    for m in METHODS},
                "later_match_any": {m: float(np.mean([r.get("post2019_match") is True for r in rows if r["method"] == m]))
                                    for m in METHODS},
                "diffs": {}}
        for a, b in COMPARISONS:
            qd, qci = boot_diff(R[a], R[b], rng)
            idd, idci = idea_level_diff(rows, a, b, rng)
            meas["diffs"][f"{a}-{b}"] = {"question_level": qd, "question_level_ci95": qci,
                                         "idea_level": idd, "idea_level_ci95": idci}
        out["measurements"][name] = meas
    # direction flips
    flips = {}
    for a, b in COMPARISONS:
        k = f"{a}-{b}"
        signs = {n: np.sign(v["diffs"][k]["idea_level"] or 0) for n, v in out["measurements"].items()}
        flips[k] = {"signs": {n: int(s) for n, s in signs.items()}, "flips": len({s for s in signs.values() if s != 0}) > 1}
    out["direction_flips"] = flips
    hyp = hypothesis_level(qset)
    if hyp:
        out["hypothesis_level"] = hyp
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"measurement_sensitivity_{qset}.json").write_text(json.dumps(out, indent=1))
    return out


def corrected_hypotheses(qset: str) -> dict:
    """(qid, method, pair_key) -> hypothesis text re-attached to G/P pairs by name (see study.match_pair_ideas)."""
    from .study import match_pair_ideas, pair_key, questions
    out = {}
    for q in questions(qset):
        for m in ("G", "P"):
            jid = f"{q['qid']}__{m}"
            o = llm.read_output("gen", jid)
            if o is None:
                continue
            for idea in match_pair_ideas(o.get("ideas", []), llm.read_meta("gen", jid)["candidates"]):
                out[(q["qid"], m, pair_key(idea["a"], idea["b"]))] = idea.get("hypothesis")
    return out


def hyp_jobs(qset: str = "pilot", per_job: int = 10, kind: str = "hyp", corrected: bool = False) -> None:
    """For ideas with a pair-level later match under any measurement, ask whether the matched paper tests the hypothesis.
    corrected=True (kind "hyp_c") uses G/P hypothesis text re-attached to its pair by name (26 Nov correction)."""
    fix = corrected_hypotheses(qset) if corrected else {}
    files = measurement_files(qset)
    stores = {"fixed": jload(DATA / "pair_candidates.json"), "widened": jload(DATA / "pair_candidates_widened.json")}
    items, seen = [], set()
    for name, path in files.items():
        st = stores.get(name)
        if st is None:
            continue
        for r in read_jsonl(path):
            pid = r.get("post2019_paper")
            if r["method"] == "B" or not r.get("post2019_match") or not pid or not r.get("hypothesis"):
                continue
            key = f"{r['idea_id']}::{pid}"
            if key in seen:
                continue
            paper = next((c for c in st[r["pair_key"]]["post2019"]["candidates"] if c["id"] == pid), None)
            if not paper:
                continue
            seen.add(key)
            hyp = fix.get((r["qid"], r["method"], r["pair_key"]), r["hypothesis"]) if corrected else r["hypothesis"]
            if not hyp:
                continue
            items.append({"key": key, "hyp": hyp, "paper": paper})
    for it in items:
        it["item_id"] = opaque_id(kind, it["key"])
    random.Random(SEED).shuffle(items)
    for i in range(0, len(items), per_job):
        part = items[i:i + per_job]
        text = "\n\n".join(f"ITEM {it['item_id']}\nHypothesis: {it['hyp']}\nPaper [{it['paper']['id']}] "
                           f"({it['paper']['year']}) {it['paper']['title']}. {it['paper']['abstract']}" for it in part)
        prompt = llm.template("judge_hypothesis.md").format(items=text)
        assert est_tokens(prompt) < 30_000
        llm.write_job(kind, f"{qset}_{i // per_job:03d}", prompt, {"id_map": {it["item_id"]: it["key"] for it in part}})
    print(f"{len(items)} hypothesis-level items in {(len(items) + per_job - 1) // per_job} jobs")


def hypothesis_level(qset: str, kind: str = "hyp") -> dict | None:
    d = llm.JOBS / kind
    if not d.exists():
        return None
    lab = {}
    for p in sorted(d.glob(f"{qset}_*.json")):
        op = llm.JOBS / f"{kind}_out" / p.name
        if not op.exists():
            continue
        idm = llm.read_meta(kind, p.stem)["id_map"]
        for l in llm.parse_json(op.read_text())["labels"]:
            if l["item_id"] in idm:
                lab[idm[l["item_id"]]] = l["label"]
    if not lab:
        return None
    by_method = {}
    for key, label in lab.items():
        m = key.split("__")[1]
        by_method.setdefault(m, {}).setdefault(label, 0)
        by_method[m][label] += 1
    return {"n_items": len(lab), "by_method": by_method,
            "share_same": sum(1 for v in lab.values() if v == "same") / len(lab)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "hyp-jobs", "hyp-jobs-corrected"])
    ap.add_argument("--set", default="pilot")
    a = ap.parse_args()
    if a.cmd == "hyp-jobs":
        hyp_jobs(a.set)
    elif a.cmd == "hyp-jobs-corrected":
        hyp_jobs(a.set, kind="hyp_c", corrected=True)
    else:
        r = run(a.set)
        for n, v in r["measurements"].items():
            print(n, {k: round(x, 3) for k, x in v["match_rate"].items()}, "G-R idea-level", v["diffs"]["G-R"]["idea_level"])
        print(r["direction_flips"])
