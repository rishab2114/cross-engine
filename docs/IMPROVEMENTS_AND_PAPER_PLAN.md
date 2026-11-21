# Improvements log and path to a paper

A running log, updated on each review pass. Each entry says what was checked, what was found, and what it implies. Findings are kept separate from opinions.

---

## Pass 1 (19 Nov 2026, during pilot judging)

### Cross-check of what exists
| Item | Status | Checked how |
|---|---|---|
| Corpus: 60,000 works, 2000–2019, 1,500 per field per year | OK | Manifest counts; test confirms years ≤ 2019 |
| No citation-based selection | OK | Test inspects the sampling code |
| Preregistration plus Amendment 1, committed before any pilot matching | OK | Git order: `028f863` (freeze) → `abe6ffd` (Amendment 1) → `d2132fd` (search candidates) |
| G/P share one evidence procedure | OK | 417 of 420 P pairs have a path, so the leftover difference is small |
| Pilot shortlists | 10 per method per question, 0 unmapped concepts | Ingest check |
| R obeys no novelty rule (by design) | 8 of 20 R ideas reuse pairs that already co-occur in the corpus | Ingest check |

### Problems found so far
1. **The fixed search matches keyword strings literally.** For 14 of the 20 known-match controls, the source paper the pair was taken from is **not** in the search's top 5. In 1 post-2019 control the search returns nothing at all. OpenAlex keywords are machine-extracted, so the exact phrase often doesn't appear in the title or abstract. This is likely to undercount both earlier and later matches. It matters most for unusual (cross-field) pairs, which is exactly what G is designed to find. *Control recall from the judges will show how bad this is. The pre-set widening rule applies if recall is below 80%.*
2. **P can pick pairs from word collisions.** Pilot example: "stock returns" was paired with "rolling stock modernization", because of the shared word "stock" in LSA space. With path ranking switched off, word overlap can pass as relevance. That is a real finding for the ablation, but it should be reported, not hidden.
3. **G pairs are often neighbours within one subfield.** For example, "capm validity" with "expected stock returns". Zero co-occurrence in a 60k sample is a weak signal of novelty. The pre-2020 window check exists for this reason; expect many G ideas to be "already studied by 2019".
4. **Cost.** Each runner subagent uses about 125–150k tokens for 2 generation jobs. Usage limits interrupted the work once.
5. **Power, simulated.** With 40 questions, the minimum detectable difference at 80% power is about 6 percentage points if the base match rate is 2%, 8 points at 5%, 10 points at 10% and 15 points at 20%. A third to two thirds of questions are expected to be ties.

### Possible improvements (not yet adopted)
- **Search:** use synonym expansion from co-occurring keywords (the pre-set rule), plus a citation hop: works citing the top candidates.
- **Node quality:** merge near-duplicate keywords ("stock return predictability" and "return predictability") into one node before building the graph.
- **Typed relations:** extract mechanism, method and finding roles with an LLM for the papers on shortlisted paths only. That costs about 50 papers per question, not 60k.
- **A truly time-respecting graph:** build nodes from 2019-era author keywords or a frozen vocabulary instead of current OpenAlex keywords.
- **Leakage:** use an open model with a pre-2020 training cutoff as a second writer, for a true forecast test.

---

## Path to a paper (draft)

**Working title:** *Do keyword co-occurrence graph paths improve LLM research-idea generation? A preregistered retrospective benchmark across economics and transport.* (Superseded in Pass 3. The graph has no citation edges; an earlier draft of this title wrongly called it a "citation graph".)

**What the paper could claim, depending on the outcome:**
- **If G beats R and P:** paths add value beyond retrieval, and the ranking (not just the filter) helps.
- **If there is no difference:** a well-powered, preregistered null with validated search is still publishable. Most idea-generation papers report wins without matched budgets or search validation.
- **Either way, a methods contribution:** a reusable benchmark protocol (time split, known-match controls, independent search audit, hindsight probe) that addresses known weaknesses of retrospective evaluation.

**Needed before a submission-quality result:**
1. A pilot that confirms search validity (control recall ≥ 80%, audit miss rate ≤ 20%), or a widened search that reaches it.
2. The 40-question main run, which is several usage windows or an API key.
3. Human ratings on the blinded review packet (24 proposals, 2 raters), for idea quality beyond the match rate.
4. A human repeat of the search audit.
5. Related work: SciMuse, Impact4Cast, Idea-Catalyst, plus literature-based discovery (Swanson ABC model) and recent LLM ideation benchmarks.

**Possible venues:** a scientometrics journal (*Scientometrics*, *Quantitative Science Studies*), or an NLP or AI-for-science workshop for the benchmark protocol.

**Study 2 (use cases), see `STUDY2_USE_CASES.md`:** a separate paper on whether combined ideas turned into proposed, piloted or adopted interventions.

---

## Pass 2 (19 Nov 2026, pilot complete)

### Cross-check
| Check | Result |
|---|---|
| Every pilot shortlist full (10 per method per question) | OK (100 of 100) |
| G, RN and B pairs have zero co-occurrence in the sampled corpus | OK (60 of 60) |
| G and P share the evidence procedure | OK; 18 of 20 P pairs had a path |
| Judges blind | Fixed after a leak (Amendment 2); re-run rounds agree 98% |
| Runner rule compliance | One widened judge used Grep on its own oversized job file; recorded in the pilot results |
| Search validity | **Fails.** Fixed search: control recall 67% after 2019, audit miss rate 47–56%. Widened search: recall 33% after 2019, miss rate up to 56% |
| The analysis rebuilds the reported numbers | Yes, `analysis.py --set pilot [--suffix _widened]` |

### New findings
1. **The outcome measure is the bottleneck, not the generator.** Changing only the search triples or quadruples the match rates (G 5% → 15%, R 5% → 20%).
2. **Measurement error differs by method.** R loses the most to exact-phrase search, so a method ranking under the fixed search could be wrong in direction, not just size.
3. **Related-keyword expansion hurts recall.** Expansion terms crowd the top 10. The preregistered rule failed, which is itself a useful negative result.
4. **Zero co-occurrence in a 60k sample is a weak novelty filter for G.** Half of G's pairs were already studied by 2019. P and RN pairs are rarely matched in either window.
5. **Job sizing matters.** Widened judge jobs of 50–70k tokens can't be paired in one subagent. Keep jobs under about 30k tokens.

### Improvements, prioritised
1. **A validated matcher.** Test the candidate matchers (word-level search, near-synonym expansion, agentic open search, or a mix) on the 30 audit pairs and 13 confirmed controls, and adopt one by amendment only if it passes (recall ≥ 80%, miss ≤ 20%). *This blocks everything else.*
2. **Grow the validation set.** 30 audit pairs and 13 controls give wide intervals; aim for about 100 audit pairs and 40 confirmed controls, stratified by method.
3. **A human audit** of the same sheet, to check the subagent auditor's leniency.
4. **A stronger novelty filter for G.** Require that no pre-2020 OpenAlex paper (not just the corpus) matches the pair under the validated matcher before it enters the shortlist. That is a pre-screen, applied equally to G, P, RN and B.
5. **Node merging** of near-duplicate keywords, to cut trivial within-subfield pairs.
6. **Cheaper LLM steps:** an API key with prompt caching would make the 11–12M-token main run routine instead of spread over many usage windows.

### Path to a paper (revised)
The pilot strengthens the **methods-paper** angle. A defensible paper exists even before the main run:

> **"Retrospective evaluation of AI-generated research ideas depends on the literature matcher: evidence from a preregistered pilot."** Contributions: (i) a preregistered benchmark protocol with known-match controls and an independent search audit; (ii) evidence that a standard phrase search misses about half of real matches, and that the miss rate differs by idea-generation method; (iii) evidence that a natural "widening" fix makes it worse; (iv) a validated matcher (once found) and the main comparison.

**Sequence:** fix the matcher, then expand validation, then the human audit, then the main run (40 questions), then human quality ratings, then the write-up. The use-case study (Study 2) follows as a second paper and reuses the matcher-validation approach for adoption evidence.


---

## Pass 3 (21 Nov 2026, after the external review)

### Corrections
- The graph is a **keyword co-occurrence graph**. It has no citation edges.
- **OpenAlex provenance:** the topic classifier was replaced on 6 Oct 2026, with further taxonomy updates in November. Our snapshot (19 Nov 2026) uses the new assignments. Topics are used only for field selection; graph nodes are OpenAlex keywords. Neither reconstructs 2019-era indexing.
- **OpenAlex budget, as measured** (`results/openalex_quota.json`): $1/day free allowance. A search (including `title_and_abstract.search` filters) costs $0.001, a list/filter request $0.0001, a single-work lookup is free, and semantic search costs $0.001 (1 per second). Uncached request costs are now logged in `data/openalex_costs.jsonl`.

### Related work (verified)
| Work | What it shows | Relevance |
|---|---|---|
| Gu & Krenn, SciMuse, *PNAS* 2026 | 58M-paper knowledge graph plus an LLM; >100 group leaders rated 4,400 ideas. **Graph-selected concept pairs did not beat a titles-only GPT baseline**; 24.9% of ideas rated 4–5 | Graph ideation alone is not a convincing contribution |
| Gu & Krenn, Impact4Cast, *MLST* 2025 | Link forecasting on an evolving concept graph | Time-split evaluation precedent |
| Radensky et al., Scideator, ACM CAIS 2026 | Facet (purpose, mechanism, evaluation) recombination plus novelty checking; beats search+LLM in a 19-researcher study | Mechanism/method recombination is established |
| Wang et al., SciMON, ACL 2024 | Iterative novelty optimisation against retrieved literature | Literature-based novelty checking is established |
| Ghafarollahi & Buehler, SciAgents, *Adv. Mater.* 2024 | Multi-agent ontological graph reasoning | Agentic cross-domain graph discovery |
| Liu et al., ResearchBench, Findings of ACL 2026 | Stage-wise evaluation (inspiration retrieval, composition, ranking) across 12 disciplines | Evaluate the stage where value is added |
| Li, Tu & Han, Graph2Idea, arXiv, June 2026 | Target-centred knowledge graph for retrieval-augmented idea generation | Typed graph context is not novel |
| Borrego et al., ResearchLink, *Knowledge-Based Systems* 2025 | Path, embedding and literature features for hypothesis generation; P@20 = 78.7% on 600 annotated hypotheses | Same |
| Chung, Seol & Yoon, *IEEE TEM* 2026 | SAO knowledge graph over patents for recombination opportunities | Recombination for practical innovation (Study 2) |

### Reframed lead contribution
**"How sensitive are retrospective AI-discovery benchmarks to the literature matcher?"** The pilot already shows that match rates change three- to fourfold with the matcher alone, and that misses differ by method. The graph-vs-retrieval comparison becomes the application of a validated benchmark, not the headline claim.
