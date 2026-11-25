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
