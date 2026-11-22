# Matcher validation (Amendment 4): result

**Recommendation: continue validation. Do not start the 40-question main run.**

No candidate matcher passed every preregistered gate on the selection set. The failure is not only in retrieval. The **production judge**, which every matcher shares, labelled 3 of 21 "mentions both, doesn't study the link" papers as matches. That puts its precision at **84% (16/19; 95% CI 60–97%)**, below the 90% gate. As Amendment 4 requires, **the holdout was never opened** (`data/matcher_selection_decision.json`, commit `9bb1918`).

All numbers come from `python -m discovery.matcher_eval --set selection` → `results/matcher_validation_selection.json`. Every rate has an exact Clopper–Pearson 95% CI.

## Validation set (selection split)
| Unit | n | Source |
|---|---|---|
| Positive controls (pair × window with a known source paper, adjudicated "explicit") | 17 (10 before 2020, 7 after 2019) | `controls.py` (seeds 4242 and 4343) |
| Hard negatives (paper × pair adjudicated "mention_only") | 21 | Fixed-search non-match papers plus control sources (Amendment 4a) |
| Classification positives (control source papers) | 17 | as above |
| Audit pair-windows (secondary; agentic reference, circular for C and D) | 36 | Pilot audit sample |

The holdout (11 positive controls, 14 hard negatives, 24 audit units) is in `data/holdout_sealed/` and was not used.

## 1. Retrieval: does the matcher's candidate list contain a judged explicit study?
| Matcher | Before 2020 | After 2019 | Known source paper retrieved (before / after) |
|---|---|---|---|
| **A** word-level | 9/10 = 90% (56–100%) | 7/7 = 100% (59–100%) | 2/10, 2/7 |
| **B** near-synonym | 9/10 = 90% (56–100%) | **4/7 = 57%** (18–90%) | 2/10, 2/7 |
| **C** agentic | 9/10 = 90% (56–100%) | 7/7 = 100% (59–100%) | 3/10, 2/7 |
| **D** hybrid (A, then C) | 10/10 = 100% (69–100%) | 7/7 = 100% (59–100%) | 3/10, 2/7 |
| S semantic (exploratory) | 7/10 = 70% (35–93%) | 2/7 = 29% (4–71%) | 0/10, 1/7 |

**Caveat.** Most "recalled" controls were recalled through a *different* paper that the judge accepted. The known source paper was retrieved only 2–3 times in 10 before 2020, and 2 in 7 after. With judge precision at 84%, some of these recalls may be false positives. **Measured retrieval recall is therefore an upper bound.**

## 2. Classification: does the production judge label a single paper correctly?
| Metric | Value |
|---|---|
| Precision (explicit-study verdicts that are right) | **16/19 = 84%** (60–97%), **fails the ≥ 90% gate** |
| Recall on positive sources | 16/17 = 94% (71–100%) |
| Specificity on hard negatives | 18/21 = 86% (64–97%) |

**The three false positives are borderline cases:**
- "export-led growth" + "J-curve": a Pakistan trade-policy paper
- "investment risk" + "long-range dependence": ICO-token risk measurement
- "block length" + "headway": railway line capacity

Two of them had been judged "explicit" by the earlier blind judging round. The reference labels come from the same model family as the judge (`prompts/adjudicate.md`). So the gap reflects **ambiguity at the edge of the matching rule** as much as judge error. Settling it needs human labels.

## 3. Audit (secondary)
Share of a matcher's no-match pair-windows where the independent agentic audit found a match.

| Matcher | Before 2020 | After 2019 | Binding? |
|---|---|---|---|
| A | **2/6 = 33%** (4–78%) | 1/6 = 17% (0–64%) | yes, **fails** before 2020 |
| B | **6/11 = 55%** (23–83%) | **6/11 = 55%** (23–83%) | yes, **fails** |
| C | 2/7 = 29% (4–71%) | 1/6 = 17% (0–64%) | no (circular) |
| D | 2/6 = 33% (4–78%) | 0/5 = 0% (0–52%) | no (circular) |

## 4. Gates and decision
| Matcher | Recall ≥ 80% | Judge precision ≥ 90% | Audit miss ≤ 20% | Pass |
|---|---|---|---|---|
| A | ✓ | ✗ | ✗ (binding) | **no** |
| B | ✗ | ✗ | ✗ (binding) | **no** |
| C | ✓ | ✗ | (not binding) | **no** |
| D | ✓ | ✗ | (not binding) | **no** |

**The decision is none.** The holdout stays sealed and no other matcher was tried on it.

## 5. Cost (measured)
- **OpenAlex, all of this phase:** 325 searches ($0.325), 5 list requests ($0.0014) and 142 free single-work lookups. That is within the $1/day free allowance (`results/openalex_quota.json`).
- **Judge runners:** 664k tokens for 23 jobs and about 228 items, so **about 2.9k tokens per judged item**, runner overhead included.
- **Agentic search C:** about 124k tokens per runner of 8 pair-windows, so **about 15.4k tokens per pair-window**, with 4.1 OpenAlex queries ($0.004) each. One runner's tokens weren't reported because it was cut off by the usage limit.
- **Reference adjudication:** 268k tokens for 92 items.

## 6. Main-run cost projection (if a matcher later passes)
Assumes about 2,000 ideas, about 2,000 distinct pairs × 2 windows = about 4,000 pair-windows, plus about 5.8M tokens to generate the ideas.

| Matcher | Tokens for matching | OpenAlex | Total with generation, 40 questions | 20 questions |
|---|---|---|---|---|
| A | ≈ 11.6M (judging) | ≈ $4 | ≈ 17M | ≈ 9M |
| C | ≈ 62M search + 11.6M judging | ≈ $16 | ≈ 80M | ≈ 40M |
| D | ≈ 11.6M + C on about 1/3 of units (≈ 24M) | ≈ $9 | ≈ 41M | ≈ 21M |

These come from runs with 6–10 items per subagent. An API key with prompt caching would cut them sharply.

## 7. What is missing before a main run (recommendation: continue validation)
1. **Fix the classifier first.** The cheap retrievers (A, and D for recall) look adequate on recall, but the judge's precision can't be confirmed. Options:
   - (a) a stricter judge prompt that requires a quoted sentence linking A and B, which is how the adjudication prompt works
   - (b) two judges with agreement required
   - (c) calibrating on human labels

   Re-test on a **fresh** labelled set, not this selection set.
2. **Human labels.** Have a person adjudicate the selection and holdout units (`results/holdout_human_sheet.csv`, exported, with the AI labels left out so the annotator is blind). Without that, the reference is not independent of the judge.
3. **Larger validation set.** About 10 positives per window gives CIs as wide as 56–100%. Aim for about 30 positives and 30 hard negatives per window.
4. **The holdout stays sealed** until a revised matcher-and-judge passes on fresh selection data.

**Gate results to keep in view:** A had good recall at low cost and failed the audit gate only before 2020 (2 of 6). D reached 100% recall on both windows in this small sample. Neither result is certified; both depend on a judge that failed the precision gate.
