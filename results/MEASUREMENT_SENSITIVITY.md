# Measurement sensitivity: how the matcher changes the answer

**Lead finding.** On the same 100 pilot ideas, the estimated performance of the idea-generation methods depends heavily on the literature matcher used to score them. The **share of ideas "already studied by 2019" nearly doubles** with a better-recall matcher. **The sign of G − RN flips** between matchers. **Only 1 of 35 pair-level "later matches" actually tests the proposed hypothesis.** A retrospective benchmark built on pair-level matching with an unvalidated matcher can therefore rank methods differently, or for the wrong reason.

**Scope.** 2 questions, 100 ideas, 5 methods. None of the three matchers passed validation (see `MATCHER_VALIDATION.md`), and all share a judge with 84% precision. This is evidence about **measurement fragility**, not about which method is better.

Rebuild everything with `python -m discovery.sensitivity --set pilot` → `results/measurement_sensitivity_pilot.json`.

## Measurements compared
| Name | What it is | Validation status |
|---|---|---|
| fixed | Preregistered exact-phrase search, top 5 (original labels, unchanged) | Failed: post-2019 control recall 67%, audit miss 47–56% |
| widened | Amendment 1 rule: OR-ed related keywords, top 10 (unchanged) | Failed: post-2019 control recall 33% |
| A | Word-level search, top 5 (exploratory; best recall per unit of cost on the selection set) | Failed: judge precision 84%, audit miss before 2020 33% |

All three use the same blind production judge (`prompts/judge_match.md`).

## 1. The same ideas, three different pictures
**Share of ideas already studied by 2019** (pair-level earlier match):

| Method | fixed | widened | A |
|---|---|---|---|
| G graph paths | 50% | 50% | **90%** |
| P path ranking off | 15% | 15% | 30% |
| R retrieval + brainstorm | 45% | 45% | 70% |
| RN retrieval + novelty filter | 10% | 5% | 30% |
| B popularity | 85% | 75% | 90% |

**Share with any later (2020–2024) pair-level match:**

| Method | fixed | widened | A |
|---|---|---|---|
| G | 40% | 55% | 65% |
| P | 10% | 20% | 20% |
| R | 35% | 45% | 60% |
| RN | 0% | 5% | 15% |
| B | 55% | 70% | 85% |

**Retrospective match rate** (no earlier match, later match; the preregistered primary outcome):

| Method | fixed | widened | A |
|---|---|---|---|
| G | 5% | 15% | 0% |
| P | 0% | 5% | 0% |
| R | 5% | 20% | 5% |
| RN | 0% | 5% | 5% |
| B | 0% | 10% | 0% |

With better recall (A), most G pairs turn out to have been studied **before 2020**: 90% versus 50% under the fixed search. "Zero co-occurrence in the 60k-paper corpus" is a weak novelty filter, and the exact-phrase search hid that.

## 2. Estimated differences between methods
Idea-level difference in the retrospective match rate, with a 95% bootstrap CI (10,000 resamples):

| Comparison | fixed | widened | A | Sign flips? |
|---|---|---|---|---|
| G − R (primary) | 0.00 (−0.15, 0.15) | −0.05 (−0.30, 0.20) | −0.05 (−0.15, 0.00) | no (0 → −) |
| G − P (path-ranking ablation) | +0.05 (0.00, 0.15) | +0.10 (−0.10, 0.30) | 0.00 | no (+ → 0) |
| G − RN (shared filter) | +0.05 (0.00, 0.15) | +0.10 (−0.05, 0.30) | **−0.05** (−0.15, 0.00) | **yes** |
| G − B | +0.05 (0.00, 0.15) | +0.05 (−0.15, 0.25) | 0.00 | no |
| R − B | +0.05 (0.00, 0.15) | +0.10 (−0.10, 0.30) | +0.05 (0.00, 0.15) | no |

With 20 ideas per method, every interval is wide and none of these differences is meaningful on its own. The point is that **the direction of a key comparison (G vs RN) depends on the matcher**.

## 3. Pair-level matches are not hypothesis tests
For the 35 pilot ideas with a pair-level later match (under the fixed or widened search), a blind judge (`prompts/judge_hypothesis.md`) checked whether the matched paper tests **the proposed hypothesis**.

| Method | Same hypothesis | Related (same concepts, different relationship) | Different |
|---|---|---|---|
| G | 0 | 4 | 12 |
| P | 0 | 0 | 5 |
| R | 1 | 8 | 4 |
| RN | 0 | 1 | 0 |
| **Total** | **1 (3%)** | 13 (37%) | 21 (60%) |

The preregistered primary outcome counts a match when a later paper explicitly links A and B. Almost none of those papers test what the idea proposed, so **the pair-level match rate measures rediscovery of a connection, not confirmation of a hypothesis.**

## 4. What this means
1. **Retrospective benchmarks need a validated matcher before comparing methods.** Here, a matcher change moved one method's "already studied" share by 40 points and flipped a comparison.
2. **Report pair-level and hypothesis-level matching separately.** They answer different questions. The second is rare (3%), so it needs far larger samples.
3. **Novelty filters based on corpus co-occurrence overstate novelty.** A better matcher finds that most "unconnected" pairs were already studied.
4. **These are pilot-scale observations.** A methods paper needs the same comparison on many more questions, with a matcher and judge validated against **human** labels.

## Limitations
- Two questions and 100 ideas; the CIs are wide.
- All three measurements share one LLM judge (84% precision on hard negatives), and the reference labels come from the same model family.
- Matcher A was not validated; it is shown as one exploratory measurement.
- Hypothesis-level judgments cover only ideas with a fixed or widened pair-level later match.
