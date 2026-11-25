"""Immutable run manifest for the holdout v2 evaluation (review finding C02).

Holdout mode in judge_eval and retrieval_v2 accepts only what this manifest names: one judge, its number
of repetitions, one matcher, the judge prompt's SHA-256, the reference files' hashes and the selection
commit. The manifest carries a digest of its own content; an edited, incomplete or mismatched manifest
is refused. It is written once (freeze) and never overwritten.

    python -m discovery.manifest freeze --judge J0 --matcher A
    python -m discovery.manifest show
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .study import DATA

MANIFEST = DATA / "run_manifest_v2.json"
JUDGE_PROMPTS = {"J0": "judge_match.md", "J1": "judge_match_quote.md"}
MATCHERS = ("A", "D")
SETS = ("selection", "holdout")
REFERENCES = ("units_v2_selection.json", "holdout_sealed_v2/units_v2_holdout.json")


class ManifestError(RuntimeError):
    pass


def _sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _digest(content: dict) -> str:
    body = {k: v for k, v in content.items() if k != "digest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def check_set(which: str) -> str:
    if which not in SETS:
        raise ManifestError(f"unknown set {which!r}; allowed: {SETS}")
    return which


def build(judge: str, matcher: str, repetitions: int = 1, data: Path = DATA, prompts: Path | None = None) -> dict:
    from . import llm
    prompts = prompts or llm.PROMPTS
    if judge not in JUDGE_PROMPTS:
        raise ManifestError(f"judge must be one of {sorted(JUDGE_PROMPTS)}")
    if matcher not in MATCHERS:
        raise ManifestError(f"matcher must be one of {MATCHERS}")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=data.parent, text=True).strip()
    except Exception:
        commit = None
    content = {
        "version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "judge": judge, "judge_prompt": JUDGE_PROMPTS[judge],
        "judge_prompt_sha256": _sha_file(prompts / JUDGE_PROMPTS[judge]),
        "repetitions": repetitions, "matcher": matcher,
        "references_sha256": {r: _sha_file(data / r) for r in REFERENCES if (data / r).exists()},
        "selection_commit": commit,
        "holdout_exclusion": "Amendment 6: holdout units whose concept pair also appears in selection v2",
    }
    content["digest"] = _digest(content)
    return content


def freeze(judge: str, matcher: str, repetitions: int = 1, path: Path | None = None, **kw) -> dict:
    path = path or MANIFEST
    if path.exists():
        raise ManifestError(f"{path.name} already exists; a frozen manifest is never overwritten")
    m = build(judge, matcher, repetitions, **kw)
    path.write_text(json.dumps(m, indent=1))
    return m


def load(path: Path | None = None, prompts: Path | None = None) -> dict:
    """The frozen manifest, verified. Raises ManifestError if missing, edited, incomplete or stale."""
    from . import llm
    path = path or MANIFEST
    prompts = prompts or llm.PROMPTS
    if not path.exists():
        raise ManifestError("Holdout v2 is sealed: no frozen run manifest (data/run_manifest_v2.json).")
    m = json.loads(path.read_text())
    if m.get("digest") != _digest(m):
        raise ManifestError("run manifest digest mismatch: the manifest was edited after freezing")
    if m.get("judge") not in JUDGE_PROMPTS or m.get("matcher") not in MATCHERS:
        raise ManifestError("run manifest must name one judge and one matcher")
    if not isinstance(m.get("repetitions"), int) or m["repetitions"] < 1:
        raise ManifestError("run manifest repetitions must be a positive integer")
    if _sha_file(prompts / m["judge_prompt"]) != m["judge_prompt_sha256"]:
        raise ManifestError("judge prompt changed since the manifest was frozen")
    return m


def require(judge: str | None = None, matcher: str | None = None, **kw) -> dict:
    """Load the manifest and refuse any judge or matcher other than the frozen ones."""
    m = load(**kw)
    if judge is not None and judge != m["judge"]:
        raise ManifestError(f"holdout mode accepts only the frozen judge {m['judge']}, not {judge}")
    if matcher is not None and matcher != m["matcher"]:
        raise ManifestError(f"holdout mode accepts only the frozen matcher {m['matcher']}, not {matcher}")
    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["freeze", "show"])
    ap.add_argument("--judge")
    ap.add_argument("--matcher")
    ap.add_argument("--repetitions", type=int, default=1)
    a = ap.parse_args()
    if a.cmd == "freeze":
        print(json.dumps(freeze(a.judge, a.matcher, a.repetitions), indent=1))
    else:
        print(json.dumps(load(), indent=1))
