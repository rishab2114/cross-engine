"""Study orchestration: questions, generation jobs, idea ingestion, matching, judging.

Usage (each stage is idempotent; LLM stages queue job files when no API key is set):
    python -m discovery.study questions
    python -m discovery.study generate --set pilot|main
    python -m discovery.study ingest   --set pilot|main
    python -m discovery.study search   --set pilot|main
    python -m discovery.study judge    --set pilot|main
    python -m discovery.study collect  --set pilot|main
"""
from __future__ import annotations

import argparse
import difflib
import json
import random
import re
import time
from collections import Counter
from pathlib import Path

from . import llm
from . import openalex as oa
from .budget import Ledger, est_tokens
from .engine import Engine
from .methods import candidates as cand

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RESULTS = ROOT / "results"

N_QUESTIONS_PER_FIELD = 20
SHORTLIST = 10
RN_OVERGENERATE = 30
RETRIEVE_K = 30
EVIDENCE_CAP_CHARS = 24_000          # ~6,000 tokens of evidence per question, every method
N_CONCEPT_LIST = 100
QUESTION_TEMPLATE = ("What new, testable relationships could help explain outcomes or improve "
                     "methods in research on {topic}?")
MATCH_PER_WINDOW = 5
WINDOWS = {"pre2020": "publication_year:<2020", "post2019": "publication_year:2020-2024"}
JUDGE_BATCH = 25
SEED = 7

METHODS_LLM = ["G", "P", "R", "RN"]
METHODS = METHODS_LLM + ["B"]


# ---------------------------------------------------------------- helpers
def jdump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1))


def jload(path: Path):
    return json.loads(path.read_text())


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open()] if path.exists() else []


def clean_concept(c: str) -> str:
    return re.sub(r"\s*\(.*?\)\s*", " ", c).strip()


_engine: Engine | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine.load()
    return _engine


def ledger() -> Ledger:
    return Ledger(DATA / "budget_ledger.json")


# ---------------------------------------------------------------- questions
GEO_EXCLUDE = {"china", "india", "europe", "united states", "africa", "japan", "germany", "brazil",
               "united kingdom", "australia", "indonesia", "nigeria", "sub-saharan africa", "latin america",
               "developing countries", "emerging markets", "cross-national comparison"}


def _too_close(k: str, chosen: list[str]) -> bool:
    tk = set(re.findall(r"[a-z0-9]+", k))
    for c in chosen:
        tc = set(re.findall(r"[a-z0-9]+", c))
        if k in c or c in k or len(tk & tc) / len(tk | tc) >= 0.5:
            return True
    return False


def make_questions() -> dict:
    """One question per frequent pre-2020 OpenAlex keyword in each field.

    Keywords are taken in descending frequency within the field's corpus, skipping
    geographic/sample descriptors (GEO_EXCLUDE) and near-duplicates of an already
    chosen keyword (substring or token Jaccard >= 0.5). Ranks 1-20 per field form the
    main set; rank 21 is the pilot question.
    """
    e = engine()
    out = {"main": [], "pilot": []}
    for field in ("economics", "transport"):
        counts = Counter(k.lower() for d in e.docs if d["field"] == field for k in set(d["keywords"]))
        chosen = []
        for k, _ in counts.most_common():
            if k in GEO_EXCLUDE or _too_close(k, chosen):
                continue
            chosen.append(k)
            if len(chosen) == N_QUESTIONS_PER_FIELD + 1:
                break
        for i, kw in enumerate(chosen):
            q = {"qid": f"{field[:4]}{i + 1:02d}", "field": field, "topic": kw,
                 "n_corpus_papers": counts[kw], "text": QUESTION_TEMPLATE.format(topic=kw)}
            (out["main"] if i < N_QUESTIONS_PER_FIELD else out["pilot"]).append(q)
    jdump(DATA / "questions.json", out)
    return out


def questions(qset: str) -> list[dict]:
    return jload(DATA / "questions.json")[qset]


# ---------------------------------------------------------------- evidence
def paper_line(d: dict, n_chars: int) -> str:
    abstract = d["abstract"]
    if len(abstract) > n_chars:
        abstract = abstract[:n_chars].rsplit(" ", 1)[0] + " ..."
    return f"[{d['id']}] ({d['year']}, {d['field']}) {d['title']}. {abstract}"


def evidence_block(ids: list[str], cap: int = EVIDENCE_CAP_CHARS) -> str:
    e = engine()
    ids = list(dict.fromkeys(ids))
    if not ids:
        return "(none)"
    per = max(150, cap // len(ids) - 120)
    return "\n\n".join(paper_line(e.by_id[i], per) for i in ids)


def gen_prompt(question: dict, evidence: str, task: str, n: int) -> str:
    return llm.template("generation.md").format(question=question["text"], evidence=evidence, task=task, n=n)


# ---------------------------------------------------------------- generation
def candidates_for(method: str, q: dict) -> list[dict]:
    e = engine()
    fn = {"G": cand.graph_paths, "P": cand.pairwise, "B": cand.popularity}[method]
    return fn(e, q["text"])


def retrieval_context(q: dict) -> tuple[list[str], list[str]]:
    e = engine()
    docs = e.retriever.search(q["text"], k=RETRIEVE_K)
    ids = [d["id"] for d in docs]
    vocab = e.graph.vocab
    tagged = {c for d in docs for c in d["nodes"] if c in vocab}
    top = {c for c, _ in e.top_concepts(q["text"], N_CONCEPT_LIST)}
    return ids, sorted(tagged | top)


def build_generation_job(method: str, q: dict) -> tuple[str, dict]:
    if method in ("G", "P"):
        cands = candidates_for(method, q)
        lines, ev = [], []
        for i, c in enumerate(cands, 1):
            path = ""
            if method == "G" and c.get("paths"):
                path = " | path: " + " -> ".join(c["paths"][0])
            lines.append(f"{i}. a = {c['a']} ; b = {c['b']}{path} | evidence: {', '.join(c['evidence_ids'])}")
            ev.extend(c["evidence_ids"])
        task = llm.template("task_pairs.md").format(pairs="\n".join(lines))
        prompt = gen_prompt(q, evidence_block(ev), task, len(cands))
        meta = {"candidates": cands, "evidence_ids": list(dict.fromkeys(ev))}
    else:
        ids, concepts = retrieval_context(q)
        rule = ""
        n = SHORTLIST
        if method == "RN":
            n = RN_OVERGENERATE
            rule = (" Only pairs of concepts that have never been studied together in this literature are "
                    "eligible: any pair that already appears together on a paper in the collection will be "
                    "removed automatically. Prefer connections that are new.")
        task = llm.template("task_brainstorm.md").format(novelty_rule=rule, concepts="; ".join(concepts))
        prompt = gen_prompt(q, evidence_block(ids), task, n)
        meta = {"evidence_ids": ids, "concept_list": concepts, "n": n}
    return prompt, meta


def generate(qset: str) -> None:
    led = ledger()
    for q in questions(qset):
        for m in METHODS_LLM:
            jid = f"{q['qid']}__{m}"
            if llm.out_path("gen", jid).exists() or (llm.JOBS / "gen" / f"{jid}.json").exists():
                continue
            t0 = time.time()
            prompt, meta = build_generation_job(m, q)
            led.add(m, "candidate_selection+prompt", tokens_in=est_tokens(prompt),
                    seconds=time.time() - t0, qid=q["qid"], qset=qset)
            llm.write_job("gen", jid, prompt, {**meta, "qid": q["qid"], "method": m, "qset": qset})
        # B needs no LLM
        t0 = time.time()
        b = candidates_for("B", q)
        led.add("B", "candidate_selection", seconds=time.time() - t0, qid=q["qid"], qset=qset)
        jdump(DATA / "b_ideas" / f"{q['qid']}.json", b)
    print("generation jobs queued")


# ---------------------------------------------------------------- ingestion
def map_concept(name: str, allowed: list[str]) -> str | None:
    if not name:
        return None
    if name in allowed:
        return name
    low = {c.lower(): c for c in allowed}
    if name.lower() in low:
        return low[name.lower()]
    m = difflib.get_close_matches(name.lower(), list(low), n=1, cutoff=0.85)
    return low[m[0]] if m else None


def ingest(qset: str) -> list[dict]:
    e = engine()
    g = e.graph
    led = ledger()
    rows, missing = [], []
    for q in questions(qset):
        for m in METHODS:
            if m == "B":
                ideas = jload(DATA / "b_ideas" / f"{q['qid']}.json")
                raw = [{"a": c["a"], "b": c["b"], "hypothesis": c["hypothesis"], "sources": [],
                        "test": None, "disconfirming": None} for c in ideas]
                allowed = list(g.vocab)
            else:
                jid = f"{q['qid']}__{m}"
                job = jload(llm.JOBS / "gen" / f"{jid}.json")
                out = llm.read_output("gen", jid)
                if out is None:
                    missing.append(jid)
                    continue
                raw = out.get("ideas", [])
                led_rows = [r for r in led.rows if r.get("qid") == q["qid"] and r["method"] == m
                            and r["stage"] == "generation_output"]
                if not led_rows:
                    led.add(m, "generation_output",
                            tokens_out=est_tokens(llm.out_path("gen", jid).read_text()), qid=q["qid"], qset=qset)
                meta = job["meta"]
                if m in ("G", "P"):
                    # keep the selected pair even if the writer altered names
                    cands = meta["candidates"]
                    for i, idea in enumerate(raw[:len(cands)]):
                        idea["a"], idea["b"] = cands[i]["a"], cands[i]["b"]
                    raw = raw[:len(cands)]
                    allowed = list(g.vocab)
                else:
                    allowed = meta["concept_list"]
            kept = []
            for rank, idea in enumerate(raw):
                a = map_concept(idea.get("a", ""), allowed)
                b = map_concept(idea.get("b", ""), allowed)
                co = g.cooccur(a, b) if (a and b and a in g.vocab and b in g.vocab) else None
                rec = {
                    "qid": q["qid"], "field": q["field"], "method": m, "gen_rank": rank,
                    "a_raw": idea.get("a"), "b_raw": idea.get("b"), "a": a, "b": b,
                    "cooccur_pre2020": co,
                    "hypothesis": idea.get("hypothesis"), "sources": idea.get("sources", []),
                    "test": idea.get("test"), "disconfirming": idea.get("disconfirming"),
                }
                if m == "RN" and not (co is not None and g.is_novel_pair(a, b)):
                    continue  # novelty filter: drop familiar or unmappable pairs
                kept.append(rec)
            kept = kept[:SHORTLIST]
            for i, r in enumerate(kept):
                r["rank"] = i + 1
                r["idea_id"] = f"{q['qid']}__{m}__{i + 1:02d}"
                r["cross_field"] = (g.home_field(r["a"]) != g.home_field(r["b"])) if (r["a"] and r["b"]) else None
            rows.extend(kept)
    write_jsonl(DATA / f"ideas_{qset}.jsonl", rows)
    if missing:
        print(f"missing generation outputs: {len(missing)}", missing[:10])
    print(f"ingested {len(rows)} ideas")
    return rows


# ---------------------------------------------------------------- matching search
def pair_key(a: str, b: str) -> str:
    x, y = sorted([a, b])
    return f"{x} || {y}"


def idea_pair(r: dict) -> tuple[str, str] | None:
    a = r["a"] or r["a_raw"]
    b = r["b"] or r["b_raw"]
    if not a or not b or a == b:
        return None
    return a, b


def search_pair(a: str, b: str, window: str, per_window: int = MATCH_PER_WINDOW) -> tuple[int, list[dict]]:
    ca, cb = clean_concept(a).replace('"', ""), clean_concept(b).replace('"', "")
    flt = f'title_and_abstract.search:"{ca}" AND "{cb}",{WINDOWS[window]}'
    data = oa.get("works", {"filter": flt, "per_page": per_window, "sort": "relevance_score:desc",
                            "select": "id,title,publication_year,abstract_inverted_index"})
    res = []
    for w in data.get("results", []):
        res.append({"id": w["id"].rsplit("/", 1)[-1], "year": w.get("publication_year"),
                    "title": w.get("title") or "",
                    "abstract": oa.reconstruct_abstract(w.get("abstract_inverted_index"))[:900]})
    return data.get("meta", {}).get("count", 0), res


def search(qset: str) -> None:
    ideas = read_jsonl(DATA / f"ideas_{qset}.jsonl")
    path = DATA / "pair_candidates.json"
    store = jload(path) if path.exists() else {}
    pairs = {pair_key(*p) for r in ideas if (p := idea_pair(r))}
    todo = [k for k in sorted(pairs) if k not in store]
    for i, k in enumerate(todo):
        a, b = k.split(" || ")
        entry = {}
        for w in WINDOWS:
            n, res = search_pair(a, b, w)
            entry[w] = {"count": n, "candidates": res}
        store[k] = entry
        if i % 50 == 0:
            jdump(path, store)
            print(f"searched {i}/{len(todo)}", flush=True)
    jdump(path, store)
    print(f"pairs with candidates: {len(pairs)} (new {len(todo)})")


# ---------------------------------------------------------------- judging
def judge_items(keys: list[str], store: dict) -> list[dict]:
    items = []
    for k in keys:
        a, b = k.split(" || ")
        wins = {w: store[k][w]["candidates"] for w in WINDOWS if store[k][w]["candidates"]}
        if wins:
            items.append({"item_id": k, "A": a, "B": b, "windows": wins})
    return items


def render_items(items: list[dict]) -> str:
    blocks = []
    for it in items:
        lines = [f"ITEM {it['item_id']}\nA = {it['A']}\nB = {it['B']}"]
        for w, cands in it["windows"].items():
            lines.append(f"  Window {w}:")
            for c in cands:
                lines.append(f"   [{c['id']}] ({c['year']}) {c['title']}. {c['abstract']}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def judge(qset: str, kind: str = "judge", keys: list[str] | None = None) -> None:
    store = jload(DATA / "pair_candidates.json")
    ideas = read_jsonl(DATA / f"ideas_{qset}.jsonl")
    if keys is None:
        keys = sorted({pair_key(*p) for r in ideas if (p := idea_pair(r))})
    done = set()
    for p in (llm.JOBS / f"{kind}_out").glob("*.json") if (llm.JOBS / f"{kind}_out").exists() else []:
        try:
            done |= {j["item_id"] for j in llm.parse_json(p.read_text())["judgments"]}
        except Exception:
            pass
    queued = set()
    for p in (llm.JOBS / kind).glob("*.json") if (llm.JOBS / kind).exists() else []:
        queued |= set(jload(p)["meta"]["item_ids"])
    items = [it for it in judge_items(keys, store) if it["item_id"] not in done | queued]
    rng = random.Random(SEED)
    rng.shuffle(items)
    start = len(list((llm.JOBS / kind).glob("*.json"))) if (llm.JOBS / kind).exists() else 0
    for i in range(0, len(items), JUDGE_BATCH):
        batch = items[i:i + JUDGE_BATCH]
        prompt = llm.template("judge_match.md").format(items=render_items(batch))
        jid = f"{qset}_{start + i // JUDGE_BATCH:04d}"
        llm.write_job(kind, jid, prompt, {"item_ids": [b["item_id"] for b in batch]})
        ledger().add("matching", kind, tokens_in=est_tokens(prompt), scope="evaluation")
    print(f"queued {len(items)} items in {(len(items) + JUDGE_BATCH - 1) // JUDGE_BATCH} {kind} jobs")


def collect_judgments(kind: str = "judge") -> dict:
    out = {}
    d = llm.JOBS / f"{kind}_out"
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        for j in llm.parse_json(p.read_text())["judgments"]:
            out.setdefault(j["item_id"], {})[j["window"]] = j
    return out


def label_ideas(qset: str) -> list[dict]:
    """Attach pre/post matches to ideas. Windows with zero search results are 'no match found'."""
    store = jload(DATA / "pair_candidates.json")
    J = collect_judgments("judge")
    rows = read_jsonl(DATA / f"ideas_{qset}.jsonl")
    for r in rows:
        p = idea_pair(r)
        r["pair_key"] = pair_key(*p) if p else None
        for w in WINDOWS:
            r[f"{w}_count"] = store[r["pair_key"]][w]["count"] if p else 0
            has_cands = bool(p and store[r["pair_key"]][w]["candidates"])
            j = J.get(r["pair_key"], {}).get(w) if p else None
            if not has_cands:
                r[f"{w}_match"] = False
                r[f"{w}_judged"] = True
            elif j is None:
                r[f"{w}_match"] = None
                r[f"{w}_judged"] = False
            else:
                r[f"{w}_match"] = bool(j["match"])
                r[f"{w}_judged"] = True
                r[f"{w}_relation"] = j.get("relation")
                r[f"{w}_paper"] = j.get("paper_id")
        r["hit"] = (r["pre2020_match"] is False and r["post2019_match"] is True) \
            if None not in (r["pre2020_match"], r["post2019_match"]) else None
    write_jsonl(DATA / f"labelled_{qset}.jsonl", rows)
    n_unj = sum(1 for r in rows if r["hit"] is None)
    print(f"labelled {len(rows)} ideas; unjudged {n_unj}")
    return rows


# ---------------------------------------------------------------- CLI
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["questions", "generate", "ingest", "search", "judge", "label"])
    ap.add_argument("--set", default="pilot")
    a = ap.parse_args()
    if a.stage == "questions":
        print(json.dumps(make_questions(), indent=1))
    elif a.stage == "generate":
        generate(a.set)
    elif a.stage == "ingest":
        ingest(a.set)
    elif a.stage == "search":
        search(a.set)
    elif a.stage == "judge":
        judge(a.set)
    elif a.stage == "label":
        label_ideas(a.set)


if __name__ == "__main__":
    main()
