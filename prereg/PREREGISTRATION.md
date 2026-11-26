# Preregistration: graph paths vs retrieval for research-idea generation

Frozen before any idea was generated or any later-literature search was run. Changes after this point are allowed only as dated amendments at the bottom of this file. Code, prompts and inputs are frozen with this file's commit. Prompt hashes are listed in `prereg/frozen_inputs.json`.

## Research question
Given the same paper collection and a matched evidence budget, does following connections across several papers (graph paths) produce a better shortlist of research ideas than conventional retrieval followed by AI brainstorming?

## Corpus (frozen snapshot, `data/corpus_manifest.json`)
- **Source:** OpenAlex, snapshot dated in the manifest.
- **Works:** 2000–2019 articles in English with abstracts.
- **Fields:** economics is works whose primary topic is in field 20 (Economics, Econometrics and Finance). Transport is works in subfield 3313 (Transportation).
- **Selection:** a fixed-seed random sample of 1,500 works per field per year (seed = 20191231 + year), 60,000 works in total. Citation counts are not used anywhere in selection, because they include citations made after 2019.
- **Graph nodes:** OpenAlex keywords, lower-cased, that appear on at least 5 and at most 5% of corpus papers.
- **Edges:** two keywords on the same paper. Each edge keeps its papers.

## Questions (`data/questions.json`)
- **Source:** for each field, keywords are taken in descending order of corpus frequency. Geographic and sample descriptors (a fixed list) are skipped, as are near-duplicates of an already chosen keyword (substring, or token Jaccard ≥ 0.5).
- **Split:** ranks 1–20 per field form the main set of 40. Rank 21 per field gives the 2 pilot questions.
- **Wording:** every question uses the same template: "What new, testable relationships could help explain outcomes or improve methods in research on {keyword}?"

## Methods (10 ideas per question each)
Every idea names two concepts, A and B, from the node vocabulary.

**Novelty rule.** A pair is eligible only if A and B never appear together on any corpus paper, and neither name contains the other.

**Question relevance.** A concept's relevance is the cosine between the question and the mean LSA vector of the concept's papers.

**Dissimilarity.** One minus the cosine between the two concepts' centroids.

| Code | Method | How the pair is chosen | LLM writes |
|---|---|---|---|
| G | Graph paths | Novel pairs between the 15 most question-relevant concepts and the 1,000 most relevant. Score = relevance(A) × relevance(B) × dissimilarity × path strength (sum over 2- and 3-hop paths of products of normalised edge weights). Diversity cap: a concept is used at most twice. Evidence is the papers on the top two paths, at most 5 per pair. | Hypothesis, sources, test, disconfirming result for each given pair |
| P | Pairwise graph | Same pool and novelty rule as G. Score = relevance(A) × relevance(B) × dissimilarity, with no path information. Evidence is the most question-relevant paper for each concept. | Same as G |
| R | Retrieval + brainstorm | Top 30 abstracts by reciprocal-rank fusion of BM25 and LSA cosine. The concept list is the keywords on those papers plus the 100 most relevant concepts. No novelty rule. | 10 ideas, each choosing A and B from the list |
| RN | Retrieval + novelty filter | Same retrieval, evidence and list as R. The LLM is told the novelty rule and over-generates 30 ideas. Code keeps, in the LLM's order, the first 10 that satisfy the novelty rule. If fewer than 10 pass, one more round of 30 is allowed. | 30 ideas, filtered by code |
| B | Popularity baseline | No LLM. Among the 60 most relevant concepts, novel pairs are ranked by log(frequency) + log growth (2015–19 vs 2010–14) of both concepts. Same diversity cap. | Nothing: template "A is associated with B." |

All LLM methods share the same generation template (`prompts/generation.md`) and output schema. Evidence is capped at 24,000 characters (about 6,000 tokens) per question for every method. G and P differ only by the path-strength factor and the evidence each pair brings.

## Outcome measurement
- **Later-literature search.** For each distinct pair and each window, the fixed search is the OpenAlex filter `title_and_abstract.search:"A" AND "B"`, with parenthetical qualifiers removed and results sorted by relevance. It keeps the top 5 works.
  - Window `pre2020` is publication year ≤ 2019 (all of OpenAlex, not only the corpus).
  - Window `post2019` is 2020–2024.
  - A window with zero results is recorded as "no match found" without judging.
- **Matching rule** (`prompts/judge_match.md`). A paper counts only if its title or abstract shows that it explicitly studies a relationship, effect, association, mechanism or method linking A and B. Merely mentioning both does not count, and synonyms count. Judging is done at the pair level: the judge never sees which method, question or hypothesis produced the pair.
- **Hit.** No match in `pre2020` and a match in `post2019`.

## Primary outcome and test
- **Outcome:** per-question hit rate = hits ÷ 10. The denominator is fixed at 10, so empty slots count as non-hits.
- **Primary test:** G vs R. Wilcoxon signed-rank test across the 40 questions, two-sided, α = 0.05. Zero differences are dropped (the `wilcox` method). Also reported: the mean paired difference with a 95% bootstrap CI (10,000 resamples, seed 11) and the matched-pairs rank-biserial correlation.

## Secondary outcomes
- **Key secondary:** G vs RN, with the same test at α = 0.05. This asks whether graph paths add anything once both methods use the novelty filter.
- **Other comparisons, Holm-corrected as a family:** G vs B, G vs P, R vs B and RN vs B.
- **Descriptive measures per method:**
  - share of ideas already studied by 2019
  - hit rate among ideas with no earlier match
  - mean pre-2020 log frequency of the concepts used (popularity)
  - share of cross-field pairs (home fields differ) and hit rates for cross-field vs within-field pairs
  - distinct concepts per idea
  - results by field
- **Judge agreement.** A second, independent judge re-judges a random 10% of judged pairs. Raw agreement and Cohen's κ are reported. If agreement is below 80%, it is reported next to the headline result.
- **Leakage probe** (`prompts/leakage_probe.md`). For every pair from G, P, R and RN, the model is asked from memory alone whether the A–B relationship was studied before 2020 and in 2020–2024. Answers are compared with the judged labels.
- **Citation accuracy** (`prompts/judge_citation.md`). For 50 randomly chosen ideas per LLM method, the first cited source is checked against its abstract.
- **Cost.** Setup time (graph and indexes), then per-query candidate selection time and token estimates (characters ÷ 4) for prompts and outputs.

## Pilot and the search-miss check
The 2 pilot questions run through every stage before the main run. From the pilot's judged pairs, a blinded sample of up to 30 is drawn: half apparent later matches, half "no earlier match" and no later match.

An independent searcher, given only A, B and the matching rule, searches OpenAlex openly. It uses synonyms and citation trails, up to about 6 queries per pair. The estimated miss rate of the fixed search, per window, is reported next to the headline result. A sheet for human re-checking is in `results/search_audit_sheet.csv`.

Reporting language: an idea is described as having **"no earlier match found"**, never as "novel". A miss is described as "no later match found".

If the pilot shows a high miss rate, the fixed search may be widened by dated amendment **before** the main run.

## Known deviations from the proposal
1. Graph nodes are OpenAlex keywords, not LLM-extracted mechanism, method or finding relations. Each edge still links back to its source papers.
2. LLM steps are run by Claude subagents in one session, not through a metered API. Cost is estimated from tokens.
3. The model was trained on literature published after 2019, so this is a retrospective benchmark. The leakage probe measures how much the model already knows.
4. No human ratings in this run. The blinded review packet is prepared for later use.
5. The search audit is done by an independent subagent, so it is a lower bound on misses. A human repeat is recommended.

## Design decisions made before freezing (no outcome data had been seen)
- The question source was changed from OpenAlex topics to keywords. The transport subfield has only 13 primary topics in the corpus, too few for 20 questions.
- Graph nodes were changed from legacy OpenAlex concepts to keywords, after inspecting pilot candidates. Concept tags were noisy, for example "Focus (optics)" and "Hollywood" on transport papers.
- The novelty rule now also excludes pairs where one name contains the other, such as "urbanism" and "new urbanism".
- A dissimilarity factor was added to G and P scoring, so pairs are related to the question but not near-synonyms. It applies to both, so G and P still differ only by paths.

These choices were made by inspecting the pilot questions' candidate pairs only. No later-literature search or judgment had been run.

## Amendments
(none yet)

### Amendment 1 — 19 November 2026 (before any pilot search, matching or judging)
This amendment follows an external review. No pilot outcome data had been seen when it was written: no later-literature search and no judgment had run for pilot ideas. The only searches run were for the known-match controls below, which are built independently of any idea.

1. **Clean path ablation.** P is now G with path ranking switched off. G and P use the same pool, novelty filter, writer and template, and **the same evidence procedure** (`attach_evidence` in `methods/candidates.py`): the support papers of the pair's two strongest paths when a path exists, otherwise the most question-relevant paper for each concept. Paths are shown to the writer for both methods. The only difference is the path-strength factor in G's score. The share of P pairs with a path is reported; at freezing it was 417 of 420 pairs (pilot and main sets combined). The two original pilot P outputs are kept in `jobs/superseded/` and are not used.
2. **Comparison roles.**
   - **Primary:** G vs R, the practical workflow comparison.
   - **Key secondary, each at α = 0.05:** G vs P is the test of path ranking. G vs RN is the comparison under a shared filter; it is not a test of paths, because candidate selection, evidence and the task all differ.
   - **Other comparisons, Holm-corrected:** G vs B, R vs B and RN vs B.
3. **Outcome name.** The primary outcome is the **retrospective match rate**: the share of 10 slots whose pair has no earlier match found by the fixed search and judge, and has a later match. "Novel" is replaced by **"zero co-occurrence in the sampled corpus"**. The no-context probe is described as a **hindsight diagnostic**. Idea quality (testability, specificity, evidence quality) is scored separately in the blinded review packet. The paper documents are 2000–2019, but their OpenAlex keywords, topics and classifiers come from a current snapshot, so the benchmark is labelled **retrospective** throughout.
4. **Statistics.**
   - **Headline:** the paired percentage-point difference with a 95% bootstrap CI.
   - **Wilcoxon:** uses `zero_method="pratt"`, so tied questions are not discarded, and the number of ties is reported.
   - **RN:** reports both its shortlist fill rate and its hits per 10 requested slots (the fixed denominator).
5. **Validating the literature search.**
   - **Known-match controls** (`src/discovery/controls.py`, `data/controls.json`): 20 pairs, 10 per window, each built from a known source paper.
     - Pre-2020 pairs come from keyword pairs on corpus papers.
     - Post-2019 pairs come from a seeded sample of 2020–2024 papers in the same fields, using pairs that never co-occur in the corpus.
     - Each control produces two items under opaque ids, mixed blind into the pilot judge batches: *confirm* (the source paper alone) and *recall* (the fixed search's top 5).
     - **Recall** is the share of confirmed controls whose recall item is judged a match. All judge items now use opaque ids.
   - **Independent search audit:** earlier and later windows are reported separately. After unblinding, each missed match is attributed to the method or methods that proposed the pair.
   - **Widening rule, fixed before any audit or control result is seen:** if the audit miss rate in either window is above 20%, or control recall in either window is below 80%, the main run uses a widened search. Each concept is expanded with up to 3 synonyms from its strongest co-occurring keywords (OR-ed within the concept), with the top 10 per window. The audit is then re-run on the pilot before the main run.
6. **Budget and power, before the main run.** Measure one batch at the planned size: one runner with 5 generation jobs, plus one judge runner. Project the main-run cost from that, then simulate power at 40 questions using the pilot's match and tie rates and a range around them. The main run starts only with the user's approval after these numbers are reported.
7. **Scope.** The main run is on hold. This session completes the pilot only.

### Amendment 2 — 19 November 2026 (blinding fix; no pilot results had been analysed)
In the first pilot judging round, each judge job file also carried its metadata. That metadata was the id map from opaque item ids to internal keys, so judges could see which items were known-match controls (internal keys `CTRL::…`). One judge reported this. The internal keys of real items are only the two concept names, so the method that produced a pair was not revealed.

**Fix.** All job metadata now goes to a separate sidecar (`jobs/<kind>_meta/`) that runners are never given. Job files contain only the prompt.

**Re-run.** The pilot judging was re-run from scratch by new judge subagents. The first round's outputs are kept in `jobs/superseded/judge_round0_ids_visible/`, are not used for any reported outcome, and are compared with the blind round only as a check of judge stability.

**Generation jobs.** Their files had also carried metadata (the method label and the candidate list) and were migrated the same way. This does not affect the generation outputs: each writer sees only its own method's task, which already identifies the task type.

### Amendment 3 — 19 November 2026 (pre-set widening rule triggered)
The pilot validation triggered the widening rule fixed in Amendment 1:
- **Control recall:** 100% before 2020 (7 of 7 confirmed) but **67% after 2019** (4 of 6), below the 80% threshold.
- **Independent audit (30 pairs):** among pairs the pipeline marked as no match, the auditor found an explicit study anyway in **56%** of pre-2020 cases (9 of 16) and **47%** of post-2019 cases (7 of 15), above the 20% threshold. The auditor confirmed every match the pipeline found (0 of 14 pre-2020 and 0 of 15 post-2019 contradicted).

**The rule as fixed in Amendment 1 is applied unchanged.** Each concept is OR-ed with up to 3 of its strongest co-occurring keywords (by normalised edge weight), and the top 10 per window are judged (`search_pair_widened` in `study.py`).

**Caveat recorded now.** These expansions are related keywords, not strict synonyms. They may raise recall at the cost of precision. The widened labels are checked against the **same** independent audit findings, which were collected without access to any pipeline output, and widened control recall is computed from new blind recall items.

**Main run.** The main run will use the widened search only if it reaches control recall ≥ 80% and an audit miss rate ≤ 20% on the pilot. Otherwise the search problem is reported as unresolved and the main run stays on hold.

### Amendment 4 — 21 November 2026 (matcher validation; written before any replacement matcher is run)
**Why.** Under Amendment 3, both the fixed and the widened search failed validation. This amendment fixes, in advance, how replacement matchers are validated and chosen. The 40-question main run and all Study 2 generation stay on hold.

**1. Two tasks, measured separately**
- **Retrieval.** Unit: a pair × window with a known positive. The question is whether the matcher's candidate list contains a paper that the production judge (`prompts/judge_match.md`) marks as an explicit study, and whether it contains the known source paper (stricter, reported too).
- **Classification.** Unit: a paper × pair. The question is whether the production judge, given that single paper, labels the link correctly against the reference label.

**2. Reference labels**
- **Procedure.** References come from a separate adjudication prompt (`prompts/adjudicate.md`): one of explicit / mention_only / not_both / unclear, with a supporting quote. It is run blind by subagents that never see matcher output or production-judge verdicts.
- **Not fully independent.** These labels come from the same model family as the production judge. A human adjudication sheet (`results/holdout_human_sheet.csv`) is exported for the holdout; until a human completes it, the reference is described as **not fully independent**.
- **Positive controls.** Pair × window units whose source paper is adjudicated "explicit". These are the 20 existing controls plus about 40 new ones (`controls.py`, seed 4343, same construction).
- **Paper-level hard negatives.** Paper × pair units adjudicated "mention_only". They are drawn, with seed 4344, from papers the fixed search returned for pilot pairs (all such papers contain both phrases) in windows the production judge called no match. Target: about 40.
- **"No match found by reference."** For a pair × window, this label is **never treated as a true negative** and is not used for precision.
- **Audit pairs.** The 30 existing audit pairs, with the earlier independent agentic audit as reference. These are **secondary**. They are circular for matchers C and D, because the audit was itself an agentic search.

**3. Candidate matchers.** All use the same production judge on their candidates.
- **A, word-level:** `title_and_abstract.search` with the words of A AND the words of B, unquoted, parentheticals removed, top 5.
- **B, near-synonym:** each concept OR-ed with up to 2 vocabulary keywords that have content-centroid cosine ≥ 0.85 and share at least one content word, exact phrases, top 5.
- **C, agentic:** a subagent with at most 6 OpenAlex queries per item (`prompts/match_agentic.md`) returns up to 3 candidate work ids per window, without labelling them.
- **D, hybrid:** A, then C for the windows where A has no judged match.
- **Exploratory only:** OpenAlex semantic search, top 5, reported but not eligible for selection.

**4. Split and sealing**
- All units (positive controls, hard negatives and audit pairs) are split 60/40 into **selection** and **holdout** with seed 4345, stratified by unit type and window.
- Holdout unit ids are written to `data/holdout_sealed/` and no matcher is run on them until the selection decision is committed.

**5. Pass gates (selection set, every window)**
- Retrieval recall on positive controls ≥ 80%.
- Production-judge classification precision ≥ 90% on hard negatives plus positive sources.
- Audit miss rate ≤ 20% (binding for A and B only).

**6. Selection rule.** Among the matchers that pass, choose the one with the lowest cost per pair (subagent tokens, then OpenAlex dollars). **Only that matcher is run on the holdout, once.** If it fails, the failure is reported and **no other matcher is tried on the same holdout**. If no matcher passes on the selection set, the holdout is still not opened and the recommendation is to continue validation.

**7. Reporting**
- Every rate comes with an exact Clopper–Pearson 95% CI. With roughly 8–10 positives per window in the holdout, the holdout is **preliminary validation**: a check against major failures, not a certification.
- Costs are reported as subagent tokens per matcher and OpenAlex dollars by operation type (from `data/openalex_costs.jsonl`; measured prices: search $0.001, list $0.0001, singleton free, $1/day free allowance).

**8. Secondary and sensitivity analyses**
- **Hypothesis-level matching** (`prompts/judge_hypothesis.md`) is applied to pilot ideas with a pair-level match.
- **Measurement sensitivity** (`src/discovery/sensitivity.py`) recomputes G − R, G − P and G − RN on the 100 pilot ideas under each measurement method. Fixed and widened labels are kept unchanged.

#### Amendment 4a — 21 November 2026 (after adjudication, before any matcher run)
Adjudication produced 30 "explicit", 35 "mention_only", 25 "not_both" and 2 "unclear" labels across 92 units.

**Hard negatives broadened.** Hard negatives from fixed-search non-match windows numbered only 14. The paper-level hard-negative set therefore also includes control source papers adjudicated "mention_only". Both have the same meaning: a paper that mentions both concepts but does not study the link. Each unit records its origin.

**Positive controls.** These stay at 28 sources adjudicated "explicit". Two fixed-search "no match" papers were adjudicated "explicit". They are disagreements between the production judge and the reference and are reported, not used as negatives.

**Holdout size.** About 5 positive controls per window. That confirms the holdout is preliminary only.

No matcher had been run when this was decided.

### Amendment 5 — 22 November 2026 (judge repair and re-validation; written before any new judge or matcher test)
**Why.** Under Amendment 4 no matcher passed, because the shared production judge had 84% precision on hard negatives (16/19). By the user's decision, this round uses **model-generated reference labels**. Every result is labelled *model-referenced, not human-validated*.

**1. A fresh labelled set** (`src/discovery/units_v2.py`), with no pair or paper overlapping Amendment 4 units:
- **Positive candidates:** about 120 controls, 60 per window, built as in `controls.py` with seed 5151.
- **Hard-negative candidates:** about 120 papers containing the words of both concepts, taken from search A results (top 5) on new keyword pairs drawn from corpus papers, with seed 5152.

**2. Double adjudication**
- **Procedure:** two independent runs of `prompts/adjudicate.md` (orderings `adj_v2a` and `adj_v2b`, in separate subagents that never see the other ordering).
- **Agreed labels:** an item counts as a **positive** only if both runs say "explicit", and as a **hard negative** only if both say "mention_only".
- **Disagreements:** these items are the **contested** set. It is reported (agreement rate, Cohen's κ) and exported to `results/fresh_human_sheet.csv`.
- **Target:** at least 30 agreed positives and 30 agreed hard negatives per window. A shortfall is reported, not relaxed.

**3. Split.** Seeded (5153) 60/40 split into selection and holdout (`data/holdout_sealed_v2/`), stratified by window and type.

**4. Judge candidates**
- **J0:** `prompts/judge_match.md`, the baseline.
- **J1, quote-anchored:** `prompts/judge_match_quote.md`.
- **J2:** J0 run twice by independent runners; a match only if both say match.
- **J3:** J1 run twice the same way.

**Judge gates (selection v2):** precision ≥ 90% and recall ≥ 80%, with Clopper–Pearson lower bounds reported. **Choice:** the cheapest passing judge (J0 < J1 < J2 < J3), committed before any retrieval re-test.

**5. Retrieval re-test with the chosen judge** (selection v2 positives)
- **A** (word-level): retrieval recall ≥ 80% per window, plus the Amendment 4 audit rule (≤ 20% miss), which stays binding for A.
- **D** (A, then agentic C on A-misses only): retrieval recall ≥ 80% per window.
- **Choice:** the cheapest passing, committed.

**6. Holdout v2.** Run once, only for the chosen judge and matcher. If it fails, report it; nothing else is tried on that holdout. If no judge or no matcher passes, holdout v2 stays sealed.

**7. Exploratory.** The 100 pilot ideas are re-scored with the chosen judge and matcher (or with J1 and A if none passes, labelled exploratory) and added to the measurement-sensitivity analysis.

The 40-question main run and Study 2 generation remain out of scope.

#### Amendment 5b — 24 November 2026 (zero-cost link detector; trained and frozen before any v2 label was read)
At the user's request, a **scenario layer** trains cheap link detectors. In free mode it uses no LLM and no paid service. OpenAlex has a hard stop at $0.90 a day (`openalex.check_budget`).

**Training data** (`src/discovery/scenarios.py`, seed 5154). It excludes every pair and paper in v1 units and v2 candidates.
- **(a) Template scenarios:** 3,000 synthetic abstracts, 600 pairs × 5 classes: explicit effect, explicit method, mention-only in the same sentence, mention-only in separate sentences, and not both. Hand-written templates are combined with filler sentences from real corpus abstracts.
- **(b) Weak labels:** 3,000 real corpus abstracts. Explicit means one sentence contains both concepts plus a relation cue; mention_only means both appear but never in the same sentence.

**Detector** (`src/discovery/link_detector.py`)
- Mentions of A and B are masked as `[A]` and `[B]`.
- Features are TF-IDF 1–3-grams plus structural features: same sentence, distance, relation cue, list pattern and presence of both.
- The model is logistic regression.
- The threshold is chosen by 5-fold cross-validation on the training data only, maximising F1 subject to precision ≥ 0.90.

**Frozen detectors** (`results/link_detector_training.json`)

| Detector | Trained on | CV precision | CV recall | Threshold |
|---|---|---|---|---|
| **J4** | template data only | 0.997 | 0.993 | 0.08 |
| **J5** | templates + weak labels + 63 v1 real adjudicated items | 0.979 | 0.909 | 0.25 |

**Testing on v2.** Both are tested on the v2 selection set with the same gates as J0–J3. The cost order is **J4 < J5 < J0 < J1 < J2 < J3**.

**J6 cascade (exploratory, not selectable):** J5 with a low threshold of 0.05, then J1.

The synthetic-to-real gap (CV score versus v2 score) will be reported.

### Amendment 6 — 25 November 2026 (response to the Codex review; written before the v2 retrieval re-test, the deployment sample and any holdout-v2 use)
This amendment responds to `docs/CODEX_REVIEW_2026-11-24.md` (findings C01–C06). The discussion is in `AGENT_DISCUSSION.md`. It changes no decision already taken. Under Amendment 5, J0 remains the chosen judge.

**1. Holdout-v2 overlap exclusion (C05).**
- Selection v2 and holdout v2 share **9 concept pairs** (0 papers), because the split was item-based. This was counted from pair identities only; no holdout label or judgment was read.
- Every holdout-v2 unit whose concept pair also occurs in selection v2 is **excluded from holdout analysis**. The split file is not modified. The excluded unit ids are logged in every holdout result (`contracts.exclude_overlap`).

**2. Frozen run manifest (C02).**
- Holdout v2 is used only through `data/run_manifest_v2.json` (`src/discovery/manifest.py`). The manifest records the judge, its repetitions, the matcher, the judge prompt's SHA-256, the reference files' hashes, the selection commit and a self-digest.
- Holdout mode refuses a missing, edited or incomplete manifest, and refuses any judge or matcher other than the frozen ones. It never re-selects.
- The manifest is written once, after the matcher decision and before any holdout job.

**3. Completeness and error states (C03).**
- Retrieval units carry explicit states: match, no_match, no_candidates, pending or error.
- Recall is computed over completed units, but **a gate passes only with zero pending and zero error units**.
- **D runs C only after a completed A miss**, never for a pending or failed A unit.
- **Declared rule for an undefined audit miss rate** (the matcher left no audit pair unmatched): it passes only if every audit unit is complete.
- The v1 evaluator now enforces the same rules. Re-running it reproduces the committed v1 numbers exactly (0 pending, 0 errors; no matcher passes).

**4. Strict output contracts (C05).**
- Judge outputs must use JSON booleans and cover exactly the job's item ids, without duplicates.
- A cited paper must be one of the item's candidates.
- For the quote-anchored judge (J1), the quote must occur in the cited paper's title or abstract after normalisation; otherwise the item counts as no match.
- **Applied retrospectively to selection v2:** all 392 classification outputs pass, every J1 quote is found in its paper, and every selection-v2 judge rate is unchanged.

**5. Retrieval re-test, read against Amendment 5's rules.**
- The Amendment 4 audit rule is binding for A, and the Amendment 4 audit units were judged with the J0 prompt (`judge_match.md`). On them, A's miss rate is **2/6 = 33% before 2020** and 1/6 = 17% after 2019. **A therefore fails the binding audit rule and cannot be chosen**, whatever its v2 recall.
- A is still run on the 77 selection-v2 positives (`src/discovery/retrieval_v2.py`), because it is D's first stage.
- C searcher jobs then run for completed A misses, and **D is evaluated against Amendment 5's gate**: recall ≥ 80% in each window, complete, with no errors. If D passes, D is the chosen matcher. If not, holdout v2 stays sealed.
- **Specificity view** (user decision, "do both", 24 Nov): every retrieval result is also reported with J1. That includes C searches for J1's completed A misses. These are reported only and never used for selection.

**6. Deployment-sample validation of the judges (C01; descriptive, not a gate).**
- **Population:** the actual matcher-A candidate lists of the 100 pilot ideas (`data/pair_candidates_A.json`). Of the 200 pair-windows, 181 have at least one candidate.
- **Sample:** seed 6161, stratified by window × generating method (G, P, R, RN, B), with 4 lists per stratum (40 lists). Every paper in a sampled list is included, with the same title and truncated abstract that the judges saw.
- **Reference:** two independent adjudication orderings with `prompts/adjudicate.md`. Only agreed labels count (explicit vs mention_only/not_both). Contested items are reported and appended to the human sheet.
- **Judgments:**
  - J0 and J1 classify every sampled paper individually, as new jobs.
  - Pair-window verdicts: J0 uses the committed pilot rescoring outputs (the same prompt), and J1 gets new list jobs.
- **Reported:**
  - paper-level precision, sensitivity and specificity
  - pair-window ("any paper matches") precision, sensitivity and specificity
  - the observed prevalence and contested counts
  - Clopper–Pearson intervals
- **Interpretation fixed now, before any of these data are seen:**
  - If J0's pair-window precision is at least 0.90, J0 is supported for deployment use.
  - If it is below 0.80, J0 alone is **not** adequate for main-run claims, and the recommendation is a stricter rule (J1, or J0 ∧ J1). That rule would need its own amendment before any main run.
  - Between 0.80 and 0.90 is reported as borderline.
- This does not change the selection decision or the manifest. Same-family references measure repeatability, not independent truth.

**7. Job identity and completeness (C04, C06).**
- LLM jobs are immutable and content-addressed, with a provenance check and stable seeds.
- The selection-v2 judge job files are frozen with their outputs. Regenerating them raises an error by design.
- The final analysis refuses unjudged ideas unless `--provisional` is passed, which marks the output as provisional.
- The 24,000-character evidence cap is now a hard limit. Measured: 2 of 168 queued generation prompts exceeded it by 142 characters. Both are main-run jobs with no output, so the pilot is unaffected.

### Amendment 7 — 25 November 2026 (main-run sensitivity rules; written after holdout v2 and before any main-run scoring)
Responds to Codex J16 and to the user's decision to report a stricter view ("do both", 24 Nov). No main-run idea has been generated or scored under the current measurement.

**1. Primary measurement (unchanged).** J0 + D as frozen in `data/run_manifest_v2.json`. A list matches if J0 says match.

**2. Declared sensitivity rules.** These are reported for every main-run comparison and never replace the primary result after the fact.
- **S1, list-level intersection:** a pair-window counts as matched only if **both** J0 and J1 say match on the same candidate list.
- **S2, same-paper agreement:** S1, **and** J1's quote is verified in its cited paper (`contracts.quote_in_text`), **and** J1's cited paper is the same as J0's cited paper.
- For each comparison, report the primary, S1 and S2 estimates with paired intervals, and flag any change in direction or significance. A conclusion that holds under the primary rule but reverses under S1 or S2 is reported as **inconclusive**.

**3. Judge-policy comparison (P0 J0, P1 J1, P2 J0 twice, P4 J0 then J1 on positives).**
- This is development work only. The C01 sample (`data/deploy_sample_c01.json`) is development data for it.
- Any policy improvement must be confirmed on a **fresh seeded sample of real candidate lists**, disjoint in pairs from C01, with C-fallback lists included and sampling fractions recorded. Only after that may a policy replace the primary.
- The thresholds, evidence rules and abstention rules for that confirmation are fixed in a further amendment, before the fresh sample is judged.

**4. Changes the recommendation if found.** Either of these makes the stricter rule primary, through a new amendment, before any main-run conclusion:
- human labels on ordinary J0-positive lists showing precision below 0.80
- a main comparison that reverses direction under S1

### Amendment 8 — 26 November 2026 (main-run outcome measurement; written during idea generation and before any main-run search or judging)
The owner chose the full 40-question main run, in free mode. This amendment fixes how its outcome is measured. No main-run idea has been searched or judged.

**1. Primary measurement (unchanged from the frozen manifest).** J0 + D. Matcher A runs for **both windows of every distinct pair**, and J0 judges each A list. C (agentic search, at most 6 queries per item) runs only after a **completed** A miss (no_match or no_candidates), and J0 judges C's list. Hit = no match before 2020 and a match in 2020–2024. Empty or unmappable idea slots count as non-hits (fixed denominator of 10). Code: `src/discovery/main_run.py`.

**2. Decisive-only C and J1 (cost control that leaves the outcome unchanged).** C and J1 run only where they can still change a hit under at least one rule:
- If a pre-2020 A match settles the primary hit, no C stage runs.
- When both windows are A misses, the post-2019 C stage runs first; the pre-2020 C stage runs only if post-2019 matched.
- J1 confirmations come before any C stage.
- `tests/test_main_run.py` checks, over 3,000 random scenarios, that this gives **exactly the same hits** as running C and J1 everywhere, under all three rules.
- **Descriptive consequence:** "already studied by 2019" uses the D result where it was determined and the A-stage result otherwise. Both are reported, labelled `pre2020_match` and `pre2020_match_A_stage`.

**3. Sensitivity rules (Amendment 7, made concrete).**
- **S1:** the primary match is confirmed by J1 on the same list (the list where J0 matched).
- **S2:** S1, plus J1's quote is verified in its cited paper and that paper is the one J0 cited.
- A J1 rejection of a J0 match makes the window "no match" under S1 and S2. C is not re-run, because C runs only after primary misses.

**4. Errors and pacing.**
- A failed search or an invalid judge output is an error state, never a miss. Error units are retried. Hits that depend on them stay undetermined, and the final analysis refuses undetermined hits unless `--provisional` (C06).
- C searchers are told to report request failures as `"error"` for an item, never as an empty candidate list.
- **Budget:** OpenAlex stays under $0.90 a day; the A searches stop at the cap and resume the next day. C rounds are scheduled with their estimated query cost counted in that budget.

**5. Secondary outcomes.** As preregistered:
- a second independent J0 run on a seeded 10% of judged A lists (agreement and κ)
- the leakage probe for G/P/R/RN pairs
- citation checks (50 per LLM method)
- hypothesis-level judging of hits (secondary)

**Amendment 8, correction (26 Nov 2026, during generation, before any main-run search was judged).**
- **The bug:** `study.ingest` attached G/P idea text to the selected pairs by position. Writers frequently return ideas in preference order (the generation prompt asks for "the order given" and also "best first"), so the text was mis-attached in 33 of 40 G/P outputs checked so far.
- **Not affected:** the pair-level primary outcome. The 10 selected pairs per question, their order and their path flags come from the candidates, not the writer.
- **Affected:** the pilot's hypothesis-level secondary result (17 of 35 items).
- **The fix:** ingest now matches by pair name (`study.match_pair_ideas`, tested), keeping the selected-pair order and recording `matched_by` and `writer_rank`. The pilot hypothesis-level items are re-judged with corrected text (`jobs/hyp_c`), and the result replaces the earlier one with a dated note.
