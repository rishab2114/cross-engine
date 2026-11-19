# Cross-Field Research Discovery Engine

*Independent research proposal · Rishab Mishra · Draft v3*

## Overview

I propose building a research discovery engine that searches across academic fields and turns promising connections into questions someone could actually test. A researcher could enter a specific problem, choose the fields to search, or let the engine explore broadly. Each suggestion would show which papers inspired it, how their ideas fit together, what the closest existing work already covers, and how to test the proposed connection.

**Research question.** Given the same collection of papers and the same total compute budget, does following connections across several papers produce a better shortlist of novel, testable research ideas than conventional literature search followed by AI brainstorming?

## The tool

The engine is the main deliverable. In guided mode, a researcher enters a question and can select which fields to search. In exploratory mode, the engine starts from a set of concepts and explores broadly across the selected fields, or across the full indexed collection. Both modes search candidate connections in batches and return a shortlist that the user can inspect and export.

The graph connects papers, problems, mechanisms, methods, and findings. Each extracted relationship links back to its source and the passage that supports it. A path might connect a mechanism described in one field with a method used to measure it in another. A proposal would explain the connection, state a testable hypothesis, and describe what evidence would count against it. It can flag what data a test would require and link to datasets when a source explicitly provides them.

## Which papers it would use

The engine would reuse relevant papers and bring in new ones. OpenAlex would supply a new multidisciplinary corpus of titles, abstracts where available, topics, publication dates, and citation links. Papers previously collected for GRAPH may be reused when they fit a query or field. The topics selected by the user define where the tool looks. A paper can contribute a mechanism or method even when it uses different terminology from the target field. ([OpenAlex work attributes](https://help.openalex.org/data/works/attributes/))

SciMuse, Impact4Cast, and Idea-Catalyst inform the design. The papers used by the engine would be assembled independently using field and date filters. The prototype would support adding more collections through the same process.

I propose economics and transport research for the first evaluation. These fields overlap through transport economics, so some connections between them will already sit inside one established literature. Instead of treating this as hidden noise, I will label each shortlisted path by whether it crosses that subfield boundary and report results for both groups. A pair of fields with less overlap is left for the follow-up study.

## First evaluation

All settings in this section are fixed and recorded before either method is run.

### Design

**Main comparison.** Graph-based search against keyword and semantic retrieval followed by AI brainstorming. Both methods get the same paper collection, the same evidence fields, the same language model, the same generation template and output format, and the same shortlist size. Their inputs differ by design, so the prompts cannot be identical. Only the generation step is held constant.

**Path-length check.** A pairwise-only version of the graph, run under the same cost cap, tests whether following longer paths adds value beyond single links.

**Questions.** 20 guided questions per field (40 in total), written before either run. Each method returns a shortlist of 10 ideas per question. These numbers are proposed and may change after a pilot run on separate questions, but they will be fixed before the main run.

**Scope.** The first evaluation tests guided mode only. Exploratory mode is included in the prototype and demonstrated, but it is not part of the comparison. Testing whether a broader corpus beats a single-field corpus is a follow-up study.

### Budget

I will use one end-to-end cost cap for the fixed batch of 40 questions, with a cost schedule set in advance. The count covers document indexing, graph extraction, embedding, retrieval, and idea generation for each method. Shared preparation is counted equally for every method, and each method's setup is charged once across the batch. I will report setup cost, cost per query, and wall-clock time. This shows what it costs to build the tool and what it costs to use it again.

### Primary outcome

The **historical hit rate**: for each question, the share of shortlisted ideas whose proposed connection was explicitly investigated in 2020–2024 work. The two methods are compared within each question, using a paired test across the 40 questions (Wilcoxon signed-rank). Every other measure in this proposal is secondary.

### Historical check

I will freeze the available literature at the end of 2019 and use papers from 2020–2024 as the evaluation window.

- **Matching rule.** A connection counts as investigated only if a later paper explicitly studies the relationship proposed. A joint mention of the two concepts does not count. I will write the rule and its examples before the run, apply it the same way to every shortlist, and record whether later work supports, challenges, or simply tests the idea.
- **Who matches.** A first matching pass may be automated. I will hand-audit a random sample of matches and non-matches and report how often the audit agrees with the automated decision.
- **Popularity baseline.** A method can score well here by proposing obvious pairings of popular concepts. As a control, I will pair concepts using only their pre-2020 frequency and growth trend, with no language model, and measure how often those pairs were studied later. The engine has to beat this baseline for the hit rate to mean anything. I will also report how common each shortlisted idea's concepts were before 2020, so readers can see whether either method won by playing safe.
- **What it measures.** The historical check measures whether ideas proved fruitful, not whether they were novel. The human review below covers novelty.

### Model leakage

A modern language model may remember work published after 2019, so the historical check is a retrospective benchmark, not a true forecast. Leakage probably favours the baseline. Retrieval followed by brainstorming relies more on what the model already knows, while the graph method grounds generation in pre-2020 evidence. A graph win would therefore be conservative. To measure leakage, I will give the model each shortlisted pairing with no supporting context and ask whether it has been studied. Then I will report how often it correctly identifies post-2019 work. If a capable model with an earlier training cutoff is available, I will repeat the comparison with it.

### Small human review (exploratory)

I plan to sample 24 proposals across the two methods, two fields, and shortlist ranks. Two suitably qualified reviewers will rate each proposal, for 48 ratings in total. Recruitment through university research contacts is a feasibility step. Reviewers will see the ideas in shuffled order with method labels hidden.

A separate literature check will use the same sources, date restrictions, query templates, citation-search procedure, and time allowance for every sampled idea. Reviewers will judge novelty against the closest prior work found by that common procedure. They will also score whether the hypothesis is specific and feasible to test. I will report agreement between reviewers and where coverage or data access limits the assessment.

With roughly three proposals per method-field-rank cell, this pilot is descriptive. I will not report significance tests from it.

### Secondary measures

- Source accuracy: whether each cited passage supports the relationship attributed to it
- Distinctness of ideas within a shortlist
- Results split by whether a path crosses the transport-economics boundary
- Pairwise-only graph against the full graph
- Cost and time as described in the budget section

## Limitations

- OpenAlex abstract coverage is uneven, and economics is a weak spot. Relationships are extracted from titles and abstracts, so many supporting passages will be single sentences.
- Economics and transport overlap, which may understate how much connections between more distant fields could help.
- The historical check rewards ideas that later became research topics. It cannot credit good ideas that nobody happened to pursue.
- The human review is small and depends on recruiting qualified reviewers.

## Contribution and deliverables

The research contribution is a direct test of whether graph paths add value over strong retrieval under matched conditions. The first release would include:

- A working prototype with guided and exploratory modes
- An exportable shortlist of ideas with sources and test designs
- A reproducible benchmark with the corpus snapshot, questions, matching rules, popularity baseline, and scoring rules

The tool can run independently and provide hypotheses for other projects to investigate later.

## Starting references

- Gu, X. and Krenn, M. (2026). Generating interesting scientific ideas using knowledge graphs and LLMs: Evaluations with 100 research group leaders. *Proceedings of the National Academy of Sciences*. [SciMuse](https://doi.org/10.1073/pnas.2611349123)
- Gu, X. and Krenn, M. (2025). Forecasting high-impact research topics via machine learning on evolving knowledge graphs. *Machine Learning: Science and Technology*, 6, 025041. [Impact4Cast](https://doi.org/10.1088/2632-2153/add6ef)
- Kargupta, P., Mehri, S., Hakkani-Tür, D. and Han, J. (2026). Sparking Scientific Creativity via LLM-Driven Interdisciplinary Inspiration. arXiv:2603.12226. [Idea-Catalyst](https://arxiv.org/abs/2603.12226)
