"""Prototype command-line tool.

    discover guided  --question "..." [--fields economics transport] [--method G|P|R|RN|B]
    discover explore --concepts "Congestion pricing" "Air quality" [--fields ...]
    discover export  --ideas results/shortlist.json --out shortlist.md

Without ANTHROPIC_API_KEY the LLM writing step is saved as a job file (the
candidate pairs and their evidence are still printed and exported).
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from . import llm, study
from .engine import Engine
from .methods import candidates as cand


def _graph_from_concepts(e: Engine, concepts: list[str], fields: list[str] | None, n: int = 10):
    """Exploratory mode: start from seed concepts and follow paths to unconnected concepts."""
    g = e.graph
    seeds = [c for c in concepts if c in g.vocab]
    missing = [c for c in concepts if c not in g.vocab]
    if missing:
        print("not in vocabulary (ignored):", missing)
    scored = []
    targets = [c for c in g.vocab if not fields or g.home_field(c) in fields]
    for a in seeds:
        # only consider concepts reachable in two hops (cheap pre-filter)
        reach = {m2 for m in g.adj[a] for m2 in g.adj[m]}
        for b in reach & set(targets):
            if g.is_novel_pair(a, b):
                s, paths = g.path_score(a, b)
                if s > 0:
                    scored.append((s, g.key(a, b), {"paths": [list(p) for p in paths]}))
    top = cand._diverse_top(scored, n)
    for c in top:
        c["evidence_ids"] = g.support_papers(tuple(c["paths"][0]))
    return top


def _print(ideas, e: Engine):
    for i, c in enumerate(ideas, 1):
        print(f"\n{i}. {c['a']}  <->  {c['b']}   (score {c.get('score', 0):.4g})")
        if c.get("paths"):
            print("   path:", " -> ".join(c["paths"][0]))
        for pid in c.get("evidence_ids", []):
            d = e.by_id[pid]
            print(f"   [{pid}] {d['year']} {d['title'][:110]}")
        if c.get("hypothesis"):
            print("   hypothesis:", c["hypothesis"])


def export(ideas: list[dict], out: Path) -> None:
    if out.suffix == ".csv":
        with out.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["rank", "a", "b", "hypothesis", "test", "disconfirming", "sources"])
            for i, c in enumerate(ideas, 1):
                w.writerow([i, c["a"], c["b"], c.get("hypothesis", ""), c.get("test", ""),
                            c.get("disconfirming", ""), json.dumps(c.get("sources") or c.get("evidence_ids"))])
    else:
        lines = ["# Shortlist", ""]
        for i, c in enumerate(ideas, 1):
            lines += [f"## {i}. {c['a']} ↔ {c['b']}", ""]
            for k in ("hypothesis", "test", "disconfirming"):
                if c.get(k):
                    lines.append(f"- **{k.capitalize()}:** {c[k]}")
            if c.get("paths"):
                lines.append(f"- **Path:** {' → '.join(c['paths'][0])}")
            src = c.get("sources") or [{"paper_id": p} for p in c.get("evidence_ids", [])]
            for s in src:
                lines.append(f"- Source: https://openalex.org/{s['paper_id']} {s.get('role', '')}")
            lines.append("")
        out.write_text("\n".join(lines))
    print("wrote", out)


def main() -> None:
    ap = argparse.ArgumentParser(prog="discover")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("guided"); g.add_argument("--question", required=True)
    g.add_argument("--fields", nargs="*"); g.add_argument("--method", default="G", choices=["G", "P", "R", "RN", "B"])
    g.add_argument("--out", default="results/shortlist.json")
    x = sub.add_parser("explore"); x.add_argument("--concepts", nargs="+", required=True)
    x.add_argument("--fields", nargs="*"); x.add_argument("--out", default="results/shortlist.json")
    ex = sub.add_parser("export"); ex.add_argument("--ideas", required=True); ex.add_argument("--out", required=True)
    a = ap.parse_args()

    if a.cmd == "export":
        export(json.loads(Path(a.ideas).read_text()), Path(a.out))
        return
    e = Engine.load()
    study._engine = e
    if a.cmd == "explore":
        ideas = _graph_from_concepts(e, a.concepts, a.fields)
    else:
        q = {"qid": "adhoc", "text": a.question, "field": None}
        if a.method == "B":
            ideas = cand.popularity(e, a.question)
        else:
            prompt, meta = study.build_generation_job(a.method, q)
            ideas = meta.get("candidates", [])
            out = llm.run("adhoc", f"adhoc__{a.method}", prompt, meta)
            if out:
                ideas = out["ideas"]
            else:
                print(f"(no API key: writing step queued in {llm.JOBS / 'adhoc'})")
        if a.fields:
            ideas = [c for c in ideas if e.graph.home_field(c["a"]) in a.fields or e.graph.home_field(c["b"]) in a.fields] or ideas
    _print(ideas, e)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(ideas, indent=1))
    print("\nsaved", a.out)


if __name__ == "__main__":
    main()
