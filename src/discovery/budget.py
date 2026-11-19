"""Token and wall-clock ledger. Tokens are estimated as characters / 4."""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path


def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self.rows: list[dict] = json.loads(path.read_text()) if path.exists() else []

    def add(self, method: str, stage: str, tokens_in: int = 0, tokens_out: int = 0,
            seconds: float = 0.0, scope: str = "per_query", **extra) -> None:
        self.rows.append({"method": method, "stage": stage, "scope": scope,
                          "tokens_in": tokens_in, "tokens_out": tokens_out,
                          "seconds": round(seconds, 3), **extra})
        self.save()

    @contextmanager
    def timed(self, method: str, stage: str, scope: str = "setup", **extra):
        t0 = time.time()
        yield
        self.add(method, stage, seconds=time.time() - t0, scope=scope, **extra)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.rows, indent=1))

    def summary(self) -> dict:
        out: dict = {}
        for r in self.rows:
            m = out.setdefault(r["method"], {"setup_seconds": 0.0, "query_seconds": 0.0,
                                             "tokens_in": 0, "tokens_out": 0})
            if r["scope"] == "setup":
                m["setup_seconds"] += r["seconds"]
            else:
                m["query_seconds"] += r["seconds"]
            m["tokens_in"] += r["tokens_in"]
            m["tokens_out"] += r["tokens_out"]
        return out
