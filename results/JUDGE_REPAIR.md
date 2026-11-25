# Judge repair and re-validation: results (DRAFT: holdout retrieval pending)

*Amendments 5, 5b and 6, plus responses to the Codex review (C01–C06). 25 November 2026. Every number below is rebuilt by the scripts named beside it. **All reference labels are model-referenced** (same-family adjudicators, agreed labels only). They measure repeatability, not independent truth; human sheets are exported for that.*

## Bottom line
- **Preregistered path (J0):** J0 was chosen as the judge on selection v2, and D (matcher A, then agentic search C on A's completed misses) was chosen as the matcher. Holdout v2 was then used **once**, through a frozen manifest:
  - **J0 classification:** precision 43/47 (91%), recall 43/43.
  - **D retrieval:** HOLDOUT_RETRIEVAL_SUMMARY.
- **Weak point (the specificity view):** J0 often calls a paper a match when it mentions both concepts without studying the link. Its specificity on hard negatives is 16/21 = 76% (selection) and 11/15 = 73% (holdout).
- **In the actual deployment population this costs little, for a specific reason.** On 40 real pilot candidate lists (C01), 63% of lists contain a true match. At that prevalence, J0's list-level precision is 22/24 = 92% (95% CI 73–99%) and it found 22/22 true matches.
- **Implication for lower base rates:** if the main run's candidate lists are less match-rich, J0's precision will fall. At 10% prevalence it would be about 42% (an implied value, not observed). The stricter quote-anchored J1 was 20/20 precise on the same lists and found 20/22.
- **Recommendation:** use J0 + D as the preregistered measurement. Report every main-run result a second time under J0 ∧ J1 as a declared sensitivity analysis. Get human labels on the contested sheets before strong claims. The main-run size (the full 40 questions, 20 per field, or a smaller run) is the user's decision.

## 1. Reference labels (Amendment 5)
`src/discovery/units_v2.py` → `data/units_v2.json`

| | Value |
|---|---|
| Candidates double-adjudicated | 238 (two independent orderings) |
| Agreement / Cohen's κ | 92.0% / 0.87 |
| Agreed positives | 129 (70 before 2020, 59 after 2019) |
| Agreed hard negatives | 36 (17 / 19); short of the target of 30 per window, reported, not relaxed |
| Contested | 19 → `results/fresh_human_sheet.csv` |
| Split | seeded 60/40; selection 77 positives + 21 hard negatives; holdout 52 + 15 |
| Selection/holdout overlap | 9 concept pairs, 0 papers. Excluded from holdout analysis (Amendment 6) |

## 2. Judge choice (selection v2)
`src/discovery/judge_eval.py` → `results/judge_validation_selection_v2.json`

| Judge | Precision | Recall | Specificity (hard negatives) | Passes the gate (P ≥ 0.90, R ≥ 0.80) |
|---|---|---|---|---|
| **J0** production prompt | 75/80 (0.86–0.98) | 75/77 (0.91–1.00) | 16/21 | **yes, chosen** (cheapest passing) |
| J1 quote-anchored | 53/54 (0.90–1.00) | 53/77 (0.57–0.79) | 20/21 | no (recall) |
| J2 = J0 ∧ J0 | 75/79 | 75/77 | 17/21 | yes |
| J3 = J1 ∧ J1 | 53/53 | 53/77 | 21/21 | no |
| J4 detector (synthetic) | 22/28 | 22/77 | 15/21 | no |
| J5 detector (+weak, +v1 real) | 24/31 | 24/77 | 14/21 | no |
| J6 cascade (exploratory) | 48/49 | 48/77 | 20/21 | not selectable |

**Other checks:**
- J0 run-to-run agreement: 92/98.
- **Strict contracts (C05)**, applied retrospectively:
  - all 392 outputs pass
  - every J1 quote occurs in its cited paper
  - every rate above is unchanged
- **Link detectors:** cross-validation grouped by concept pair (`results/link_detector_grouped_cv.json`) matches row-wise CV. J4: precision 0.997, recall 0.995. J5: 0.978 and 0.907. So their failure on real papers is a synthetic-to-real gap, not pair leakage.

## 3. Retrieval re-test (selection v2, 77 positives)
`src/discovery/retrieval_v2.py` → `results/retrieval_v2_selection.json`, decision in `data/matcher_selection_decision_v2.json`

| Judge / matcher | Recall, pre-2020 | Recall, post-2019 | Complete (0 pending, 0 errors) |
|---|---|---|---|
| **J0 / A** | 41/42 (0.87–1.00) | 34/35 (0.85–1.00) | yes, but **A fails the binding audit rule** |
| **J0 / D** | **42/42 (0.92–1.00)** | **34/35 (0.85–1.00)** | **yes: chosen** |
| J1 / A (specificity view) | 40/42 | 30/35 | yes |
| J1 / D (specificity view) | 40/42 | 33/35 | yes |

**Notes:**
- **Why A can't be chosen:** the Amendment 4 audit rule is binding for A. On those audit units, judged with the J0 prompt, A missed 2/6 before 2020 (33% > 20%).
- **D** ran C only after **completed** A misses: 8 units (J0's 2 plus J1's 7, 1 shared), with 32 searcher queries.
- **Did A return the source paper?** In 27/42 and 18/35 units. Recall is higher than that because J0 also accepts *other* papers that study the link. That is legitimate, but it depends on J0's precision (§4).

## 4. Deployment-sample validation (C01; descriptive, not a gate)
`src/discovery/deploy_sample.py` → `results/deployment_validation_c01.json`

**Design:**
- **Population:** the matcher-A candidate lists the pilot actually judged (181 of 200 pair-windows had candidates).
- **Sample:** 4 lists per method × window stratum (seed 6161) = 40 lists, 182 papers, each double-adjudicated.
- **Adjudication:** agreement 89.6% (κ 0.85; 98.4% on explicit vs not); 155 agreed papers, 27 contested → `results/deployment_human_sheet.csv`.
- **Prevalence:** 51/155 papers (33%) are agreed explicit. **22/35 lists (63%) contain one**; 5 lists have a contested reference.

| Level | Judge | Precision | Sensitivity | Specificity |
|---|---|---|---|---|
| Pair-window (list) | **J0** (the committed pilot verdicts) | **22/24 (0.73–0.99)** | 22/22 (0.85–1.00) | 11/13 (0.55–0.98) |
| Pair-window | J1 | 20/20 (0.83–1.00) | 20/22 (0.71–0.99) | 13/13 |
| Pair-window | J0 ∧ J1 | 20/20 | 20/22 | 13/13 |
| Paper | J0 | 50/53 (0.84–0.99) | 50/51 | 101/104 |
| Paper | J1 | 34/37 (0.78–0.98) | 34/51 (0.52–0.79) | 101/104 |

**Codex J10 additions:**
- **Stratified list-clustered bootstrap, 95% CIs:** J0 list precision 0.80–1.00, specificity 0.67–1.00. J0 paper precision 0.86–1.00.
- **Population-weighted estimates:** J0 list precision 0.911, J1 1.00.
- **Implied PPV for J0 at other list-level prevalences**, assuming sensitivity and specificity carry over: 0.42 at 10%, 0.68 at 25%, 0.87 at 50%. J1's implied PPV stays at 1.00 because it made no observed false positives; that estimate is limited by n = 13 negatives.
- **List length:** J0's 2 false matches both came on 5-paper lists (2/9 negative lists, against 0.14 expected if errors were independent at p = 0.029 per paper).
- **Errors by method:** too few per stratum to compare (2 J0 false matches in total).

**Reading fixed in advance (Amendment 6.6):** J0's pair-window precision is ≥ 0.90, so **"J0 supported for deployment use"**. This holds at the prevalence observed here, with a CI reaching down to 0.73. It does not hold automatically for less match-rich lists.

## 5. Holdout v2, used once
Run manifest `data/run_manifest_v2.json`: J0 ×1, matcher D, digest `a33553c0…`, committed before any holdout job. Nine overlap units were excluded, leaving 43 positives and 15 hard negatives.

| | Result |
|---|---|
| **J0 classification** (`results/judge_validation_holdout_v2.json`) | precision **43/47 (0.80–0.98)**, recall **43/43 (0.92–1.00)**, specificity 11/15 (0.45–0.92); 0 invalid outputs |
| **D retrieval** (`results/retrieval_v2_holdout.json`) | HOLDOUT_RETRIEVAL_TABLE |

HOLDOUT_VERDICT

## 6. Review fixes (Codex C02–C06), now enforced in code
- **C02:** holdout runs only through the frozen manifest. Alternative judges, a missing matcher and an edited manifest are all refused; tests in `tests/test_contracts.py`.
- **C03:** explicit pending and error states; gates need zero of each. D only runs after completed A misses. The v1 evaluator reproduces its committed numbers.
- **C04:** immutable, content-addressed jobs with a provenance check and stable seeds. The git audit found no output paired with a changed prompt.
- **C05:** JSON booleans only, exact id sets, cited-paper membership and quote spans; grouped detector CV; the holdout overlap exclusion.
- **C06:** the final analysis refuses unjudged ideas unless `--provisional`; a hard evidence cap (166/168 queued prompts unchanged; 2 main-run prompts over the cap by 142 characters, with no output yet); proposal caveats added.

## 7. Costs (free mode)
- **OpenAlex:** $0.073 logged today (A searches on selection and holdout). The searcher subagents' C queries are not in that log: 32 on selection, HOLDOUT_C_QUERIES on holdout, ≤ $0.001 each. The cumulative project total is under $0.55, inside the free tier.
- **LLM:** Claude subagent job files under plan usage, $0. The completed runners reported roughly 120–175k tokens each (about 2.5M in total for this phase). Runners stopped by the 5-hour limit were resumed after the reset.

## 8. What this does and does not establish
- **It establishes:** a measurement pipeline (J0 + D) that passes its preregistered gates on selection and on a held-out set, with enforced provenance, completeness and blinding.
- **It does not establish:**
  - **Independent truth.** References and judges are the same model family, and the adjudication rule is close to J0's own wording, which favours J0. Human labels on the contested sheets are the next step towards independent validation.
  - **Precision at lower prevalence.** J0's specificity on hard negatives (73–76%) is its known weakness.
  - **That a later pair-level match means the generated hypothesis was tested.** That is a separate, secondary, hypothesis-level outcome.

## 9. Recommendation
- **Measurement:** J0 + D is ready to use for the main run under the preregistered rules. Two declared additions:
  - (i) Report every main-run result also under **J0 ∧ J1** (the specificity view), with any disagreement in direction flagged.
  - (ii) Before strong claims, send the contested items (`fresh_human_sheet.csv`, `deployment_human_sheet.csv`) to a human reviewer.
- **The main run stays on hold until the user decides its size:** the full 40 questions (20 per field) or a smaller run. This report clears the measurement blocker; it does not start the run.
