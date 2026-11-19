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
