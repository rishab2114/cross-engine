"""Build the frozen pre-2020 corpus and write its snapshot manifest.

Selection uses a fixed-seed random sample within each field x year. No citation
counts (which include post-2019 citations) are used for selection.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from . import openalex as oa

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

FIELDS = {
    "economics": "primary_topic.field.id:20",
    "transport": "primary_topic.subfield.id:3313",
}
YEARS = range(2000, 2020)
PER_FIELD_YEAR = 1500
SEED = 20191231
BASE_FILTER = "has_abstract:true,type:article,language:en"

# Concepts used as graph nodes: OpenAlex level >= 2 with score >= MIN_SCORE.
MIN_LEVEL = 2
MIN_SCORE = 0.35


def slim(w: dict, field: str) -> dict:
    concepts = [
        c["display_name"] for c in (w.get("concepts") or [])
        if c.get("level", 0) >= MIN_LEVEL and c.get("score", 0) >= MIN_SCORE
    ]
    return {
        "id": w["id"].rsplit("/", 1)[-1],
        "doi": w.get("doi"),
        "title": w.get("title") or "",
        "year": w.get("publication_year"),
        "field": field,
        "abstract": oa.reconstruct_abstract(w.get("abstract_inverted_index")),
        "concepts": sorted(set(concepts)),
        "keywords": [k["display_name"] for k in (w.get("keywords") or [])],
        "topic": (w.get("primary_topic") or {}).get("display_name"),
        "topic_id": ((w.get("primary_topic") or {}).get("id") or "").rsplit("/", 1)[-1],
    }


def build(per_field_year: int = PER_FIELD_YEAR, years=YEARS, out: Path | None = None) -> Path:
    out = out or DATA / "corpus.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    counts = {}
    seen = set()
    with out.open("w") as fh:
        for field, flt in FIELDS.items():
            for y in years:
                f = f"{flt},publication_year:{y},{BASE_FILTER}"
                works = oa.sample_works(f, per_field_year, seed=SEED + y)
                n = 0
                for w in works:
                    rec = slim(w, field)
                    assert rec["year"] is not None and rec["year"] <= 2019
                    if rec["id"] in seen or not rec["abstract"]:
                        continue
                    seen.add(rec["id"])
                    fh.write(json.dumps(rec) + "\n")
                    n += 1
                counts[f"{field}:{y}"] = n
                print(field, y, n, flush=True)
    write_manifest(out, counts, per_field_year)
    return out


def write_manifest(path: Path, counts: dict, per_field_year: int) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "snapshot_date": dt.date.today().isoformat(),
        "source": "OpenAlex API (api.openalex.org)",
        "fields": FIELDS,
        "base_filter": BASE_FILTER,
        "years": [min(YEARS), max(YEARS)],
        "selection": "fixed-seed random sample within field x year (OpenAlex sample+seed); seed = SEED + year",
        "seed_base": SEED,
        "per_field_year_cap": per_field_year,
        "concept_rule": f"OpenAlex concepts with level >= {MIN_LEVEL} and score >= {MIN_SCORE}",
        "no_citation_ranking": True,
        "note": ("OpenAlex metadata (topics, concepts, citation links) is revised over time; "
                 "this snapshot date fixes the version used. Topic/concept tags are assigned by "
                 "OpenAlex's current classifiers, not by 2019-era indexing."),
        "counts": counts,
        "total": sum(counts.values()),
        "sha256": digest,
    }
    (path.parent / "corpus_manifest.json").write_text(json.dumps(manifest, indent=2))


def load(path: Path | None = None) -> list[dict]:
    path = path or DATA / "corpus.jsonl"
    return [json.loads(l) for l in path.open()]


if __name__ == "__main__":
    build()
