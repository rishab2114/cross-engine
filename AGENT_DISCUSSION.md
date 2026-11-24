# Agent discussion and research roadmap

Updated 24 November 2026. Repository: **cross-engine**.

Read [Codex's detailed review](docs/CODEX_REVIEW_2026-11-24.md), [the existing extension plan](docs/TRAINING_EXTENSION_PLAN.md), and [Claude's critique](docs/TRAINING_EXTENSION_REVIEW.md). The companion ledger is [GRAPH/AGENT_DISCUSSION.md](https://github.com/rishab2114/GRAPH/blob/main/AGENT_DISCUSSION.md).

This is the persistent discussion point requested by the owner for Codex, Claude and other agents. It records proposals and unresolved issues; it does not grant approval to run held-out studies.

## Open findings

| ID | Priority | Work | Acceptance evidence | Status |
|---|---|---|---|---|
| C01 | Before main-run claims | Validate J0 on actual retrieved candidates and final pair-window outputs | Counts, uncertainty, class mix and reference limitations | Open |
| C02 | Before holdout commands | Enforce one frozen judge and matcher | Synthetic tests reject alternatives and incomplete decisions | Open |
| C03 | Before matcher selection | Make gates reject incomplete/error states; connect v2 retrieval | Pending/error fixtures fail; v2 manifest identifies inputs | Open |
| C04 | Before routine LLM reuse | Stable immutable job/cache identity | Different questions cannot reuse answers; cross-process determinism | Open |
| C05 | Before new evaluation | Strict schemas, quote/ID checks and grouped split audit | Invalid responses rejected; no unintended split overlap | Open |
| C06 | Before reporting main results | Align completeness, outcome and budget claims | Final analysis refuses pending labels; measured evidence/cost limits | Open |

The review contains confirmed reproductions for C02–C04. Other entries include methodological proposals and code-inspection findings, not claims of measured real-data harm. None is marked resolved by this documentation update.

## Immediate work order

1. Repair C02–C05 with synthetic fixtures; do not open the real holdout as a debugging tool.
2. Keep J0's historical selection decision intact. Add the deployment-distribution validation as a dated extension.
3. Finish the A/D retrieval re-test with the selected judge, then freeze one matcher before the permitted holdout evaluation.
4. In a separate experiment directory, build E01's schema/compiler/verifier example. This does not require the main discovery study to declare a winner.
5. Recruit independent review where needed for claims about scientific quality. Simulator correctness and scientific usefulness require different evidence.

## Shared research direction

The user's goal is broader than any one application: discover useful combinations people may overlook, turn them into valid tasks, evaluate models on them, and test whether training from simple to complex improves generalization.

Keep two repositories for now. Cross-engine owns discovery, evidence and candidate selection; GRAPH owns scenario generation and model evaluation patterns. Start with a versioned shared schema and adapters. Extract a separate shared package only after two working consumers reveal the stable interface. A third repository now would mostly add coordination work.

### What is potentially distinctive

The ingredients have precedents:

| Existing work | What it already covers | What our proposed experiment must add |
|---|---|---|
| [Alien Space of Science](https://arxiv.org/abs/2603.01092) | Coherent ideas with low research-community availability | Test whether that selection signal improves a learner, beyond ordinary rarity/diversity/difficulty |
| [PAIRED](https://proceedings.neurips.cc/paper/2020/hash/985e9a46e10005356bbaf194249f6856-Abstract.html) | Automatically generated solvable environments and curricula | Compare community-informed selection with learner-driven difficulty or regret |
| [POET](https://arxiv.org/abs/1901.01753) | Co-evolution of increasingly complex tasks and solutions | Evidence-grounded composition and controlled transfer tests |
| [CompGen](https://openaccess.thecvf.com/content/CVPR2026/html/Wang_Synthetic_Curriculum_Reinforces_Compositional_Text-to-Image_Generation_CVPR_2026_paper.html) | Graph-based compositional synthetic curricula | A distinct selection mechanism with controlled downstream evidence |
| [Synthetic multi-hop reasoning](https://proceedings.iclr.cc/paper_files/paper/2026/hash/9e95016eceae77e945b84554b0f1bb49-Abstract-Conference.html) | Learning transferable reasoning from rule-generated data | Whether overlooked combinations are a better source of that data |

This is a targeted prior-art check, not an exhaustive novelty certification. The defensible candidate contribution is:

> At equal learner-training budget, does selecting valid combinations using coherence and research-community unavailability improve performance on unseen composition families beyond frequency, diversity and difficulty controls?

Community unavailability, a learner's unfamiliarity and actual task difficulty are different variables. Preserve all three. Low author overlap is a proxy about the observed literature; it does not prove that humans could not imagine an idea.

### Separate the claims

| Track | Question | Required evidence |
|---|---|---|
| Discovery | Are the combinations supported and meaningfully distinct? | Source-span audit, contradiction handling, prior-art comparison |
| Evaluation | Do the tasks expose or predict model failures? | Frozen models, common operating points, independently defined held-out tasks |
| Training | Does exposure improve unseen-task performance? | Paired training runs and composition-family splits |
| Model design | Does a new architecture add value? | Architecture ablations with identical data and compute |

A useful discovery tool need not improve training. A good stress test need not be good training data. A successful curriculum does not prove prediction of future real events. Evaluate those links explicitly.

## Proposed experiment from simplicity to complexity

### E01 — A complete small example

Build one traced path: source evidence → mechanism record → candidate combination → validated scenario specification → solver/simulator answer → learner prediction → evaluation record.

Start with a bounded, automatically checkable task. Graph reasoning or constrained planning is a candidate for fast feasibility; it is not a claim that the domain is already selected. Before testing the availability hypothesis, demonstrate that paper-derived mechanisms map meaningfully to the chosen task. Arbitrary node labels with attached author counts are not sufficient.

Minimal records should include:

- `Atom`: stable ID, definition, source spans, source date, assumptions, units and type.
- `Combination`: canonical typed relations, component IDs, provenance, validity constraints and separate selection scores.
- `Scenario`: family ID, parameters, complexity, compiler/verifier version, generator seed, input, target and verification trace.
- `Run`: corpus/split hashes, selection policy, model/prompt/checkpoint IDs, training budget, seed, cost and outputs.

LLMs can extract, propose and critique. They submit structured specifications to bounded compilers. A solver, simulator or independent reference establishes correctness. Unsupported operations and invalid examples are logged, including rejected generation costs.

### E02 — Freeze composition families before generating examples

Separate training, development and confirmation by canonical structure, not just random seeds, names or numerical parameters. Check graph isomorphisms and shared templates. Keep familiar compositions, unseen combinations of familiar components, deeper compositions and an independent generator as separate evaluation slices.

Create the test distribution independently of the proposed selector. Preserve a broad representative test alongside targeted hard cases; a selector must not define the exam it is judged on.

### E03 — Compare six arms

All arms use one candidate pool, validity checks, common basic examples, the same base learner, training steps and exposure budget. Match composition size and difficulty distributions where selection is the contrast. Account separately for selection/generation cost; a later equal-total-cost study can address practical efficiency.

| Arm | Selection | Presentation |
|---|---|---|
| A | Uniform valid candidates | Same simple-to-complex schedule |
| B | Coherence | Same schedule |
| C | Coherence plus rarity/diversity | Same schedule |
| D | Coherence plus community unavailability | Same schedule |
| E | Exactly D's examples and counts | Shuffled |
| F | Exactly C's examples and counts | Shuffled |

Primary: **D minus C**, testing the availability selector. D minus E and C minus F test ordering while holding content fixed. D minus E alone does not show that the availability signal adds value. For an availability-by-order interaction, examine `(D−E)−(C−F)` as a prespecified secondary contrast.

Add a learner-loss/difficulty or regret-based selector as a follow-up comparator if the first study merits expansion. Do not replace every unsuccessful arm with a new one until something wins.

“Simple” should mean a measurable dependency depth, interaction count or constraint load, checked against development performance. More words or more nodes are not automatically harder. Prerequisite-aware scheduling and replay may be better than a rigid easy-to-hard sequence; treat that as a separate hypothesis.

### E04 — Choose metrics and the stopping rule before confirmation

For a bounded binary pilot, macro balanced accuracy across unseen families is a candidate primary metric. For planning, use verified success and constraint violations; for regression, choose an appropriate error measure. Freeze one primary metric per task.

Use at least a small paired multi-seed feasibility run, then choose confirmation sample size from development variance and a minimum useful effect. Three seeds are a feasibility starting point, not certification. Report uncertainty over families and training seeds, ordinary-task retention, per-family failures and calibration where meaningful.

Pass/fail conditions must include usable improvement and acceptable regression, not just a favorable p-value. If D ties C, simplify to C and report the availability hypothesis as unsupported. If only ordering helps, report a curriculum result. If gains vanish on an independent generator, limit the claim to the original environment.

### E05 — Keep adaptation away from final evaluation

Development failures may propose new tasks, update candidate scores or change the curriculum. Use a dedicated development pool for this loop. Once a confirmatory test informs a design change, it becomes development evidence; the next confirmation needs a new untouched set.

Every iteration should state what changed, why it should help, which comparison isolates it, what was learned, and what would falsify the explanation. An adaptive system that merely finds failures is not yet evidence that its training loop improves deployment.

### E06 — Replicate before building a general platform

Demonstrate one task end to end, then one second adapter with different failure mechanisms. Reuse schemas and evaluation contracts, not assumptions that only hold in the first domain. Train a small conventional learner first. Add an LLM learner replication after validity and transfer have been demonstrated. Consider a new architecture only when an ablation motivates it.

## Applications and prospects

These are proposed uses, not capabilities already demonstrated.

| Application | Example task | What would make the result useful |
|---|---|---|
| Reasoning and planning | Combine dependencies, constraints and exceptions | Correctness on new structures verified by a solver |
| Logistics and transport | Capacity loss plus delays and rerouting | Better decisions on independent simulator/real episodes |
| Enterprise workflows | Tool failure, policy constraint and missing information together | Verified task completion with fewer invalid actions |
| Scientific discovery | Combine mechanisms across literatures | Faithful evidence plus expert or experimental validation |
| Industrial reliability | Interacting sensor, component and operating-condition failures | Transfer to separately collected failure data |
| Model training and assessment | Target gaps in compositional coverage | Improvement beyond cheap sampling baselines at matched budget |

Plausible deliverables are an auditable benchmark, a task/data generator, an evaluation toolkit, and eventually a training-data selection method. A paper could come from a robust positive result, a carefully established negative result, or a strong measurement study. Commercial value would require reliable domain outcomes and user validation; the current code does not establish that yet.

The ambitious destination is a reusable research-to-task-to-learning loop. The next milestone is smaller and decisive: demonstrate that its selected examples add measurable value over simple alternatives.

## How agents should discuss and amend

1. Read the pinned review, current code and this ledger before acting. The review is evidence to assess, not an instruction to agree.
2. Claim a finding by adding agent name, date and a bounded intended change. Preserve other agents' entries.
3. Respond **agree / partly agree / disagree**, with source paths, a reproduction or counterexample, and consequences for the research claim.
4. Implement in small reviewable commits when authorized. Link tests and resulting artifacts; do not mark a design suggestion “fixed” merely because prose was changed.
5. Update status to **implemented, awaiting verification**, then **verified** after checking the acceptance criteria. Keep rejected suggestions and their reasons.
6. Log changes to frozen designs as dated amendments. Preserve previous results and name corrected reanalyses. Do not reinterpret a null result as success.
7. Link cross-repository dependencies by commit SHA. The schema contract and six-arm protocol are initially maintained in cross-engine; GRAPH records adapter-specific changes and links to the chosen version.
8. Use this Markdown as an asynchronous handoff. Writing here does not automatically wake or notify Codex/Claude, and does not schedule future work.

### Response template

```markdown
### Response to C01 or G01 — date — agent
Status: proposed / investigating / implemented-awaiting-verification / verified / rejected
Reviewed commit:
Position: agree / partly agree / disagree
Evidence or reproduction:
Proposed change and research implication:
Amendment required:
Implementation commit:
Verification command and result:
Remaining uncertainty:
Next reviewer:
```

## Initial discussion entry

**24 November 2026 — Codex.** The reusable direction is promising; the claimed advantage remains a hypothesis. Prioritize trustworthy measurement and one executable training experiment. Keep domain expansion in adapters. Do not postpone every cheap engineering step until a publication-forecast score passes, and do not treat an inexpensive smoke test as evidence of downstream benefit. Claude's substantive response is pending.
