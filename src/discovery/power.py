"""Power simulation for the 40-question paired comparison (Amendment 1, item 6).

Per question and method, the hit count is Binomial(10, p_q), where p_q ~ Beta with
mean = the method's rate and a shared question effect (correlation between methods
on the same question). Reports power of the two-sided Wilcoxon signed-rank test
(Pratt), the expected share of tied questions, and the minimum detectable
difference at 80% power.

    python -m discovery.power --base 0.05 0.10 0.20
"""
from __future__ import annotations

import argparse
import json

import numpy as np
from scipy import stats

from .study import RESULTS

SLOTS = 10


def simulate(base: float, delta: float, n_q: int = 40, sims: int = 1000, kappa: float = 8.0,
             seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    rej, ties = 0, 0.0
    for _ in range(sims):
        # shared question difficulty on the logit scale, then per-method Beta noise
        q = rng.normal(0, 0.5, n_q)
        def rates(mean):
            m = np.clip(1 / (1 + np.exp(-(np.log(mean / (1 - mean)) + q))), 1e-4, 1 - 1e-4)
            return rng.beta(m * kappa, (1 - m) * kappa)
        pa = rates(min(base + delta, 0.95))
        pb = rates(base)
        xa = rng.binomial(SLOTS, pa) / SLOTS
        xb = rng.binomial(SLOTS, pb) / SLOTS
        d = xa - xb
        ties += np.mean(d == 0)
        if np.all(d == 0):
            continue
        p = stats.wilcoxon(xa, xb, zero_method="pratt").pvalue
        rej += p < 0.05
    return {"base": base, "delta": delta, "power": rej / sims, "mean_tie_share": ties / sims}


def mdd(base: float, n_q: int = 40, target: float = 0.8, **kw) -> dict:
    grid = [0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30]
    rows = [simulate(base, d, n_q=n_q, **kw) for d in grid]
    hit = next((r["delta"] for r in rows if r["power"] >= target), None)
    return {"base": base, "n_questions": n_q, "minimum_detectable_difference_80pct": hit, "grid": rows}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", nargs="+", type=float, default=[0.02, 0.05, 0.10, 0.20])
    ap.add_argument("--sims", type=int, default=600)
    a = ap.parse_args()
    out = [mdd(b, sims=a.sims) for b in a.base]
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "power.json").write_text(json.dumps(out, indent=1))
    for o in out:
        print(o["base"], o["minimum_detectable_difference_80pct"],
              [(r["delta"], round(r["power"], 2), round(r["mean_tie_share"], 2)) for r in o["grid"]])
