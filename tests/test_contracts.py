"""Synthetic-fixture tests for the Codex review findings (C02-C06). No real holdout data is read."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from discovery import llm

SRC = str(Path(__file__).resolve().parents[1] / "src")


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "JOBS", tmp_path / "jobs")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return tmp_path / "jobs"


def _answer(kind, job_id, obj):
    p = llm.out_path(kind, job_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj))


# ---------------------------------------------------------------- C04: job identity
def test_c04_different_questions_never_share_an_answer(jobs):
    p1, p2 = "question one + evidence", "question two + evidence"
    id1 = f"adhoc__G__{llm.job_digest('adhoc', p1, max_tokens=8000)}"
    id2 = f"adhoc__G__{llm.job_digest('adhoc', p2, max_tokens=8000)}"
    assert id1 != id2
    assert llm.run("adhoc", id1, p1) is None  # queued
    _answer("adhoc", id1, {"ideas": ["answer to one"]})
    assert llm.run("adhoc", id1, p1) == {"ideas": ["answer to one"]}  # identical run resumes
    assert llm.run("adhoc", id2, p2) is None  # never question one's answer


def test_c04_reused_id_with_new_prompt_is_refused(jobs):
    llm.write_job("k", "j1", "prompt A", {"id_map": {"I1": "x"}})
    llm.write_job("k", "j1", "prompt A", {"id_map": {"I1": "x"}})  # identical rewrite: no-op
    with pytest.raises(llm.JobConflict):
        llm.write_job("k", "j1", "prompt B", {"id_map": {"I1": "x"}})
    with pytest.raises(llm.JobConflict):
        llm.write_job("k", "j1", "prompt A", {"id_map": {"I1": "y"}})  # metadata change
    llm.write_job("k", "j1", "prompt B", {"id_map": {"I1": "x"}}, replace=True)  # allowed: no output yet
    _answer("k", "j1", {"judgments": []})
    with pytest.raises(llm.JobConflict):
        llm.write_job("k", "j1", "prompt C", {"id_map": {"I1": "x"}}, replace=True)  # output exists
    with pytest.raises(llm.JobConflict):
        llm.run("k", "j1", "prompt C")


def test_c04_output_provenance_checked(jobs):
    llm.write_job("k", "j1", "prompt A", {})
    _answer("k", "j1", {"judgments": []})
    jp = jobs / "k" / "j1.json"
    jp.write_text(json.dumps({"id": "j1", "kind": "k", "prompt": "tampered"}))
    with pytest.raises(llm.JobConflict):
        llm.read_output("k", "j1")


def test_c04_api_path_persists_job_before_calling(jobs, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")

    def boom(*a, **k):
        raise ConnectionError("network down")
    monkeypatch.setattr(llm.requests, "post", boom)
    with pytest.raises(ConnectionError):
        llm.run("k", "j1", "prompt A", {"id_map": {"I1": "x"}})
    assert json.loads((jobs / "k" / "j1.json").read_text())["prompt"] == "prompt A"
    meta = llm.read_meta("k", "j1")
    assert meta["_prompt_sha256"] == llm.sha256("prompt A") and meta["_model"] == llm.MODEL


_JOBS_SCRIPT = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from discovery import llm, judge_eval
llm.JOBS = Path(sys.argv[2])
U = {"positives": [{"uid": f"P{i}", "a": f"alpha {i}", "b": f"beta {i}", "window": "pre2020",
                    "paper": {"id": f"W{i}", "year": 2010, "title": f"t{i}", "abstract": "x"}} for i in range(23)],
     "hard_negatives": [{"uid": f"N{i}", "a": f"gamma {i}", "b": f"delta {i}", "window": "post2019",
                         "paper": {"id": f"V{i}", "year": 2021, "title": f"s{i}", "abstract": "y"}} for i in range(7)]}
judge_eval.units = lambda which: U
judge_eval.write_jobs("selection")
out = {}
for d in sorted(llm.JOBS.glob("*_meta")):
    for p in sorted(d.glob("*.json")):
        out[f"{d.name}/{p.name}"] = json.loads(p.read_text())["id_map"]
print(json.dumps(out, sort_keys=True))
"""


def test_c04_job_regeneration_is_deterministic_across_processes(tmp_path):
    outs = []
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        r = subprocess.run([sys.executable, "-c", _JOBS_SCRIPT, SRC, str(tmp_path / f"jobs{seed}")],
                           capture_output=True, text=True, env=env, check=True)
        outs.append(r.stdout.strip().splitlines()[-1])
    assert outs[0] == outs[1] and len(json.loads(outs[0])) > 0


# ---------------------------------------------------------------- C02: frozen manifest
from discovery import contracts, judge_eval, manifest, retrieval_v2  # noqa: E402


def _unit(uid, a, b, window, pid, title="t", abstract="x"):
    return {"uid": uid, "a": a, "b": b, "window": window,
            "paper": {"id": pid, "year": 2010 if window == "pre2020" else 2021, "title": title, "abstract": abstract}}


@pytest.fixture
def v2data(tmp_path, monkeypatch, jobs):
    data = tmp_path / "data"
    (data / "holdout_sealed_v2").mkdir(parents=True)
    sel = {"positives": [_unit("S1", "alpha", "beta", "pre2020", "W1")],
           "hard_negatives": [_unit("S2", "gamma", "delta", "post2019", "W2")]}
    hold = {"positives": [_unit("H1", "beta", "alpha", "post2019", "W3"),   # same pair as S1 -> excluded
                          _unit("H2", "kappa", "lambda", "pre2020", "W4")],
            "hard_negatives": [_unit("H3", "mu", "nu", "post2019", "W5")]}
    (data / "units_v2_selection.json").write_text(json.dumps(sel))
    (data / "holdout_sealed_v2" / "units_v2_holdout.json").write_text(json.dumps(hold))
    monkeypatch.setattr(manifest, "MANIFEST", data / "run_manifest_v2.json")
    for mod in (judge_eval, retrieval_v2):
        monkeypatch.setattr(mod, "SELECTION_FILE", data / "units_v2_selection.json")
        monkeypatch.setattr(mod, "HOLDOUT_FILE", data / "holdout_sealed_v2" / "units_v2_holdout.json")
    monkeypatch.setattr(judge_eval, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(retrieval_v2, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(retrieval_v2, "DATA", data)
    return data


def test_c02_holdout_refused_without_complete_manifest(v2data):
    with pytest.raises(manifest.ManifestError):
        judge_eval.units("holdout")
    with pytest.raises(manifest.ManifestError):
        manifest.build("J0", None, data=v2data)  # a matcher is required
    with pytest.raises(manifest.ManifestError):
        manifest.check_set("holdout2")


def test_c02_manifest_is_immutable_and_verified(v2data):
    m = manifest.freeze("J0", "D", data=v2data)
    assert manifest.load()["digest"] == m["digest"]
    with pytest.raises(manifest.ManifestError):
        manifest.freeze("J1", "A", data=v2data)  # never overwritten
    with pytest.raises(manifest.ManifestError):
        manifest.require(judge="J1")  # alternative judge refused
    with pytest.raises(manifest.ManifestError):
        retrieval_v2.judge_jobs("holdout", "J1", "A")
    edited = {**m, "judge": "J1"}
    manifest.MANIFEST.write_text(json.dumps(edited))
    with pytest.raises(manifest.ManifestError):
        manifest.load()  # digest mismatch


def test_c02_holdout_jobs_only_for_frozen_judge_and_without_overlap(v2data, jobs):
    manifest.freeze("J0", "D", data=v2data)
    judge_eval.write_jobs("holdout")
    kinds = sorted(p.name for p in jobs.iterdir() if not p.name.endswith("_meta"))
    assert kinds == ["cls_J0_r1_holdout"]
    keys = set()
    for p in (jobs / "cls_J0_r1_holdout_meta").glob("*.json"):
        keys |= set(json.loads(p.read_text())["id_map"].values())
    assert keys == {"H2", "H3"}  # H1 shares a pair with selection (Amendment 6)
    r = judge_eval.evaluate("holdout")
    assert list(r["judges"]) == ["J0"] and "cheapest_passing" not in r
    assert r["amendment6_excluded_uids"] == ["H1"] and r["judges"]["J0"]["pass"] is False  # nothing judged yet


# ---------------------------------------------------------------- C03: incomplete work never passes
def _ret_units():
    return [_unit(f"U{i}", f"a{i}", f"b{i}", "pre2020" if i < 3 else "post2019", f"W{i}") for i in range(6)]


def test_c03_pending_and_error_states_block_the_gate(v2data, jobs, monkeypatch):
    U = _ret_units()
    monkeypatch.setattr(retrieval_v2, "units", lambda which: U)
    paper = lambda i: {"id": f"W{i}", "year": 2010 if i < 3 else 2021, "title": f"a{i} affects b{i}", "abstract": "x"}
    store = {f"A::U{i}": {"status": "ok", "papers": [paper(i)]} for i in (0, 1, 3, 4)}
    store["A::U2"] = {"status": "error", "error": "timeout"}          # search failed
    (v2data / "retrieval_v2_candidates_selection.json").write_text(json.dumps(store))  # U5: never searched
    retrieval_v2.judge_jobs("selection", "J0", "A")
    kind = "ret_J0_A_selection"
    for p in sorted((jobs / kind).glob("*.json")):
        idm = llm.read_meta(kind, p.stem)["id_map"]
        _answer(kind, p.stem, {"judgments": [{"item_id": i, "window": next(u["window"] for u in U if u["uid"] == k),
                                              "match": True, "paper_id": f"W{k[1:]}"} for i, k in idm.items()]})
    r = retrieval_v2.evaluate("selection", judges=("J0",), matchers=("A", "D"))
    a = r["results"]["J0/A"]
    assert a["recall"]["pre2020"]["rate"] == 1.0 and a["recall"]["post2019"]["rate"] == 1.0
    assert a["states"]["error"] == 1 and a["states"]["pending"] == 1
    assert a["recall_gate"] and a["pass_recall_gate"] is False  # perfect completed recall, still no pass
    with pytest.raises(RuntimeError):
        retrieval_v2.agentic_jobs("selection", ("J0",))  # C waits for completed A misses


def test_c03_d_runs_c_only_after_completed_a_miss(v2data, jobs, monkeypatch):
    U = _ret_units()[:2]
    monkeypatch.setattr(retrieval_v2, "units", lambda which: U)
    store = {"A::U0": {"status": "ok", "papers": []},  # completed miss: no candidates
             "A::U1": {"status": "ok", "papers": [{"id": "W1", "year": 2010, "title": "a1 and b1", "abstract": "x"}]}}
    (v2data / "retrieval_v2_candidates_selection.json").write_text(json.dumps(store))
    retrieval_v2.judge_jobs("selection", "J0", "A")
    kind = "ret_J0_A_selection"
    p = next((jobs / kind).glob("*.json"))
    idm = llm.read_meta(kind, p.stem)["id_map"]
    _answer(kind, p.stem, {"judgments": [{"item_id": i, "window": "pre2020", "match": False, "paper_id": None}
                                         for i in idm]})
    todo = retrieval_v2.agentic_jobs("selection", ("J0",))
    assert sorted(todo) == ["U0", "U1"]  # both are completed misses
    st = retrieval_v2.states("selection", "J0", "D")
    assert st == {"U0": "pending", "U1": "pending"}  # C not answered yet -> pending, never a miss


# ---------------------------------------------------------------- C05: strict contracts
ITEMS = {"K1": {"windows": {"pre2020": [{"id": "W1", "title": "Fuel taxes and congestion",
                                          "abstract": "We estimate the “effect of fuel taxes” on   urban congestion in 40 cities."}]}},
         "K2": {"windows": {"post2019": [{"id": "W2", "title": "Transit", "abstract": "Ridership rose."}]}}}
IDM = {"I1": "K1", "I2": "K2"}


def _out(*js):
    return json.dumps({"judgments": list(js)})


def test_c05_string_booleans_and_id_sets_rejected():
    ok = {"item_id": "I2", "window": "post2019", "match": False}
    with pytest.raises(contracts.SchemaError):
        contracts.parse_judgments(_out({"item_id": "I1", "window": "pre2020", "match": "false"}, ok), IDM, ITEMS)
    with pytest.raises(contracts.SchemaError):
        contracts.parse_judgments(_out(ok), IDM, ITEMS)  # missing I1
    with pytest.raises(contracts.SchemaError):
        contracts.parse_judgments(_out(ok, ok, {"item_id": "I1", "window": "pre2020", "match": False}), IDM, ITEMS)
    with pytest.raises(contracts.SchemaError):
        contracts.parse_judgments(_out(ok, {"item_id": "I9", "window": "pre2020", "match": False}), IDM, ITEMS)
    with pytest.raises(contracts.SchemaError):  # cited paper is not a candidate of this item
        contracts.parse_judgments(_out(ok, {"item_id": "I1", "window": "pre2020", "match": True, "paper_id": "W2"}),
                                  IDM, ITEMS)


def test_c05_quotes_must_occur_in_the_cited_text():
    ok = {"item_id": "I2", "window": "post2019", "match": False}
    good = {"item_id": "I1", "window": "pre2020", "match": True, "paper_id": "W1",
            "quote": 'estimate the "effect of fuel taxes" on urban congestion'}
    r = contracts.parse_judgments(_out(good, ok), IDM, ITEMS, quote_judge=True)
    assert r["K1"]["match"] is True and r["K1"]["quote_ok"] is True
    frag = {**good, "quote": "We estimate ... on urban congestion"}
    assert contracts.parse_judgments(_out(frag, ok), IDM, ITEMS, quote_judge=True)["K1"]["match"] is True
    bad = {**good, "quote": "fuel taxes reduce congestion"}
    r = contracts.parse_judgments(_out(bad, ok), IDM, ITEMS, quote_judge=True)
    assert r["K1"]["match"] is False and r["K1"]["quote_ok"] is False
    none = {**good, "quote": None}
    assert contracts.parse_judgments(_out(none, ok), IDM, ITEMS, quote_judge=True)["K1"]["match"] is False


def test_c05_overlap_exclusion_is_order_insensitive():
    sel = {"positives": [_unit("S1", "alpha", "beta", "pre2020", "W1")], "hard_negatives": []}
    hold = {"positives": [_unit("H1", "beta", "alpha", "post2019", "W9"), _unit("H2", "x", "y", "pre2020", "W8")],
            "hard_negatives": []}
    kept, dropped = contracts.exclude_overlap(hold, sel)
    assert dropped == ["H1"] and [u["uid"] for u in kept["positives"]] == ["H2"]


def test_c05_evaluators_never_read_the_unsplit_label_file():
    import inspect
    for mod in (judge_eval, retrieval_v2, manifest):
        assert '"units_v2.json"' not in inspect.getsource(mod)


# ---------------------------------------------------------------- C06: completeness and evidence budget
def test_c06_final_analysis_refuses_unjudged(monkeypatch):
    from discovery import analysis
    monkeypatch.setattr(analysis, "read_jsonl", lambda p: [{"hit": True}, {"hit": None}])
    monkeypatch.setattr(analysis, "jload", lambda p: {"main": [{"qid": "q1"}]})
    with pytest.raises(analysis.IncompleteLabels):
        analysis.run("main")


def test_c06_evidence_block_respects_hard_cap():
    from discovery import study
    by_id = {f"W{i}": {"id": f"W{i}", "year": 2010, "field": "economics", "title": "A long title " * 3,
                       "abstract": "word " * 400} for i in range(60)}
    block = study.evidence_block(list(by_id), cap=24_000, by_id=by_id)
    assert len(block) <= 24_000 and block.count("[W") == 60
    with pytest.raises(ValueError):
        study.evidence_block(list(by_id), cap=500, by_id=by_id)


def test_c03_v1_matcher_gate_rejects_pending(monkeypatch, tmp_path):
    from discovery import matcher_eval as me
    pcs = [{"uid": f"P{i}", "window": w, "pair_key": f"p{i}", "source": {"id": f"W{i}"}}
           for i, w in enumerate(["pre2020"] * 3 + ["post2019"] * 3)]
    U = {"positive_controls": pcs, "audit_pairs": [], "classification_positives": [{"uid": "C1"}],
         "hard_negatives": [{"uid": "N1"}]}
    store = {f"A::P{i}": [{"id": f"W{i}"}] for i in range(6)}
    J = {f"RET::A::P{i}": {"match": True} for i in range(4)}  # P4, P5 still pending
    J.update({"CLS::C1": {"match": True}, "CLS::N1": {"match": False}})
    monkeypatch.setattr(me, "units", lambda which: U)
    monkeypatch.setattr(me, "judgments", lambda which: J)
    monkeypatch.setattr(me, "agentic_candidates", lambda which: {})
    monkeypatch.setattr(me, "jload", lambda p: store if "matcher_candidates" in str(p) else {"items": []})
    monkeypatch.setattr(me, "RESULTS", tmp_path)
    r = me.evaluate("selection", "A")["matchers"]["A"]
    assert r["retrieval"]["post2019"]["rate"] == 1.0 and r["pending"] == 2
    assert r["gates"]["recall"] and r["gates"]["pass"] is False
    J["RET::A::P4"] = {"match": "true"}  # a string is an error state, not a match
    J["RET::A::P5"] = {"match": True}
    r = me.evaluate("selection", "A")["matchers"]["A"]
    assert r["errors"] == 1 and r["gates"]["pass"] is False
