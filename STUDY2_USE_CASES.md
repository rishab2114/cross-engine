# Study 2 (draft): Assumption-aware evidence-path transfer in urban mobility

*Design draft only. Nothing in this document has been run. It needs its own preregistration before any generation, and it is **gated on reviewer recruitment** (see the gate below).*

## Question
Do **assumption-aware, evidence-grounded knowledge paths** improve the quality and practical testability of cross-disciplinary research applications, compared with conventional retrieval and with graph-guided generation, when evidence and compute are equal?

Working title: *From Papers to Pilots: Evaluating Evidence-Grounded Cross-Domain Knowledge Transfer.*

## Why this framing (positioning)
The literature already covers graph-based and facet-based idea generation:
- **SciMuse** (Gu & Krenn, *PNAS* 2026): graph-selected concept pairs did not beat a titles-only GPT baseline on expert-rated interest.
- **Graph2Idea** (Li, Tu & Han, arXiv 2026) and **ResearchLink** (Borrego et al., *Knowledge-Based Systems* 2025): typed and graph-structured context for hypothesis generation.
- **Scideator** (Radensky et al., ACM CAIS 2026): recombination of purposes, mechanisms and evaluations, with novelty checking.
- **SAO knowledge-graph recombination over patents** (Chung, Seol & Yoon, *IEEE TEM* 2026): recombination aimed at practical innovation.

So neither graph construction nor recombination is the contribution. The question tested here is narrower: **does explicitly checking whether a mechanism transfers (assumptions plus contradicting evidence) add value beyond an equally resourced generic critique?**

## Scope
- **Target domain:** urban mobility and public-sector transport operations, for example crowding, reliability, routing, congestion and information delivery.
- **Source domains:** behavioural economics, operations research and computing (a small curated set added to the existing corpus).
- **Possible data for later proof-of-concept checks:** Singapore LTA DataMall (bus arrival, load and passenger-volume data; registration required) and the Mobility Database (transit feeds). Observational or simulated results will **not** be presented as proof that an intervention works.

## Methods
All methods share the same source universe, generation model, output schema and shortlist slots. Indexing and extraction costs are reported separately.

| Code | Design | What it isolates |
|---|---|---|
| RN | Retrieval + LLM, under the same novelty screen | The conventional workflow |
| G0 | The existing keyword co-occurrence graph + LLM | Untyped graph paths |
| G1 | Typed evidence paths (problem, mechanism, method, context, evidence, contradiction) extracted **only from shortlisted papers**, each claim tied to a passage | The value of relation structure |
| G1-critic | G1 plus a **meaningful generic critical-revision pass** with the same evidence access and the same extra budget as G2 | The control for the extra compute |
| G2 | G1 plus explicit transfer validation: list the assumptions the transfer needs, search for contradicting evidence, reject unsupported candidates | The value of assumption-aware checking |

**Key comparisons:**
- **G2 vs G1-critic** (primary). G2 vs G1 alone would be confounded by G2's extra compute.
- G1 vs G0.
- G0 vs RN.

**Mechanistic ablation: counterfactual evidence removal.** Remove a crucial supporting paper or path, then re-run. A recommendation that doesn't change shows the evidence was decoration, not grounding.

## Output: a standard discovery record
| Field | Content |
|---|---|
| Target | Actor, specific problem, setting |
| Combination | Mechanism (from field X) + method (from field Y) |
| Evidence | Source IDs and supporting passages |
| Transfer logic | Why the mechanism should apply in the target setting |
| Constraints | Assumptions, risks, contradicting evidence |
| Proposal | A specific action someone could take |
| Experiment | Metric, comparison group, failure condition |
| Prior-art status | Studied / tested / adopted / unresolved, with sources |

A method may **reject** a candidate rather than produce a plausible-sounding but unsupported proposal. Rejections are counted.

## Outcomes, kept separate
1. **Primary: blinded expert ratings** on a calibrated rubric covering specificity, feasibility, testability, evidence support and contextual fit.
2. **Secondary: retrospective real-world evidence.** Documents from 2020–2024 showing the intervention was **proposed**, **piloted** or **adopted**, as three separate categories.
   - A document that mentions both ingredients is a **lead**; a documented deployment combining A and B is an **outcome**.
   - This needs its own validated matcher, built with Study 1's protocol: known-outcome controls, hard negatives and a sealed holdout.
3. **Mechanistic:** citation faithfulness, support for the essential assumptions, the rate at which contradicting evidence is detected, and the counterfactual-removal results.

## Gate: reviewers
Before any generation run:
1. Recruit transport, economics or operations-research reviewers.
2. Agree the rubric.
3. Run a small calibration exercise and report inter-rater agreement.

**Without expert reviewers, Study 2 stays a feasibility prototype** and makes no claim about superior practical quality.

## Feasibility pilot (once reviewers are available)
8 target problems × 3 ideas × 5 methods = 120 proposals, rated by 2 blinded reviewers. Its purpose is to calibrate the instruments and estimate power, **not** to declare a winner.

## Evidence sources for adoption outcomes
| Source | Reachable here? |
|---|---|
| OpenAlex (reports, grey literature) | Yes (metered: $1/day free) |
| Agency publications and news | Uncertain; needs dated snapshots |
| Patent databases (PatentsView, Lens) | Needs an API key |
| Policy-document indexes (for example Overton) | Needs a subscription |

## Dependencies on Study 1
Study 2 reuses the corpus, retrieval, the G0 graph, the job and blinding infrastructure (job metadata in sidecar files, opaque item ids) and the **matcher-validation protocol** (Amendment 4). It does not reuse Study 1's outcome measure.
