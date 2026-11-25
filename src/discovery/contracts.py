"""Strict output contracts for LLM judge outputs (review finding C05) and split hygiene (Amendment 6).

- JSON booleans only: "false", 0, null are schema errors, never coerced with bool().
- The judgments must cover exactly the job's expected item ids, once each per window.
- A cited paper_id must be one of the item's candidate papers.
- Quote-anchored judges (J1): the quote must occur in the cited paper's title or abstract as the judge
  saw it, after Unicode/whitespace/case/quote-mark normalisation; "..." separates fragments that must
  each occur. A match whose quote is not found is counted as no match and flagged.
"""
from __future__ import annotations

import json
import re
import unicodedata

from .study import pair_key


class SchemaError(ValueError):
    pass


_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                         "−": "-", " ": " "})


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").translate(_QUOTES).lower()
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def quote_in_text(quote: str, text: str) -> bool:
    """Every fragment of the quote (split on ellipses) occurs in the text, after normalisation."""
    q = normalise(quote).strip(" \"'")
    t = normalise(text)
    frags = [f.strip(" \"'.,;:") for f in re.split(r"\.\.\.|…|\[\.\.\.\]", q)]
    frags = [f for f in frags if f]
    return bool(frags) and all(f in t for f in frags)


def paper_text(p: dict) -> str:
    return f"{p.get('title') or ''}. {p.get('abstract') or ''}"


def parse_judgments(text: str, id_map: dict, items: dict | None = None, quote_judge: bool = False) -> dict:
    """Validate one judge output against its job.

    id_map: opaque item_id -> key (the job's expected ids).
    items: key -> {"windows": {window: [papers]}} (what the judge saw), for paper-id and quote checks.
    Returns key -> {"match": bool, "window", "paper_id", "quote", "quote_ok"}. Raises SchemaError.
    """
    m = re.search(r"\{.*\}", (text or "").strip(), re.S)
    if not m:
        raise SchemaError("no JSON object")
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise SchemaError(f"invalid JSON: {exc}") from exc
    js = obj.get("judgments") if isinstance(obj, dict) else None
    if not isinstance(js, list):
        raise SchemaError("'judgments' must be a list")
    out, seen = {}, set()
    for j in js:
        if not isinstance(j, dict):
            raise SchemaError("judgment is not an object")
        iid = j.get("item_id")
        if iid not in id_map:
            raise SchemaError(f"unexpected item_id {iid!r}")
        key = id_map[iid]
        win = j.get("window")
        if items is not None:
            wins = list(items[key]["windows"])
            if win is None and len(wins) == 1:
                win = wins[0]
            if win not in wins:
                raise SchemaError(f"{iid}: window {win!r} not among {wins}")
        if (iid, win) in seen:
            raise SchemaError(f"duplicate judgment for {iid} / {win}")
        seen.add((iid, win))
        if not isinstance(j.get("match"), bool):
            raise SchemaError(f"{iid}: 'match' must be a JSON boolean, got {j.get('match')!r}")
        rec = {"match": j["match"], "window": win, "paper_id": j.get("paper_id"), "quote": j.get("quote"),
               "quote_ok": None}
        if j["match"] and items is not None:
            papers = {str(p.get("id")): p for p in items[key]["windows"][win]}
            pid = str(j.get("paper_id")) if j.get("paper_id") is not None else None
            if pid not in papers:
                if len(papers) == 1 and pid is None:
                    pid = next(iter(papers))
                else:
                    raise SchemaError(f"{iid}: paper_id {j.get('paper_id')!r} is not a candidate of this item")
            rec["paper_id"] = pid
            if quote_judge:
                q = j.get("quote")
                rec["quote_ok"] = bool(isinstance(q, str) and q.strip() and len(q.split()) <= 40
                                       and quote_in_text(q, paper_text(papers[pid])))
                if not rec["quote_ok"]:
                    rec["match"] = False  # quote-anchored rule: no verifiable quote, no match
        out[key] = rec
    expected = set(id_map)
    got = {iid for iid, _ in seen}
    if got != expected:
        raise SchemaError(f"missing judgments for {sorted(expected - got)[:5]}")
    return out


# ---------------------------------------------------------------- Amendment 6: split overlap
def overlap_pairs(selection: dict, holdout: dict) -> set[str]:
    sel = {pair_key(u["a"], u["b"]) for t in ("positives", "hard_negatives") for u in selection.get(t, [])}
    return {pair_key(u["a"], u["b"]) for t in ("positives", "hard_negatives") for u in holdout.get(t, [])} & sel


def exclude_overlap(holdout: dict, selection: dict) -> tuple[dict, list[str]]:
    """Holdout units whose concept pair also appears in selection are excluded from analysis (Amendment 6).
    Returns the filtered units and the excluded uids (logged; the split file itself is not modified)."""
    bad = overlap_pairs(selection, holdout)
    kept, dropped = {}, []
    for t in ("positives", "hard_negatives"):
        kept[t] = []
        for u in holdout.get(t, []):
            if pair_key(u["a"], u["b"]) in bad:
                dropped.append(u["uid"])
            else:
                kept[t].append(u)
    return kept, dropped
