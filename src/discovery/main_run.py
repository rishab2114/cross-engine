"""Main-run outcome measurement (Amendment 8): frozen J0 + D, decisive-only C, S1/S2 sensitivity.

    python -m discovery.main_run search      # matcher A, both windows, every distinct pair (stops at the daily cap)
    python -m discovery.main_run jobs        # queue all work needed now: J0 on A/C lists, decisive C searches, J1 confirms
    python -m discovery.main_run status      # unit states, undetermined hits, queued work
    python -m discovery.main_run label       # data/labelled_main.jsonl (+ _S1, _S2); refuses undetermined hits unless --provisional

Primary rule (frozen manifest): a pair-window matches if J0 says match on A's list, or, after a completed A miss
(no_match or no_candidates), on C's list. S1: the primary match is confirmed by J1 on the same list. S2: S1, plus J1's
quote is verified in its cited paper and that paper is the one J0 cited. A hit is "no match before 2020 and a match in
2020-2024". C (and J1) run only where they can still change a hit under at least one rule; the hits are therefore the
same as running D everywhere. The decision logic is pure (`unit_state`, `hit`, `next_actions`) and tested on fixtures.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter

from . import llm, manifest
from . import openalex as oa
from .budget import est_tokens
from .contracts import SchemaError, parse_judgments
from .matchers import SEL, _fmt, search_A
from .study import DATA, jdump, jload, opaque_id, pair_key, idea_pair, read_jsonl, render_items, write_jsonl

QSET = "main"
WINDOWS = ("pre2020", "post2019")
STORE = DATA / "main_candidates.json"
K_J0A, K_J0C, K_C, K_J1 = "main_J0_A", "main_J0_C", "main_C", "main_J1"
PER_JOB = 12
AGENTIC_PER_JOB = 8
MAX_JOB_TOKENS = 30_000
MISS = ("no_match", "no_candidates")
RULES = ("primary", "S1", "S2")


# ---------------------------------------------------------------- pure decision logic
def primary_state(f: dict) -> tuple[str, str | None]:
    """(state, reason) with state in match / nomatch / pending / error and reason in A / C / None."""
    a = f.get("A", "pending")
    if a == "match":
        return "match", None
    if a in ("pending", "error"):
        return a, "A"
    c = f.get("C")
    if c in (None, "pending"):
        return "pending", "C"
    if c == "error":
        return "error", "C"
    return ("match", None) if c == "match" else ("nomatch", None)


def matched_list(f: dict) -> str | None:
    """Which list produced the primary match ("A" or "C")."""
    if f.get("A") == "match":
        return "A"
    if f.get("A") in MISS and f.get("C") == "match":
        return "C"
    return None


def unit_state(f: dict, rule: str) -> tuple[str, str | None]:
    s, r = primary_state(f)
    if rule == "primary" or s != "match":
        return s, r
    j = f.get("J1")
    if j is None:
        return "pending", "J1"
    if rule == "S1":
        return ("match", None) if j.get("match") else ("nomatch", None)
    j0_paper = f.get("A_paper") if matched_list(f) == "A" else f.get("C_paper")
    ok = bool(j.get("match") and j.get("quote_ok") and j.get("paper_id") is not None
              and str(j.get("paper_id")) == str(j0_paper))
    return ("match", None) if ok else ("nomatch", None)


def hit(pre: str, post: str) -> bool | None:
    if pre == "match" or post == "nomatch":
        return False
    if pre == "nomatch" and post == "match":
        return True
    return None


def next_actions(f_pre: dict, f_post: dict) -> set[tuple[str, str]]:
    """Minimal next work, as (window, "C" | "J1"), to settle every rule's hit for one pair.
    Cheap J1 confirmations first; with two pending C stages, the post-2019 one first."""
    out: set[tuple[str, str]] = set()
    for rule in RULES:
        (ps, pr), (qs, qr) = unit_state(f_pre, rule), unit_state(f_post, rule)
        if hit(ps, qs) is not None:
            continue
        cand = [(w, r) for w, s, r in (("pre2020", ps, pr), ("post2019", qs, qr)) if s == "pending" and r in ("C", "J1")]
        if not cand:
            continue  # waiting on A, or stuck on an error
        j1 = [c for c in cand if c[1] == "J1"]
        if j1:
            out |= set(j1)
        elif len(cand) == 2:
            out.add(("post2019", "C"))
        else:
            out.add(cand[0])
    return out


# ---------------------------------------------------------------- data layer
def pairs() -> list[str]:
    return sorted({pair_key(*p) for r in read_jsonl(DATA / f"ideas_{QSET}.jsonl") if (p := idea_pair(r))})


def _store() -> dict:
    return jload(STORE) if STORE.exists() else {}


def search() -> None:
    """Matcher A for both windows of every distinct pair. Failed requests are recorded as errors and retried on
    the next run; the daily budget stop leaves the remaining units pending (never a miss)."""
    store, n = _store(), 0
    try:
        for pk in pairs():
            a, b = pk.split(" || ")
            for w in WINDOWS:
                k = f"A::{pk}::{w}"
                if k in store and store[k]["status"] == "ok":
                    continue
                try:
                    store[k] = {"status": "ok", "papers": search_A(a, b, w)}
                except oa.BudgetExceeded:
                    raise
                except Exception as exc:
                    store[k] = {"status": "error", "error": str(exc)[:300]}
                n += 1
                if n % 50 == 0:
                    jdump(STORE, store)
    except oa.BudgetExceeded as exc:
        print("stopped:", exc)
    jdump(STORE, store)
    print(f"A searched {n} units this run; {sum(1 for k in store if k.startswith('A::'))} A units stored")


def _job_outputs(kind: str):
    d = llm.JOBS / kind
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        yield p, llm.JOBS / f"{kind}_out" / p.name


def _lists(store: dict, stage: str) -> dict:
    return {k.split("::", 1)[1]: v for k, v in store.items() if k.startswith(f"{stage}::")}


def _judged(kind: str, lists: dict, quote: bool) -> tuple[dict, set, set]:
    """unit -> judgment record; plus the units queued and the units whose output was invalid."""
    out, queued, bad = {}, set(), set()
    for p, op in _job_outputs(kind):
        idm = llm.read_meta(kind, p.stem)["id_map"]
        queued |= set(idm.values())
        if not op.exists():
            continue
        its = {u: {"windows": {u.rsplit("::", 1)[1]: lists[u]["papers"]}} for u in idm.values() if u in lists}
        try:
            llm.check_provenance(kind, p.stem)
            out.update(parse_judgments(op.read_text(), idm, its, quote_judge=quote))
        except (SchemaError, llm.JobConflict, KeyError):
            bad |= set(idm.values())
    return out, queued, bad


def c_candidates(store: dict) -> tuple[dict, set]:
    """Parse C searcher outputs into C lists (works fetched by id, which is free; window enforced)."""
    queued = set()
    for p, op in _job_outputs(K_C):
        idm = llm.read_meta(K_C, p.stem)["id_map"]
        queued |= set(idm.values())
        if not op.exists():
            continue
        try:
            llm.check_provenance(K_C, p.stem)
            res = llm.parse_json(op.read_text())["results"]
        except Exception as exc:
            for u in idm.values():
                store.setdefault(f"C::{u}", {"status": "error", "error": f"invalid searcher output: {exc}"[:300]})
            continue
        seen = set()
        for r in res:
            iid = r.get("item_id")
            if iid not in idm or iid in seen:
                continue
            seen.add(iid)
            u = idm[iid]
            k = f"C::{u}"
            if k in store and store[k]["status"] == "ok":
                continue
            if r.get("error"):
                store[k] = {"status": "error", "error": str(r["error"])[:300], "job": p.stem}
                continue
            papers, w = [], u.rsplit("::", 1)[1]
            for wid in (r.get("candidates") or [])[:3]:
                try:
                    papers.extend(_fmt([oa.get(f"works/{str(wid).rsplit('/', 1)[-1]}", {"select": SEL})]))
                except Exception:
                    pass
            papers = [x for x in papers if x.get("year") and ((x["year"] <= 2019) if w == "pre2020" else (2020 <= x["year"] <= 2024))]
            store[k] = {"status": "ok", "papers": papers, "queries": r.get("queries", []), "job": p.stem}
        for iid, u in idm.items():
            if iid not in seen:
                store.setdefault(f"C::{u}", {"status": "error", "error": "searcher omitted this item", "job": p.stem})
    return store, queued


def facts() -> tuple[dict, dict]:
    """unit -> facts (A, A_paper, C, C_paper, J1) from the store and the judge outputs; and the queued-work sets."""
    store = _store()
    store, c_queued = c_candidates(store)
    jdump(STORE, store)
    A, C = _lists(store, "A"), _lists(store, "C")
    j0a, q0a, bad0a = _judged(K_J0A, A, quote=False)
    j0c, q0c, bad0c = _judged(K_J0C, C, quote=False)
    j1_lists = {}
    F = {}
    for pk in pairs():
        for w in WINDOWS:
            u = f"{pk}::{w}"
            f = {}
            a = A.get(u)
            if a is None:
                f["A"] = "pending"
            elif a["status"] != "ok":
                f["A"] = "error"
            elif not a["papers"]:
                f["A"] = "no_candidates"
            elif u in bad0a:
                f["A"] = "error"
            elif u in j0a:
                f["A"] = "match" if j0a[u]["match"] else "no_match"
                f["A_paper"] = j0a[u].get("paper_id")
            else:
                f["A"] = "pending"
            c = C.get(u)
            if c is not None:
                if c["status"] != "ok":
                    f["C"] = "error"
                elif not c["papers"]:
                    f["C"] = "no_candidates"
                elif u in bad0c:
                    f["C"] = "error"
                elif u in j0c:
                    f["C"] = "match" if j0c[u]["match"] else "no_match"
                    f["C_paper"] = j0c[u].get("paper_id")
                else:
                    f["C"] = "pending"
            elif u in c_queued:
                f["C"] = "pending"
            ml = matched_list(f)
            if ml:
                j1_lists[u] = (A if ml == "A" else C)[u]
            F[u] = f
    j1, q1, bad1 = _judged(K_J1, j1_lists, quote=True)
    for u, f in F.items():
        if u in j1:
            f["J1"] = j1[u]
    queued = {"J0A": q0a, "J0C": q0c, "C": c_queued, "J1": q1, "j1_lists": j1_lists, "A": A, "C_lists": C}
    return F, queued


def _write(kind: str, items: list[dict], per_job: int, template: str, render) -> int:
    if not items:
        return 0
    items = sorted(items, key=lambda x: x["item_id"])
    random.Random(llm.stable_seed(kind, len(list((llm.JOBS / kind).glob("*.json"))) if (llm.JOBS / kind).exists() else 0)).shuffle(items)
    start = len(list((llm.JOBS / kind).glob("*.json"))) if (llm.JOBS / kind).exists() else 0
    n, i = 0, 0
    while i < len(items):
        batch = items[i:i + per_job]
        prompt = llm.template(template).format(items=render(batch))
        while est_tokens(prompt) >= MAX_JOB_TOKENS and len(batch) > 1:
            batch = batch[:-1]
            prompt = llm.template(template).format(items=render(batch))
        llm.write_job(kind, f"{kind}_{start + n:04d}", prompt, {"id_map": {b["item_id"]: b["key"] for b in batch}})
        n += 1
        i += len(batch)
    return n


def _list_item(kind: str, u: str, papers: list) -> dict:
    pk, w = u.rsplit("::", 1)
    a, b = pk.split(" || ")
    return {"key": u, "item_id": opaque_id(kind, u), "A": a, "B": b, "windows": {w: papers}}


def jobs(max_c_units: int | None = None) -> dict:
    """Queue every job needed now. C searcher jobs are capped by `max_c_units` (budget pacing)."""
    manifest.require(judge="J0", matcher="D")  # the main run measures only with the frozen pipeline
    F, Q = facts()
    made = {}
    # 1. J0 on every A list with candidates
    items = [_list_item(K_J0A, u, v["papers"]) for u, v in Q["A"].items()
             if v["status"] == "ok" and v["papers"] and u not in Q["J0A"]]
    made[K_J0A] = _write(K_J0A, items, PER_JOB, "judge_match.md", render_items)
    # 2. J0 on every C list with candidates
    items = [_list_item(K_J0C, u, v["papers"]) for u, v in Q["C_lists"].items()
             if v["status"] == "ok" and v["papers"] and u not in Q["J0C"]]
    made[K_J0C] = _write(K_J0C, items, PER_JOB, "judge_match.md", render_items)
    # 3. decisive work from the planner
    want_c, want_j1 = [], []
    for pk in pairs():
        u_pre, u_post = f"{pk}::pre2020", f"{pk}::post2019"
        for w, act in next_actions(F[u_pre], F[u_post]):
            u = f"{pk}::{w}"
            if act == "J1" and u not in Q["J1"] and u in Q["j1_lists"]:
                want_j1.append(u)
            if act == "C" and (u not in Q["C"] or F[u].get("C") == "error"):
                want_c.append(u)
    items = [_list_item(K_J1, u, Q["j1_lists"][u]["papers"]) for u in sorted(set(want_j1))]
    made[K_J1] = _write(K_J1, items, PER_JOB, "judge_match_quote.md", render_items)
    want_c = sorted(set(want_c))[: max_c_units if max_c_units is not None else None]
    citems = []
    for u in want_c:
        pk, w = u.rsplit("::", 1)
        a, b = pk.split(" || ")
        # a re-queued unit (after an error) gets a fresh opaque id so its new job is distinct
        n_prev = sum(1 for p, _ in _job_outputs(K_C) if u in llm.read_meta(K_C, p.stem)["id_map"].values())
        citems.append({"key": u, "item_id": opaque_id(K_C, f"{u}#{n_prev}"), "a": a, "b": b, "w": w})
    made[K_C] = _write(K_C, citems, AGENTIC_PER_JOB, "match_agentic.md",
                       lambda bs: "\n".join(f"- item_id: {x['item_id']}\n  A = {x['a']}\n  B = {x['b']}\n  window = {x['w']}"
                                            for x in bs))
    print({k: v for k, v in made.items()})
    return made


def label(provisional: bool = False) -> dict:
    F, _ = facts()
    rows = read_jsonl(DATA / f"ideas_{QSET}.jsonl")
    summary = {}
    for rule in RULES:
        out, undetermined = [], 0
        for r in rows:
            r = dict(r)
            p = idea_pair(r)
            r["pair_key"] = pair_key(*p) if p else None
            if not p:  # empty or unmappable slot: counts as a non-hit (fixed denominator of 10)
                r.update({"pre2020_match": False, "post2019_match": False, "hit": False, "measure_status": "no_pair"})
                out.append(r)
                continue
            st = {w: unit_state(F[f"{r['pair_key']}::{w}"], rule)[0] for w in WINDOWS}
            h = hit(st["pre2020"], st["post2019"])
            a_pre = F[f"{r['pair_key']}::pre2020"].get("A")
            r["pre2020_match"] = True if st["pre2020"] == "match" else False if st["pre2020"] == "nomatch" else None
            r["post2019_match"] = True if st["post2019"] == "match" else False if st["post2019"] == "nomatch" else None
            r["pre2020_match_A_stage"] = (a_pre == "match") if a_pre in ("match",) + MISS else None
            r["hit"] = h
            r["measure_status"] = "determined" if h is not None else "undetermined"
            undetermined += h is None
            out.append(r)
        suffix = "" if rule == "primary" else f"_{rule}"
        if undetermined and not provisional:
            summary[rule] = {"undetermined": undetermined}
            continue
        write_jsonl(DATA / f"labelled_{QSET}{suffix}.jsonl", out)
        summary[rule] = {"ideas": len(out), "hits": sum(1 for x in out if x["hit"]), "undetermined": undetermined}
    print(summary)
    return summary


def status() -> dict:
    F, Q = facts()
    s = {"pairs": len(pairs()), "units": len(F),
         "A": Counter(f.get("A") for f in F.values()), "C": Counter(f.get("C") for f in F.values() if "C" in f),
         "J1": sum(1 for f in F.values() if "J1" in f)}
    for rule in RULES:
        hs = Counter()
        for pk in pairs():
            hs[str(hit(unit_state(F[f"{pk}::pre2020"], rule)[0], unit_state(F[f"{pk}::post2019"], rule)[0]))] += 1
        s[f"hits_{rule}"] = dict(hs)
    s["A"], s["C"] = dict(s["A"]), dict(s["C"])
    print(json.dumps(s, indent=1))
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["search", "jobs", "status", "label"])
    ap.add_argument("--max-c-units", type=int)
    ap.add_argument("--provisional", action="store_true")
    a = ap.parse_args()
    {"search": search, "status": status}.get(a.cmd, lambda: None)()
    if a.cmd == "jobs":
        jobs(a.max_c_units)
    if a.cmd == "label":
        label(a.provisional)
