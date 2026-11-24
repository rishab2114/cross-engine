import inspect
import json

from discovery import corpus, openalex
from discovery.budget import Ledger, est_tokens
from discovery.graph import ConceptGraph
from discovery.study import map_concept, pair_key


def toy_corpus():
    # a-m and m-b co-occur; a-b never do.
    rows = []
    for i in range(6):
        rows.append({"id": f"W{i}", "field": "economics", "year": 2010 + i, "concepts": ["a", "m"]})
    for i in range(6, 12):
        rows.append({"id": f"W{i}", "field": "transport", "year": 2010 + i % 10, "concepts": ["m", "b"]})
    for i in range(12, 18):
        rows.append({"id": f"W{i}", "field": "transport", "year": 2016, "concepts": ["b", "c"]})
    return rows


def test_reconstruct_abstract():
    inv = {"Hello": [0], "world": [1, 3], "big": [2]}
    assert openalex.reconstruct_abstract(inv) == "Hello world big world"
    assert openalex.reconstruct_abstract(None) == ""


def test_novelty_rule_and_paths():
    g = ConceptGraph(toy_corpus(), max_doc_share=1.0, min_doc_freq=1)
    assert g.cooccur("a", "m") == 6
    assert g.is_novel_pair("a", "b")
    assert not g.is_novel_pair("a", "m")
    assert not g.is_novel_pair("a", "a")
    score, paths = g.path_score("a", "b")
    assert score > 0 and paths[0] == ("a", "m", "b")
    # 3-hop a-m-b-c exists, 2-hop a-?-c does not
    s3, p3 = g.path_score("a", "c")
    assert s3 > 0 and len(p3[0]) == 4
    assert g.support_papers(("a", "m", "b")) == ["W0", "W10"] or len(g.support_papers(("a", "m", "b"))) == 2


def test_home_field_and_growth():
    g = ConceptGraph(toy_corpus(), max_doc_share=1.0, min_doc_freq=1)
    assert g.home_field("a") == "economics"
    assert g.home_field("c") == "transport"
    assert g.growth("c") > 0


def test_map_concept():
    allowed = ["Congestion pricing", "Air quality"]
    assert map_concept("congestion pricing", allowed) == "Congestion pricing"
    assert map_concept("Air qualty", allowed) == "Air quality"
    assert map_concept("Something else", allowed) is None
    assert pair_key("b", "a") == pair_key("a", "b") == "a || b"


def test_ledger(tmp_path):
    led = Ledger(tmp_path / "l.json")
    led.add("G", "gen", tokens_in=10, tokens_out=5, seconds=1.0)
    led.add("G", "build", seconds=2.0, scope="setup")
    s = led.summary()["G"]
    assert s["tokens_in"] == 10 and s["setup_seconds"] == 2.0 and s["query_seconds"] == 1.0
    assert est_tokens("abcd" * 10) == 10


def test_corpus_selection_uses_no_post2019_information():
    # Selection is a seeded random sample, never sorted by citations.
    src = inspect.getsource(openalex.sample_works) + inspect.getsource(corpus.build)
    assert "cited_by_count" not in src and "sort" not in src
    assert max(corpus.YEARS) == 2019
    # sampling parameters are deterministic for a given year
    assert corpus.SEED + 2015 == corpus.SEED + 2015


def test_corpus_file_if_present():
    p = corpus.DATA / "corpus.jsonl"
    m = corpus.DATA / "corpus_manifest.json"
    if not (p.exists() and m.exists()):
        return
    years = set()
    with p.open() as fh:
        for line in fh:
            years.add(json.loads(line)["year"])
    assert max(years) <= 2019 and min(years) >= 2000
    man = json.loads(m.read_text())
    assert man["no_citation_ranking"] is True


def test_job_files_carry_no_metadata():
    """Runners read job files; blinding labels must live only in the *_meta sidecars."""
    import pathlib
    jobs = pathlib.Path(__file__).resolve().parents[1] / "jobs"
    for kind in ("judge", "judge2", "cite", "leak", "audit"):
        for p in (jobs / kind).glob("*.json") if (jobs / kind).exists() else []:
            d = json.loads(p.read_text())
            assert "meta" not in d, p
            assert "CTRL::" not in d["prompt"], p


def test_clopper_pearson():
    from discovery.matcher_eval import cp
    r = cp(7, 8)
    assert abs(r["ci95"][0] - 0.4735) < 1e-3 and abs(r["ci95"][1] - 0.9968) < 1e-3
    assert cp(0, 5)["ci95"][0] == 0.0 and cp(5, 5)["ci95"][1] == 1.0


def test_holdout_sealed_without_decision(tmp_path, monkeypatch):
    import pytest
    from discovery import matchers
    monkeypatch.setattr(matchers, "DATA", tmp_path)
    with pytest.raises(SystemExit):
        matchers.units("holdout")


def test_validation_job_sizes_under_limit():
    import pathlib
    from discovery.budget import est_tokens
    jobs = pathlib.Path(__file__).resolve().parents[1] / "jobs"
    for kind in ("adj", "judge_m_selection", "judge_A", "hyp"):
        for p in (jobs / kind).glob("*.json") if (jobs / kind).exists() else []:
            assert est_tokens(json.loads(p.read_text())["prompt"]) < 30_000, p


def test_holdout_stays_sealed_when_no_matcher_chosen():
    import pytest
    from discovery import matchers
    from discovery.study import DATA, jload
    dec = DATA / "matcher_selection_decision.json"
    if dec.exists() and jload(dec).get("chosen_matcher") is None:
        with pytest.raises(SystemExit):
            matchers.units("holdout")


def test_openalex_daily_cap(tmp_path, monkeypatch):
    import time as _t
    import pytest
    from discovery import openalex as oa
    log = tmp_path / "costs.jsonl"
    log.write_text("\n".join(json.dumps({"t": _t.time(), "kind": "search", "cost_usd": 0.001}) for _ in range(900)))
    monkeypatch.setattr(oa, "COST_LOG", log)
    monkeypatch.setattr(oa, "CACHE", tmp_path / "cache")
    with pytest.raises(oa.BudgetExceeded):
        oa.get("works", {"filter": "publication_year:2019", "per_page": 1}, use_cache=False)
