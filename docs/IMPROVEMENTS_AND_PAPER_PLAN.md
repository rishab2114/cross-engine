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

**Working title:** *Do citation-graph paths improve LLM research-idea generation? A preregistered retrospective benchmark across economics and transport.*

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
