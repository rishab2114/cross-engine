# Cross Engine training extension plan

Draft v2 · 24 November 2026

**Working title — Training for Unseen Combinations through Coherence and Research-Community Availability**

Develop a method that selects plausible, underexplored combinations of mechanisms, converts them into verifiable training tasks, and teaches a model progressively harder interactions. Test whether this improves performance on combinations withheld from training and, subsequently, on a later real dataset.

This is a proposed extension within Cross Engine. The architecture, initial task, sample sizes, and model choices below are draft recommendations. The repository review informing this plan inspected Cross Engine at `7cb9ef1`, GRAPH at `5f8757c`, and Alien Space of Science at `a55d660de75c99afe9e0948781cdb828fe3798eb`.

**1. Research question and contribution**

Does selecting training scenarios using scientific coherence and low research-community availability improve generalization to unseen combinations, beyond selection by coherence, rarity, diversity, and difficulty alone?

The secondary question is whether presenting the selected examples from simple to complex adds value beyond presenting the same examples in a shuffled order.

Curriculum learning, synthetic training data, graph-based composition, and the Alien scoring objective already have published precedents. The proposed contribution is the connection between an explicit estimate of community availability, the selection of executable training tasks, and measured downstream generalization. Originality remains a hypothesis to check through a fuller related-work review. [Curriculum learning](https://ronan.collobert.com/pub/matos/2009_curriculum_icml.pdf) · [CompGen](https://openaccess.thecvf.com/content/CVPR2026/html/Wang_Synthetic_Curriculum_Reinforces_Compositional_Text-to-Image_Generation_CVPR_2026_paper.html) · [Synthetic reasoning training](https://proceedings.iclr.cc/paper_files/paper/2026/hash/9e95016eceae77e945b84554b0f1bb49-Abstract-Conference.html) · [Alien paper](https://arxiv.org/abs/2603.01092)

**2. How the projects complement each other**

| Component | Responsibility | Existing work to reuse or adapt |
|---|---|---|
| Cross Engine | Own the extension, source corpus, provenance, candidate selection, and experiment records | Corpus readers, paper identifiers, retrieval, budgeting, job handling, reproducible analysis |
| Alien Space of Science | Extract atoms and rank combinations by coherence and availability | Processing pipeline, clustering, dataset builders, scorer architectures, sampling and reconstruction |
| GRAPH | Inform scenario construction and evaluation under distribution change | Scenario interface patterns, frozen comparisons, stress tests, shift evaluation, uncertainty reporting |
| New extension code | Convert selected combinations into tasks and train a downstream model | Task compiler, answer verifier, curriculum scheduler, training runner, composition-based splits |

GRAPH's motif generators are specific to transaction networks. Transport or reasoning tasks require their own generators and outcome definitions. Shared infrastructure should have explicit inputs and outputs, with repository versions recorded in each experiment.

The current GRAPH result motivates a careful test. Forecast-selected combinations failed to deliver a reliable advantage over random combinations as stress tests. This extension examines whether selection helps when examples are used to train a model. Cross Engine's weak synthetic-to-real link-detector results also make independent evaluation central to the design. [GRAPH results](https://github.com/rishab2114/GRAPH/blob/5f8757cd4c1909d3a8d1ab9ccc5384eaf1cd6e68/docs/results/e3e4.md) · [Cross Engine predictions](https://github.com/rishab2114/cross-engine/blob/7cb9ef11456c11c7a34bb2cf6f5b43a488311591/data/detector_predictions_selection_v2.json)

**3. Reuse the Alien implementation**

Pin the upstream commit and include its MIT license and copyright notice with copied components. Record upstream paths and local modifications. A vendored copy under `third_party/alien_space/` with a small integration adapter is the proposed starting point. Check each downloaded dataset and model's release terms as part of acquisition. The repository documents that original paper content retains its source terms. [License](https://github.com/alejandrohdez00/alien-space-of-science/blob/a55d660de75c99afe9e0948781cdb828fe3798eb/LICENSE) · [Release data](https://github.com/alejandrohdez00/alien-space-of-science/blob/a55d660de75c99afe9e0948781cdb828fe3798eb/DATA.md)

| Upstream code | Planned use | Required adaptation |
|---|---|---|
| `atomization/pipeline.py` and `atomization/stages/` | PDF summaries, concept extraction, refinement, resumable processing | Domain prompts, provider configuration, passage-level provenance |
| `atomization/stages/cluster_atoms.py` | Embeddings, clustering, canonical atom descriptions | Inspect cluster quality and retain methodological distinctions |
| `generation/make_datasets.py` and `generation/make_availability.py` | Coherence and author-repertoire training sets | Stable author IDs, domain-specific vocabulary, explicit time cutoffs |
| `generation/model.py`, `two_tower_model.py`, and training scripts | Coherence and availability scorers | Retrain for the chosen atom catalogue |
| `generation/scoring.py` and `sample.py` | Rank a common candidate pool | Keep pool normalization fixed across methods, validate small and large combinations separately |
| `generation/reconstruct.py` | Convert combinations into structured proposals | Output executable task specifications and verifier inputs |

First reproduce a small scoring run using released artifacts in their original LLM-research domain. The README supports CPU inference and sampling without LLM calls. Atomization and reconstruction require provider access. The released inference artifacts total approximately 358 MB, while the original availability training used four A100 GPUs. A small smoke test and a full domain retraining have very different costs. [README](https://github.com/alejandrohdez00/alien-space-of-science/blob/a55d660de75c99afe9e0948781cdb828fe3798eb/README.md) · [Adaptation guide](https://github.com/alejandrohdez00/alien-space-of-science/blob/a55d660de75c99afe9e0948781cdb828fe3798eb/ADVANCED.md)

**4. First application and executable tasks**

The proposed application is urban mobility, building on Cross Engine's existing Study 2 direction. Begin with a bounded simulator covering queues, capacity limits, delayed arrivals, transfers, and route dependencies. The first supervised task predicts whether a specified disruption produces a missed connection or queue overflow under explicit rules.

An illustrative progression is a single capacity constraint, then capacity combined with a demand surge, then those mechanisms interacting with a delayed arrival and a downstream transfer. Complexity is measured through dependency depth, interacting mechanisms, and distracting information. Increasing the number of atoms alone does not establish increasing difficulty.

Use a small audited atom catalogue first. Paper-derived atoms must map to explicit simulator operations with assumptions and units. Every accepted scenario produces inputs, a target generated by the simulator, and a trace explaining that target. Check the generator against independently calculated examples. Coherence scores prioritize candidates, while executable constraints establish whether they define a valid task.

A feasibility target is 100–300 accessible papers and 10–30 executable mechanisms. These are workload estimates. This corpus may support a processing prototype while remaining too small for a meaningful author-availability model. Assess author coverage, atom coverage, and score quality before freezing the training experiment. Expand the corpus if necessary. Any interim rarity-based selector should be named and evaluated as such.

The transport experiment requires a simulator and reference outcomes. Cross Engine's earlier study of expert-rated proposals requires recruited reviewers. Its review protocol and this extension's supervised evaluation address different outcomes. [Study 2](https://github.com/rishab2114/cross-engine/blob/7cb9ef11456c11c7a34bb2cf6f5b43a488311591/STUDY2_USE_CASES.md)

**5. Candidate selection and curriculum**

Create one candidate pool before selecting training sets. Use the same task compiler, validity rules, and common basic-mechanism examples for all methods. Record compilation success and rejection rates by method, including cost. Freeze a replacement rule within each difficulty band so one method's failed proposals cannot silently reduce its training budget.

For the Alien selector, combine standardized coherence and unavailability using the upstream weighted score. Tune the weight on development data only. Normalize within comparable complexity bands, and match the final training sets on difficulty, length, primitive coverage, and example count where feasible. Report residual differences and diversity explicitly.

Low publication frequency, low author availability, and difficulty for the learner are distinct quantities. Measure all three. Verify that the author-based score adds information beyond simple rarity before interpreting it as the mechanism responsible for a result.

Use an incrementally trainable learner, initially a small neural model over structured scenarios. Freeze its architecture, initialization scheme, training steps, optimizer, and basic-mechanism warm-up across arms. An LLM fine-tuning replication can follow once the selection effect is established and its compute is measured.

**6. Comparisons**

| Arm | Scenario selection | Presentation |
|---|---|---|
| A | Uniform over valid candidates within difficulty bands | Simple to complex |
| B | Coherence | Simple to complex |
| C | Coherence plus rarity and diversity | Simple to complex |
| D | Coherence plus author unavailability | Simple to complex |
| E | Exactly D's examples and exposure counts | Shuffled |
| F | Exactly C's examples and exposure counts | Shuffled |

The proposed primary comparison is D versus C. D versus B tests the addition of availability to coherence. D versus E isolates presentation order for Alien-selected data. C, D, E, and F form a two-by-two comparison of selection and ordering. A establishes the value of deliberate selection over valid random sampling.

Match training steps and exposure counts. Report selection, preprocessing, generation, and training costs separately. A later fixed-total-cost comparison can test practical efficiency once those costs are known.

**7. Evaluation and leakage control**

Split by the canonical composition of mechanisms and relations before generating individual examples. Training, development, and test sets should use disjoint combination families. A new random seed or numerical value within a familiar composition is insufficient to create an unseen interaction.

Build and freeze the test set independently of each selector's preferred candidates. Include familiar-composition generalization, unseen compositions of learned mechanisms, and deeper compositions. Keep these outcomes separate. Use the same test tasks across all arms, inspect duplicate templates and graph isomorphisms, and keep test outcomes out of curriculum adaptation.

The proposed primary metric is macro-averaged balanced accuracy across unseen combination families. Report per-family performance, ordinary accuracy, calibration, and familiar-task retention. Start with three paired seeds for feasibility, then select the confirmatory seed count and family count using development variance and a power calculation. Confidence intervals should account for combination families and training seeds, since thousands of generated examples can share one underlying structure.

To support the claim about future events, add a dated real-data evaluation after the controlled experiment. Freeze source papers, atom extraction inputs, author histories, and selection before the target period. Record the extraction model and its training provenance. Contemporary LLMs can introduce later knowledge even when supplied older papers. Where a strict historical reconstruction is unavailable, use a prospective future evaluation and limit retrospective claims accordingly.

**8. Milestones and decisions**

| Milestone | Deliverable | Evidence needed to proceed |
|---|---|---|
| Upstream reproduction | Pinned code, checksums, small scoring run, dependency and cost record | Successful artifact loading, reproducible candidate scores, token mappings verified |
| Domain processing | Audited atoms, author metadata, executable mechanism mapping | Adequate coverage, supported extraction, useful coherence and availability scores |
| Scenario feasibility | Simulator, reference traces, disjoint composition splits | Correct answers and enough valid scenarios in every required band |
| Development pilot | Six arms with paired seeds and measured compute | Usable learning curves, calibrated difficulty, variance estimates, failure analysis |
| Preregistration | Frozen hypothesis, primary metric, thresholds, sample size, code and data hashes | All design choices set before confirmatory test outcomes are inspected |
| Confirmatory experiment | Per-family results, seed variation, uncertainty, cost, ablations | Evaluate the frozen comparisons, including null and adverse outcomes |
| External replication | Independent simulator or later real-data benchmark | Transfer beyond the original generator |

Set the minimum useful effect and acceptable familiar-task degradation from development data before confirmation. A positive result requires the primary improvement to clear the predefined threshold with uncertainty accounted for. If gains appear only on the original simulator, the supported contribution is bounded to that environment. If rarity and diversity match author unavailability, the simpler selector becomes the stronger practical explanation.

**9. Proposed implementation boundaries**

Place the extension under a dedicated Cross Engine experiment directory with a configuration file and its own preregistration. Start with five concrete modules for upstream adaptation, executable scenario generation, composition splits, curriculum training, and evaluation. Reuse existing storage and budget utilities where their behavior fits.

Version every atom catalogue, source snapshot, candidate pool, scorer, task compiler, split, and learner checkpoint. Each training example should resolve to its mechanism combination, source evidence, generated conditions, verified target, and difficulty band. Each run should resolve to a frozen configuration and paired seed.

The first implementation milestone is a reproducible upstream smoke test followed by one end-to-end domain example, from source passage through an atom combination to a verified training task and learner prediction. That establishes the technical connection before scaling the corpus or training budget.


**10. LLM integration in both projects**

Cross Engine already uses LLM generation and judging jobs. This extension adds explicit roles for extraction, scenario compilation, criticism, and downstream learning. GRAPH can use the same interfaces for its literature and scenario work, with domain-specific schemas and validators.

| Project and role | LLM contribution | Validation and comparison |
|---|---|---|
| Cross Engine literature processing | Extract mechanisms, assumptions, contexts, contradictions, and supporting passages into typed records | Audit source fidelity and extraction stability on a fixed sample |
| Cross Engine proposal generation | Explain selected atom combinations and produce structured task specifications | Compile against supported simulator operations and verify targets independently |
| Cross Engine critical review | Identify missing assumptions and propose repairs using retrieved evidence | Compare with an equal-budget generic critique and retain rejection logs |
| GRAPH literature processing | Map literature passages to a controlled vocabulary of mechanisms and graph motifs | Validate each mapping and retain paper dates and passages |
| GRAPH scenario generation | Propose bounded motif compositions and parameter specifications | Use the existing executable generator where supported and check topology, ranges, labels, and temporal constraints |
| GRAPH detector interpretation | Explain observed detector failures using measured features and scenario traces | Check explanations against computed results and controlled feature interventions |
| Both projects as training studies | Fine-tune an open-weight LLM on independently verified examples, progressing from simple to complex | Test unseen combination families, ordinary-task retention, calibration, and cost |

**Teacher and learner experiment.** A fixed teacher LLM can translate combinations into training tasks. The learner is the model whose parameters are trained on those tasks. Pin teacher model, prompts, decoding settings, and generation budget across curriculum arms. Produce reference answers through the simulator, solver, or validated labels. An LLM critic supplies diagnostic feedback, while correctness is determined through those reference outcomes.

For the LLM learner replication, begin with supervised fine-tuning of a small open-weight model and evaluate the same C/D/E/F comparison from section 6. Use an identical base checkpoint for each arm and equalize training tokens and optimizer steps. Report generated-token cost as well as retained-example count. Add reinforcement learning only if the supervised pilot identifies a concrete need and supplies a reliable reward verifier.

**Measure the contribution of the LLM.** On a bounded secondary experiment, compare deterministic task templates with LLM-compiled tasks from the same selected combinations. Hold selection and learner training constant. This identifies whether the compiler adds useful variation or introduces errors. Similarly, benchmark LLM motif selection against the existing graph selector and valid random selection using the same evidence and budget.

**Integration sequence.** Add the shared structured schema and provider adapter in Cross Engine, then implement domain adapters for GRAPH and the proposed mobility simulator. Reuse Cross Engine's existing job and budget handling where possible. Each request records its source evidence, model, prompt hash, response, validated output, retry count, and cost. Resume completed work through keyed caches. Treat malformed outputs and unsupported operations as recorded failures with a fixed retry limit.

Development feedback can suggest new candidate combinations and curriculum changes. Freeze those choices before each confirmatory evaluation. Any iteration informed by evaluation results receives a new evaluation set. Preregister the GRAPH LLM extension before running its comparisons and record its relationship to the existing Tornado study.

**Initial deliverables for the LLM integration.** A validated extraction sample, an executable scenario schema, one verified LLM-generated scenario per domain, a compiler comparison, and an LLM learner feasibility run. Scale only after measuring correctness, yield, and compute on these examples.
