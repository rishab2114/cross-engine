"""Minimal OpenAlex client: cursor/sample paging, on-disk cache, abstract reconstruction."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

BASE = "https://api.openalex.org"
CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"

WORK_SELECT = ",".join([
    "id", "title", "publication_year", "abstract_inverted_index", "concepts",
    "keywords", "primary_topic", "referenced_works", "doi",
])


def reconstruct_abstract(inv: dict | None) -> str:
    """Rebuild abstract text from OpenAlex's inverted index."""
    if not inv:
        return ""
    pos: dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def _cache_path(url: str, params: dict) -> Path:
    key = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    return CACHE / f"{key}.json"


COST_LOG = CACHE.parent / "openalex_costs.jsonl"
DAILY_CAP_USD = 0.90          # free mode: stay inside the $1/day free allowance
_last_remaining_usd: float | None = None


class BudgetExceeded(RuntimeError):
    """Raised instead of making an OpenAlex request that could go past the free daily allowance."""


def spent_today_usd() -> float:
    """Cost logged since 00:00 UTC today (requests made through this module)."""
    if not COST_LOG.exists():
        return 0.0
    import datetime as _dt
    midnight = _dt.datetime.now(_dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    total = 0.0
    for line in COST_LOG.open():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("t", 0) >= midnight:
            total += float(rec.get("cost_usd", 0))
    return total


def check_budget() -> None:
    spent = spent_today_usd()
    if spent >= DAILY_CAP_USD:
        raise BudgetExceeded(f"OpenAlex daily cap reached: ${spent:.3f} logged today >= ${DAILY_CAP_USD:.2f}")
    if _last_remaining_usd is not None and _last_remaining_usd <= 1.0 - DAILY_CAP_USD:
        raise BudgetExceeded(f"OpenAlex account reports only ${_last_remaining_usd:.3f} left today")


def _log_cost(path: str, params: dict, cost: str | None) -> None:
    """Append the billed cost of each uncached request (OpenAlex X-RateLimit-Cost-USD header)."""
    try:
        COST_LOG.parent.mkdir(parents=True, exist_ok=True)
        kind = "search" if (any("search" in k for k in params) or "search" in str(params.get("filter", ""))) else (
            "singleton" if "/" in path.strip("/") else "list")
        with COST_LOG.open("a") as fh:
            fh.write(json.dumps({"t": time.time(), "kind": kind, "cost_usd": float(cost or 0)}) + "\n")
    except Exception:
        pass


def get(path: str, params: dict | None = None, use_cache: bool = True, retries: int = 5) -> dict:
    params = dict(params or {})
    url = f"{BASE}/{path.lstrip('/')}"
    cp = _cache_path(url, params)
    if use_cache and cp.exists():
        return json.loads(cp.read_text())
    check_budget()
    delay = 1.0
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=60)
            global _last_remaining_usd
            try:
                _last_remaining_usd = float(r.headers.get("X-RateLimit-Remaining-USD"))
            except (TypeError, ValueError):
                pass
            if r.status_code == 200:
                data = r.json()
                _log_cost(path, params, r.headers.get("X-RateLimit-Cost-USD"))
                CACHE.mkdir(parents=True, exist_ok=True)
                cp.write_text(json.dumps(data))
                return data
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay *= 2
                continue
            r.raise_for_status()
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"OpenAlex request failed: {url} {params}")


def sample_works(filter_str: str, n: int, seed: int, select: str = WORK_SELECT) -> list[dict]:
    """Fixed-seed random sample of up to n works matching filter (no ranking by citations)."""
    out: list[dict] = []
    page = 1
    while len(out) < n:
        data = get("works", {
            "filter": filter_str, "sample": n, "seed": seed,
            "per_page": 200, "page": page, "select": select,
        })
        res = data.get("results", [])
        if not res:
            break
        out.extend(res)
        page += 1
    # de-duplicate (OpenAlex sampling can repeat across pages)
    seen, uniq = set(), []
    for w in out:
        if w["id"] not in seen:
            seen.add(w["id"])
            uniq.append(w)
    return uniq[:n]


def count_works(filter_str: str, search: str | None = None) -> int:
    params = {"filter": filter_str, "per_page": 1, "select": "id"}
    if search:
        params["search"] = search
    return get("works", params)["meta"]["count"]


def search_works(filter_str: str, search: str, per_page: int = 5,
                 select: str = "id,title,publication_year,abstract_inverted_index,doi") -> list[dict]:
    data = get("works", {"filter": filter_str, "search": search, "per_page": per_page, "select": select})
    return data.get("results", [])
