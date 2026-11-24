# Review of `TRAINING_EXTENSION_PLAN.md` (draft v2)

*Reviewed 24 Nov 2026 against Cross Engine at `47aec02`. This is a critical review of the plan; it is not an endorsement.*

## Verdict
This is a **well-controlled design for a third study**, but its central hypothesis has no argued mechanism, and its primary comparison may not be testable at the proposed scale. Keep it as a design document. Start it only after two cheap preconditions show that researcher availability carries signal in our domain:
1. **Alien-lite:** temporal recovery in economics and transport, with OpenAlex keywords as atoms and a CPU author-availability score.
2. **Upstream smoke test:** CPU scoring with the released Alien artifacts.

## What is strong
- **Leakage control.** Splitting by canonical composition family *before* generating examples, a frozen test set independent of every selector, checks for duplicate templates and graph isomorphisms, and confidence intervals clustered by family and seed. This is the right design for compositional generalisation.
- **Ablations.** C (coherence, rarity, diversity) against D (coherence plus author unavailability) is the correct primary contrast. The C/D/E/F 2×2 separates selection from ordering. A (uniform valid sampling) is a proper floor.
- **Honesty.** It cites GRAPH's null result (forecast-selected combinations did not beat random ones) and our weak synthetic-to-real detector result, and it separates rarity, availability and learner difficulty.
- **Provenance.** It pins the upstream commit, keeps the MIT licence, records local changes and checks dataset terms.

## Main risks

| # | Risk | Why it matters | Suggested change |
|---|---|---|---|
| 1 | **No mechanism linking community unavailability to learner benefit** | Availability measures what *researchers* are unlikely to propose. A learner gains from coverage, difficulty and diversity, not from being outside a community's reach. Rarity and difficulty are the more plausible drivers, so expect D ≈ C. | State a mechanism, or frame D as an exploratory test with a pre-declared expectation of no difference. Keep C as the practical baseline. |
| 2 | **The availability model can't be estimated from 100–300 papers** | Upstream trains on about 45,000 author repertoires. A few hundred papers give a few hundred authors with near-disjoint repertoires, so the scores will be close to noise. The plan says so itself. | Gate the study on Alien-lite. If the domain availability score doesn't beat a rarity baseline on temporal recovery, drop arm D. |
| 3 | **Mapping atoms to simulator operations is effectively hand-built** | With 10–30 executable mechanisms, the "atom catalogue" is a small hand-designed ontology. Coherence then reduces to co-occurrence counts, and selection differences shrink. | Report coherence-model quality on held-out papers, and compare it against a co-occurrence baseline before training. |
| 4 | **Cost conflicts with free mode** | Atomization and reconstruction need paid LLM providers, and upstream availability training used 4 A100 GPUs for about 14 hours. | Any paid step needs explicit approval. A free path exists: released artifacts with CPU inference, keyword atoms, and template-compiled tasks. |
| 5 | **It doesn't address Cross Engine's open blocker** | Cross Engine's outcome measure (literature matcher plus judge) is still unvalidated. | Treat this as a separate study with its own preregistration, after judge repair. |
| 6 | **Generator-bound results** | A self-built simulator defines both the tasks and the correct answers, so gains may not transfer. | Keep the planned external replication. Claims stop at the simulator until it is done. |

## Citation check (OpenAlex, 24 Nov)
- **Curriculum learning** (Bengio et al., ICML 2009): verified.
- **Alien Space of Science** (Artiles et al., arXiv 2603.01092): verified. It was read: main text and Appendix A.
- **"Synthetic Curriculum Reinforces Compositional Text-to-Image Generation"** (CompGen): exists as arXiv 2511.18378 (2025). Its CVPR 2026 version is **not confirmed** in OpenAlex.
- **The ICLR 2026 "synthetic reasoning training" link:** not checked; the title isn't given in the plan.
- **GRAPH results** (`rishab2114/GRAPH`): outside this session's repository access, so **not verified here**.

## Recommended order
1. Finish Cross Engine judge repair (Amendment 5).
2. **Alien-lite** (free): does an author-availability score beat a rarity baseline at recovering 2020–2024 keyword combinations from frozen pre-2020 data, in economics and transport?
3. **Upstream smoke test** (free): released artifacts, a small CPU scoring run, checksums.
4. Only if 2 shows availability carries signal beyond rarity: preregister the training study, starting with simulator feasibility (Milestone 3), and keep arm D.
