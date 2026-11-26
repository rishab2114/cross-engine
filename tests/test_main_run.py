"""Synthetic tests for the main-run measurement planner (Amendment 8). No real data or network."""
import itertools
import json
import random

import pytest

from discovery import main_run as mr
from discovery import openalex as oa

STATES = ("match", "no_match", "no_candidates")


def _j1(rng):
    return {"match": rng.random() < 0.7, "quote_ok": rng.random() < 0.8, "paper_id": rng.choice(["W1", "W2"])}


def _truth(rng):
    return {"A": rng.choice(STATES), "A_paper": rng.choice(["W1", "W2"]), "C": rng.choice(STATES),
            "C_paper": rng.choice(["W1", "W2"]), "J1_A": _j1(rng), "J1_C": _j1(rng)}


def _full(t):
    f = {"A": t["A"], "A_paper": t["A_paper"]}
    if t["A"] != "match":
        f["C"], f["C_paper"] = t["C"], t["C_paper"]
    ml = mr.matched_list(f)
    if ml:
        f["J1"] = t["J1_A"] if ml == "A" else t["J1_C"]
    return f


def _simulate(tpre, tpost):
    """Start from A-stage facts only and reveal C / J1 results only when the planner asks for them."""
    F = {"pre2020": {"A": tpre["A"], "A_paper": tpre["A_paper"]},
         "post2019": {"A": tpost["A"], "A_paper": tpost["A_paper"]}}
    T = {"pre2020": tpre, "post2019": tpost}
    asked = []
    for _ in range(10):
        acts = mr.next_actions(F["pre2020"], F["post2019"])
        if not acts:
            break
        for w, act in acts:
            asked.append((w, act))
            f, t = F[w], T[w]
            if act == "C":
                f["C"], f["C_paper"] = t["C"], t["C_paper"]
            else:
                f["J1"] = t["J1_A"] if mr.matched_list(f) == "A" else t["J1_C"]
    return F, asked


def test_planner_reproduces_full_information_hits():
    rng = random.Random(8)
    for _ in range(3000):
        tpre, tpost = _truth(rng), _truth(rng)
        F, _ = _simulate(tpre, tpost)
        full = {"pre2020": _full(tpre), "post2019": _full(tpost)}
        for rule in mr.RULES:
            got = mr.hit(mr.unit_state(F["pre2020"], rule)[0], mr.unit_state(F["post2019"], rule)[0])
            want = mr.hit(mr.unit_state(full["pre2020"], rule)[0], mr.unit_state(full["post2019"], rule)[0])
            assert got is not None and got == want, (tpre, tpost, rule)


def test_pre_match_needs_no_c_unless_j1_rejects():
    pre = {"A": "match", "A_paper": "W1"}
    post = {"A": "no_match"}
    assert mr.next_actions(pre, post) == {("pre2020", "J1")}  # cheap confirmation first, no C yet
    pre["J1"] = {"match": True, "quote_ok": True, "paper_id": "W1"}
    assert mr.next_actions(pre, post) == set()  # every rule settled: pre-2020 match, no hit
    pre["J1"] = {"match": False, "quote_ok": False, "paper_id": None}
    assert mr.next_actions(pre, post) == {("post2019", "C")}  # S1/S2 now treat pre-2020 as no match


def test_two_a_misses_resolve_post2019_first():
    assert mr.next_actions({"A": "no_match"}, {"A": "no_candidates"}) == {("post2019", "C")}
    # post-2019 C finds nothing: no hit under any rule, so the pre-2020 C stage is never run
    assert mr.next_actions({"A": "no_match"}, {"A": "no_candidates", "C": "no_match"}) == set()


def test_pending_and_errors_never_resolve_to_a_miss():
    assert mr.unit_state({"A": "pending"}, "primary") == ("pending", "A")
    assert mr.unit_state({"A": "error"}, "primary") == ("error", "A")
    assert mr.unit_state({"A": "no_match", "C": "error"}, "primary") == ("error", "C")
    assert mr.hit("pending", "match") is None and mr.hit("error", "match") is None
    # a unit in error is never acted on as if it were a miss (no C for it); the healthy window may still progress
    assert all(w != "pre2020" for w, _ in mr.next_actions({"A": "error"}, {"A": "match"}))


def test_s2_requires_verified_quote_from_the_same_paper():
    f = {"A": "match", "A_paper": "W1", "J1": {"match": True, "quote_ok": True, "paper_id": "W2"}}
    assert mr.unit_state(f, "S1")[0] == "match"
    assert mr.unit_state(f, "S2")[0] == "nomatch"  # different paper
    f["J1"] = {"match": True, "quote_ok": False, "paper_id": "W1"}
    assert mr.unit_state(f, "S2")[0] == "nomatch"  # quote not verified
    f["J1"] = {"match": True, "quote_ok": True, "paper_id": "W1"}
    assert mr.unit_state(f, "S2")[0] == "match"


def test_budget_stop_leaves_units_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "STORE", tmp_path / "store.json")
    monkeypatch.setattr(mr, "pairs", lambda: ["a || b", "c || d"])
    calls = {"n": 0}

    def fake(a, b, w):
        calls["n"] += 1
        if calls["n"] > 2:
            raise oa.BudgetExceeded("cap")
        return [{"id": "W1", "year": 2010, "title": "t", "abstract": "x"}]
    monkeypatch.setattr(mr, "search_A", fake)
    mr.search()
    store = json.loads((tmp_path / "store.json").read_text())
    assert sorted(store) == ["A::a || b::post2019", "A::a || b::pre2020"]  # the rest stay unsearched (pending)


def test_label_refuses_undetermined_hits(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "DATA", tmp_path)
    rows = [{"a": "x", "b": "y", "a_raw": "x", "b_raw": "y", "qid": "q", "method": "G"}]
    monkeypatch.setattr(mr, "read_jsonl", lambda p: rows)
    monkeypatch.setattr(mr, "facts", lambda: ({"x || y::pre2020": {"A": "no_match"},
                                               "x || y::post2019": {"A": "match", "A_paper": "W1"}}, {}))
    s = mr.label()
    assert s["primary"] == {"undetermined": 1} and not (tmp_path / "labelled_main.jsonl").exists()
    s = mr.label(provisional=True)
    assert s["primary"]["undetermined"] == 1 and (tmp_path / "labelled_main.jsonl").exists()


def test_gp_ideas_are_matched_to_pairs_by_name_not_position():
    from discovery.study import match_pair_ideas
    cands = [{"a": "x", "b": "y", "paths": [["x", "m", "y"]]}, {"a": "p", "b": "q"}, {"a": "r", "b": "s"}]
    raw = [{"a": "q", "b": "p", "hypothesis": "about p-q"}, {"a": "x", "b": "y", "hypothesis": "about x-y"}]
    out = match_pair_ideas(raw, cands)
    assert [o["hypothesis"] for o in out] == ["about x-y", "about p-q", None]
    assert [o["matched_by"] for o in out] == ["name", "name", "missing"]
    assert out[0]["has_path"] is True and out[1]["writer_rank"] == 0
