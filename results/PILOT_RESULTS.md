# Pilot results (2 questions)

**Bottom line.** The pipeline runs end to end. The literature search used to measure the outcome **failed validation**, and the pre-set widened search failed too. Until the measurement problem is fixed, the 40-question main run would not give a trustworthy answer, so it stays on hold (Amendment 3). Two questions give no basis for choosing a winning method, and none is claimed here.

**Metadata provenance.** The OpenAlex snapshot is dated 19 Nov 2026. OpenAlex replaced its topic classifier on 6 Oct 2026, with further taxonomy updates in November. Our topics (used for field selection) and keywords (graph nodes) are therefore current assignments, not 2019-era indexing.

All numbers below come from committed files. `python -m discovery.analysis --set pilot [--suffix _widened]` rebuilds them.

---

## 1. Shortlist sizes
Every method filled every slot: 10 ideas per method per question, 100 ideas in total, 100 distinct concept pairs.

| Method | Ideas | Fill rate | Pairs with zero co-occurrence in the sampled corpus | Pairs with a graph path |
|---|---|---|---|---|
| G (graph paths) | 20 | 100% | 20 | 20 |
| P (path ranking off) | 20 | 100% | 20 | 18 |
| R (retrieval + brainstorm) | 20 | 100% | 12 | n/a |
| RN (retrieval + novelty filter) | 20 | 100% | 20 | n/a |
| B (popularity, no LLM) | 20 | 100% | 20 | n/a |

RN kept 10 of 30 over-generated ideas per question; no second round was needed.

## 2. Is the literature search valid? No
### Known-match controls (recall)
| Window | Confirmed controls | Fixed search recall | Widened search recall |
|---|---|---|---|
| Before 2020 | 7 of 10 | **100%** (7 of 7) | 71% (5 of 7) |
| 2020–2024 | 6 of 10 | **67%** (4 of 6) | **33%** (2 of 6) |

A control counts only if the judge confirmed that its source paper explicitly studies the pair. Seven controls were not confirmed: the keywords were tagged together, but the paper did not explicitly link them.

### Independent search audit (30 pairs, blinded)
An independent searcher subagent with open OpenAlex access, no top-5 limit and citation trails, and no sight of any pipeline result, searched each pair.

| Window | Pipeline found no match | ...but the auditor found one | **Miss rate** (fixed) | Miss rate (widened) | Pipeline matches the auditor contradicted |
|---|---|---|---|---|---|
| Before 2020 | 16 | 9 | **56%** | 56% | 0 of 14 |
| 2020–2024 | 15 | 7 | **47%** | 56% | 0 of 15 |

**Misses by method** (fixed search, after unblinding): R accounts for 5 of 9 earlier misses and 3 of 7 later misses; B for 2 and 2; G for 1 and 1; RN for 1 and 1; P for 0 and 0.

**What this means:**
- The fixed search is **precise but blind to about half of real matches.** Every match it found was real, but it missed roughly half of them.
- The misses are not spread evenly across methods. R's ideas are written in natural phrasing, which an exact-phrase search misses. So measurement error **differs by method**, and that could change the ranking.
- The **pre-set widening rule made recall worse.** OR-ing related keywords ("stock returns" OR "asset pricing" …) fills the top 10 with papers about the added terms and pushes out the actual A–B papers.
- The sample is small (30 pairs, 13 confirmed controls), so these rates are rough. They are still far beyond the 20% and 80% thresholds.

## 3. Judge stability
- The first judging round was redone after a blinding fix (Amendment 2). The two rounds agree on **98%** of verdicts (138 of 141): 98% on real items and 97% on controls. Judging is stable; the search is the weak link.
- One widened-search judge, unable to load a 71k-token job in one read, used Grep on its own job file to read it in pieces. No other files were opened. This breaks the runner rules but not blinding. Future judge batches will be sized under about 30k tokens.

## 4. Measured cost
| Unit | Tokens (subagent total) | Wall-clock |
|---|---|---|
| Generation, 1 runner × 5 jobs (planned batch size) | 187,523 (≈ 37.5k per job) | 165 s |
| Generation, 1 runner × 2 jobs (pilot) | 125k–140k | 70–90 s |
| Judging, 1 runner × 2 batches of 25 items (fixed search) | ≈ 182k | ≈ 100 s |
| Judging, widened search (10 candidates per window) | 160k–195k per **single** job | 50–140 s |
| Independent audit, 10 pairs | 138k–149k | 180–200 s |
| One-off setup: graph build / retrieval index | n/a | 2 s / 50 s CPU |

**Main-run projection** (fixed search, 40 questions, about 2,000 ideas): about 5.8M tokens for generation, 4.3M for judging and about 1M for the second judge, leakage probe and citation checks. **Total ≈ 11–12M tokens**, over several 5-hour usage windows. Using agentic, open search as the matcher (the method the auditor used) would cost about 14k tokens per pair, or about 28M for 2,000 pairs.

## 5. Power (simulated, 40 questions)
| Base match rate | Minimum detectable difference at 80% power | Expected share of tied questions |
|---|---|---|
| 2% (about the pilot, fixed search) | 6 points | 52–67% |
| 5% | 8 points | 35–47% |
| 10% (about the pilot, widened search) | 10 points | 23–32% |
| 20% | 15 points | 15–19% |

Wilcoxon (Pratt) with question-level correlation; see `results/power.json`. Any real difference smaller than about 6–10 points would likely go undetected, and measurement error of the size above would weaken any real difference further.

## 6. Descriptive rates (no basis for choosing a winner)
Retrospective match rate: no earlier match found, and a later match found. Mean over 2 questions, out of 10 slots.

| Method | Fixed search | Widened search | Already studied by 2019 (fixed) | Any later match (fixed) |
|---|---|---|---|---|
| G | 5% | 15% | 50% | 40% |
| P | 0% | 5% | 15% | 10% |
| R | 5% | 20% | 45% | 35% |
| RN | 0% | 5% | 10% | 0% |
| B | 0% | 10% | 85% | 55% |

The rates triple or quadruple when only the search changes. **The measurement instrument, not the method, is currently the biggest source of variation.** G's pairs are often already studied by 2019 (50%), consistent with "zero co-occurrence in a 60k sample" being a weak novelty filter. RN's and P's pairs rarely match in either window. They may be genuinely unexplored, or the search may miss them; the audit suggests misses are common.

## 7. What has to happen before the main run
1. **Fix the matcher.** The candidates, to be tested on the same 30 audit pairs and 13 confirmed controls before anything is chosen:
   - (a) word-level search without exact phrases, plus the original terms required in the title or abstract
   - (b) near-synonym expansion only (string or embedding similarity), not co-occurring keywords
   - (c) agentic open search as the matcher, which is what the audit did: higher cost, apparently much higher recall
   - (d) a mix: the fixed search first, then agentic search only for "no match" pairs

   Adopt one only by a dated amendment, and only if it reaches control recall ≥ 80% and an audit miss rate ≤ 20%.
2. **Repeat the audit with a human** on the same sheet (`results/search_audit_sheet.csv`). The subagent auditor may be lenient ("close variants" counted).
3. **Decide the budget:** about 11–12M tokens with the fixed matcher, more with agentic matching. Or reduce to 20 questions by amendment, accepting less power.
