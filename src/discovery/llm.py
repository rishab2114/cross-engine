"""LLM provider interface.

If ANTHROPIC_API_KEY is set, prompts are sent to the Anthropic Messages API.
Otherwise each prompt is written as a job file (jobs/<kind>/<id>.json) for an
external runner (in this study: Claude subagents) to answer into
jobs/<kind>_out/<id>.json. Either way, the prompt text and output are stored.

Job identity (review finding C04):
- A job's prompt is immutable once written: rewriting it with different text or metadata raises
  JobConflict (unless replace=True and no output exists yet).
- The sidecar records the prompt's SHA-256; an output is only returned if the job file still holds
  that prompt (provenance check).
- run() persists the prompt and metadata before either the API or the file runner executes it.
- job_digest() gives content-derived ids, and stable_seed() replaces process-randomised hash().
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


class JobConflict(RuntimeError):
    """A job id was reused for different input, or an output no longer matches its job."""


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def stable_seed(*parts) -> int:
    """Deterministic across processes (unlike hash(), which is randomised per process for str)."""
    return int(sha256("|".join(map(str, parts)))[:8], 16)


def job_digest(kind: str, prompt: str, model: str | None = None, max_tokens: int | None = None, **extra) -> str:
    """Content-derived job id suffix: kind, prompt (which embeds the question and evidence), model, decoding."""
    payload = json.dumps({"kind": kind, "prompt": prompt, "model": model or MODEL, "max_tokens": max_tokens,
                          **extra}, sort_keys=True)
    return sha256(payload)[:16]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    tmp.write_text(text)
    os.replace(tmp, path)


def _norm(meta: dict | None) -> dict:
    return json.loads(json.dumps(meta or {}))


def template(name: str) -> str:
    return (PROMPTS / name).read_text()


def prompt_hashes() -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in sorted(PROMPTS.glob("*.md"))}


def write_job(kind: str, job_id: str, prompt: str, meta: dict | None = None, replace: bool = False) -> Path:
    """Write the prompt-only job file (what the runner reads) and a separate meta sidecar.

    The sidecar (jobs/<kind>_meta/<id>.json) holds id maps, methods and candidates. Runners
    are never pointed at it, so blinding labels cannot leak into a judge's or writer's input.
    Writing the same job again is a no-op; writing different input under an existing id raises.
    """
    d = JOBS / kind
    p = d / f"{job_id}.json"
    sc = JOBS / f"{kind}_meta" / f"{job_id}.json"
    meta = {**_norm(meta), "_prompt_sha256": sha256(prompt)}
    if p.exists():
        old_prompt = json.loads(p.read_text()).get("prompt")
        old_meta = json.loads(sc.read_text()) if sc.exists() else None
        same_meta = old_meta is None or {k: v for k, v in old_meta.items() if k != "_prompt_sha256"} == \
            {k: v for k, v in meta.items() if k != "_prompt_sha256"}
        if old_prompt == prompt and same_meta:
            if old_meta is not None and "_prompt_sha256" not in old_meta and not out_path(kind, job_id).exists():
                _atomic_write(sc, json.dumps(meta, indent=1))
            return p
        if out_path(kind, job_id).exists() or not replace:
            raise JobConflict(f"{kind}/{job_id}: job exists with different {'prompt' if old_prompt != prompt else 'metadata'}"
                              f"{' and has an output' if out_path(kind, job_id).exists() else ''}; use a new job id")
    _atomic_write(p, json.dumps({"id": job_id, "kind": kind, "prompt": prompt}, indent=1))
    _atomic_write(sc, json.dumps(meta, indent=1))
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


def check_provenance(kind: str, job_id: str) -> None:
    """Raise if the job file no longer holds the prompt recorded when it was written."""
    sc = JOBS / f"{kind}_meta" / f"{job_id}.json"
    jp = JOBS / kind / f"{job_id}.json"
    if not (sc.exists() and jp.exists()):
        return
    want = json.loads(sc.read_text()).get("_prompt_sha256")
    if want and sha256(json.loads(jp.read_text()).get("prompt", "")) != want:
        raise JobConflict(f"{kind}/{job_id}: job prompt changed after it was recorded; output provenance unknown")


def read_output(kind: str, job_id: str) -> dict | None:
    p = out_path(kind, job_id)
    if not p.exists():
        return None
    check_provenance(kind, job_id)
    return parse_json(p.read_text())


def run(kind: str, job_id: str, prompt: str, meta: dict | None = None, max_tokens: int = 8000) -> dict | None:
    """Return the parsed output if available (API or a filled job file), else queue a job.

    The job (prompt + meta) is persisted before execution on both paths; an existing job id with a
    different prompt raises JobConflict instead of returning another prompt's answer.
    """
    jp = JOBS / kind / f"{job_id}.json"
    if jp.exists() and json.loads(jp.read_text()).get("prompt") != prompt:
        raise JobConflict(f"{kind}/{job_id}: existing job has a different prompt")
    meta = {**_norm(meta), "_model": MODEL, "_max_tokens": max_tokens}
    write_job(kind, job_id, prompt, meta)
    existing = read_output(kind, job_id)
    if existing is not None:
        return existing
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]},
        timeout=600,
    )
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json()["content"])
    _atomic_write(out_path(kind, job_id), text)
    return parse_json(text)
