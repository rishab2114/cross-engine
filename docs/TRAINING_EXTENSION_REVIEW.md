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
- **"Synthetic Curriculum Reinforces Compositional Text-to-Image Generation"** (CompGen): arXiv 2511.18378 (2025), **and it has an official CVPR 2026 proceedings entry** (corrected 25 Nov after Codex's review; OpenAlex's venue record was simply missing it).
- **"Learning from Synthetic Data Improves Multi-hop Reasoning"**: **has an official ICLR 2026 proceedings entry** (corrected 25 Nov). These neighbouring results mean "graphs + synthetic data + curriculum" is not itself a new contribution.
- **GRAPH results** (`rishab2114/GRAPH`): outside this session's repository access, so **not verified here**.

## Recommended order
1. Finish Cross Engine judge repair (Amendment 5).
2. **Alien-lite** (free): does an author-availability score beat a rarity baseline at recovering 2020–2024 keyword combinations from frozen pre-2020 data, in economics and transport?
3. **Upstream smoke test** (free): released artifacts, a small CPU scoring run, checksums.
4. Only if 2 shows availability carries signal beyond rarity: preregister the training study, starting with simulator feasibility (Milestone 3), and keep arm D.

## Iteration after inspecting the upstream code (24 Nov, later)
**What the inspection and smoke test establish** (`docs/ALIEN_CODE_REUSE.md`, `results/alien_smoke_test.json`)
- **The pipeline runs here, for free.** Upstream sampling and scoring run on our CPU in **34 s** for 1,000 candidates, with **0 LLM calls and $0**, and the downloaded artifacts match their published checksums (9 of 9). So Milestone 1 of the plan, upstream reproduction, is **done** at smoke-test scale.
- **Reusable without an LLM:** the coherence transformer, the two-tower availability model, the dataset builders, scoring and sampling (about 2,500 lines). Only atomization, LLM cluster naming and reconstruction need paid providers.
- **The released models only cover LLM research** (273 atoms). A transport or economics application needs retraining on our own atoms and authors.

**A revised, cheaper path (v3)**

| Stage | What | Free? | Gate to the next stage |
|---|---|---|---|
| 0 | **Alien-lite temporal test:** keyword-cluster atoms, OpenAlex authorships (≈ $0.06), CPU-retrained coherence and availability, recovery of 2020–2024 combinations against **rarity** and popularity baselines | Yes | Availability must beat rarity at recovering strictly novel combinations (CI excluding zero) |
| 1 | **Mechanism catalogue for a transport simulator:** 10–30 hand-specified operations (capacity, queue, delay, transfer, surge), each linked to the atom clusters that describe it | Yes (manual) | Every operation is traceable to atoms and has unit tests |
| 2 | **Simulator and template compiler:** deterministic task generation and correct answers, with composition-family splits | Yes (CPU) | Correct answers checked on hand-computed examples; enough valid tasks in every difficulty band |
| 3 | **Small learner** (MLP or GNN over structured scenarios, CPU), arms A–F, 3 paired seeds | Yes (CPU) | Usable learning curves and variance estimates |
| 4 | Preregistered confirmatory run | Yes (CPU) | — |
| 5 | LLM-compiler comparison and open-weight LLM learner | **No.** Needs paid tokens or a GPU | Needs explicit user approval |

**The key change from the plan:** Stage 0 comes first and *decides* whether arm D (author unavailability) exists at all. If availability doesn't beat rarity in our domain, the training study runs with A, B, C, F only and reports that availability was not informative here. That is still a useful result, and it makes the GRAPH null result easier to interpret.

## Response to Codex's disagreement (25 Nov)
See `AGENT_DISCUSSION.md`. In short:
- **Temporal recovery no longer gates the training study.** It stays the gate for using availability inside Cross Engine's discovery filter.
- **The training pilot's gate is Codex's:** valid executable tasks, nondegenerate scores, reliable provenance and genuinely different portfolios.
- **A cheap availability proxy comes before any learned encoder:** author-set overlap between the two concepts' pre-2020 author communities.
