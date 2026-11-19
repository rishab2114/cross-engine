"""Independent-search check of the fixed literature search (pilot only).

A blinded sample of pairs (half apparent hits / later matches, half 'no earlier match'
or misses) is given to an independent searcher who sees only the two concepts and the
matching rule, never the pipeline's candidates or verdicts.

    python -m discovery.search_audit sample     # writes jobs/audit/*.json and results/search_audit_sheet.csv
    python -m discovery.search_audit compare    # after jobs/audit_out/*.json exist
"""
from __future__ import annotations

import csv
import json
import random
import sys

from . import llm
from .study import DATA, RESULTS, jdump, jload, read_jsonl

N_SAMPLE = 30
PER_JOB = 10
SEED = 2020

AUDIT_PROMPT = """You are an independent literature searcher. For each pair of concepts below, search the scholarly literature as thoroughly as you reasonably can using OpenAlex (the OpenAlex tools available to you, or the public API at https://api.openalex.org). Use synonyms, broader and narrower terms, and citation trails (references and citing works) — do not stop at one query. Do not use general web search.

Find, separately for each window, the best paper that EXPLICITLY studies a relationship between concept A and concept B:
- window "pre2020": published 2019 or earlier
- window "post2019": published 2020–2024

MATCHING RULE: a paper counts only if its title or abstract shows it explicitly studies a relationship, effect, association, mechanism or method linking A and B (synonyms and close variants count). A paper that merely mentions both does not count.

Spend at most about 6 queries per pair. Record the queries you ran.

PAIRS
{pairs}

OUTPUT: write only a JSON object {{"results": [{{"item_id": ..., "pre2020": {{"found": true/false, "paper_id": ..., "title": ..., "year": ..., "evidence": ...}}, "post2019": {{...same...}}, "queries": [...]}}, ...]}}
"""


def sample() -> None:
    rows = read_jsonl(DATA / "labelled_pilot.jsonl")
    by_pair = {}
    for r in rows:
        if r.get("pair_key") and r.get("hit") is not None:
            by_pair.setdefault(r["pair_key"], r)
    pos = [k for k, r in by_pair.items() if r["post2019_match"] or r["hit"]]
    neg = [k for k, r in by_pair.items() if not r["post2019_match"] and r["pre2020_match"] is False]
    rng = random.Random(SEED)
    rng.shuffle(pos); rng.shuffle(neg)
    half = N_SAMPLE // 2
    chosen = pos[:half] + neg[:N_SAMPLE - min(half, len(pos))]
    chosen = chosen[:N_SAMPLE]
    rng.shuffle(chosen)
    jdump(DATA / "search_audit_sample.json", chosen)
    with (RESULTS / "search_audit_sheet.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["item_id", "concept_A", "concept_B", "earliest_explicit_study_<=2019 (id/title)",
                    "explicit_study_2020-2024 (id/title)", "queries_used", "searcher_initials"])
        for k in chosen:
            a, b = k.split(" || ")
            w.writerow([k, a, b, "", "", "", ""])
    for i in range(0, len(chosen), PER_JOB):
        part = chosen[i:i + PER_JOB]
        ids = {f"P{i + j:02d}": k for j, k in enumerate(part)}
        text = "\n".join(f"- item_id: {o}\n  A = {k.split(' || ')[0]}\n  B = {k.split(' || ')[1]}" for o, k in ids.items())
        llm.write_job("audit", f"audit_{i // PER_JOB:02d}", AUDIT_PROMPT.format(pairs=text), {"id_map": ids})
    print(f"sampled {len(chosen)} pairs ({min(half, len(pos))} positive, rest negative)")


def compare(suffix: str = "") -> dict:
    rows = read_jsonl(DATA / f"labelled_pilot{suffix}.jsonl")
    pipe = {}
    for r in rows:
        if r.get("pair_key"):
            pipe.setdefault(r["pair_key"], r)
    found = {}
    for p in sorted((llm.JOBS / "audit_out").glob("*.json")):
        idmap = llm.read_meta("audit", p.stem)["id_map"]
        for res in llm.parse_json(p.read_text())["results"]:
            if res["item_id"] in idmap:
                found[idmap[res["item_id"]]] = res
    sample_keys = jload(DATA / "search_audit_sample.json")
    out = {"n": 0, "pre2020": {}, "post2019": {}, "items": []}
    for w, flag in (("pre2020", "pre2020_match"), ("post2019", "post2019_match")):
        pipe_no = aud_yes_given_pipe_no = pipe_yes = aud_no_given_pipe_yes = 0
        for k in sample_keys:
            if k not in found:
                continue
            p_m, a_m = bool(pipe[k][flag]), bool(found[k][w]["found"])
            if not p_m:
                pipe_no += 1; aud_yes_given_pipe_no += a_m
            else:
                pipe_yes += 1; aud_no_given_pipe_yes += (not a_m)
        out[w] = {"pipeline_no_match": pipe_no,
                  "independent_search_found_match_anyway": aud_yes_given_pipe_no,
                  "miss_rate_among_pipeline_no_match": aud_yes_given_pipe_no / pipe_no if pipe_no else None,
                  "pipeline_match": pipe_yes,
                  "independent_search_did_not_confirm": aud_no_given_pipe_yes}
    # Unblinding: attribute each missed match to the method(s) that proposed the pair.
    methods = {}
    for r in rows:
        if r.get("pair_key"):
            methods.setdefault(r["pair_key"], set()).add(r["method"])
    missed = {"pre2020": {}, "post2019": {}}
    for k in sample_keys:
        if k not in found:
            continue
        for w, flag in (("pre2020", "pre2020_match"), ("post2019", "post2019_match")):
            if not pipe[k][flag] and found[k][w]["found"]:
                for m in methods.get(k, []):
                    missed[w][m] = missed[w].get(m, 0) + 1
    out["missed_matches_by_method"] = missed
    for k in sample_keys:
        if k in found:
            out["items"].append({"item_id": k, "methods": sorted(methods.get(k, [])),
                                 "pipeline_pre": pipe[k]["pre2020_match"],
                                 "pipeline_post": pipe[k]["post2019_match"],
                                 "audit_pre": found[k]["pre2020"], "audit_post": found[k]["post2019"]})
    out["n"] = len(out["items"])
    (RESULTS / f"search_audit{suffix}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("n", "pre2020", "post2019")}, indent=1))
    return out


if __name__ == "__main__":
    if sys.argv[1] == "compare_widened":
        compare("_widened")
    else:
        {"sample": sample, "compare": compare}[sys.argv[1]]()
