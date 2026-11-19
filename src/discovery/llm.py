"""LLM provider interface.

If ANTHROPIC_API_KEY is set, prompts are sent to the Anthropic Messages API.
Otherwise each prompt is written as a job file (jobs/<kind>/<id>.json) for an
external runner (in this study: Claude subagents) to answer into
jobs/<kind>_out/<id>.json. Either way, the prompt text and output are stored.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "prompts"
JOBS = ROOT / "jobs"
MODEL = os.environ.get("DISCOVERY_MODEL", "claude-sonnet-5-5")


def template(name: str) -> str:
    return (PROMPTS / name).read_text()


def prompt_hashes() -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in sorted(PROMPTS.glob("*.md"))}


def write_job(kind: str, job_id: str, prompt: str, meta: dict | None = None) -> Path:
    """Write the prompt-only job file (what the runner reads) and a separate meta sidecar.

    The sidecar (jobs/<kind>_meta/<id>.json) holds id maps, methods and candidates. Runners
    are never pointed at it, so blinding labels cannot leak into a judge's or writer's input.
    """
    d = JOBS / kind
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{job_id}.json"
    p.write_text(json.dumps({"id": job_id, "kind": kind, "prompt": prompt}, indent=1))
    md = JOBS / f"{kind}_meta"
    md.mkdir(parents=True, exist_ok=True)
    (md / f"{job_id}.json").write_text(json.dumps(meta or {}, indent=1))
    return p


def read_meta(kind: str, job_id: str) -> dict:
    """Meta for a job: the sidecar if present, else the legacy in-file meta."""
    sc = JOBS / f"{kind}_meta" / f"{job_id}.json"
    if sc.exists():
        return json.loads(sc.read_text())
    return json.loads((JOBS / kind / f"{job_id}.json").read_text()).get("meta", {})


def out_path(kind: str, job_id: str) -> Path:
    return JOBS / f"{kind}_out" / f"{job_id}.json"


def parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in output")
    return json.loads(m.group(0))


def read_output(kind: str, job_id: str) -> dict | None:
    p = out_path(kind, job_id)
    if not p.exists():
        return None
    return parse_json(p.read_text())


def run(kind: str, job_id: str, prompt: str, meta: dict | None = None, max_tokens: int = 8000) -> dict | None:
    """Return the parsed output if available (API or a filled job file), else queue a job."""
    existing = read_output(kind, job_id)
    if existing is not None:
        return existing
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        write_job(kind, job_id, prompt, meta)
        return None
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]},
        timeout=600,
    )
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json()["content"])
    p = out_path(kind, job_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return parse_json(text)
