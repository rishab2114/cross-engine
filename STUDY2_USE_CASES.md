# Study 2 (draft): From connected research to practical use cases

*Design draft only. Nothing in this document has been run. It builds on the Study 1 engine and benchmark.*

## The idea in one line
Take A (a mechanism, finding or problem) and B (a method, technology or practice) from different papers. Find C, a specific thing someone could **do**, that uses part of A and part of B. Then check whether anyone later actually tried it.

Study 1 asks whether a connection was later **studied**. Study 2 asks whether a combination was later **tried in practice**.

## What a use case is (and is not)
A use case must name all four parts. If any part is missing, it is a research topic, not a use case.

| Part | Question it answers | Example |
|---|---|---|
| **Actor** | Who would do it? | A city transit agency |
| **Intervention** | What exactly would they do? | Publish real-time bus crowding levels in its trip-planning app |
| **Problem** | Which concrete problem does it address, for whom? | Peak-hour overcrowding on high-frequency routes |
| **Combination** | Which part comes from A, and which from B? | A: travellers shift departure time when given information on queues (behavioural economics paper). B: automatic passenger counters give load estimates (transport operations paper). |

Each use case also states:
- **Evidence behind it.** The papers for A and B, and what each contributes, with the same source-accuracy check as Study 1.
- **Smallest real-world trial.** What a pilot would look like, and how long it would take.
- **Failure condition.** What result in a pilot would show it doesn't work.
- **Preconditions.** Data, regulation, cost or infrastructure it needs.

**How C differs from a Study 1 hypothesis.** A hypothesis says "X is associated with Y" and is tested with data. A use case says "actor Z does W to solve problem Q", and is tested by doing it. One hypothesis can support several use cases, and a use case can be worth trying even when its mechanism is only partly understood.

## Outcomes: proposed, piloted, adopted
These three outcomes are tracked separately and never merged into one score.

| Level | Evidence required | Typical sources |
|---|---|---|
| **Proposed** | A document after the cutoff recommends or plans this intervention for this kind of problem | Policy reports, consultations, white papers, industry reports |
| **Piloted** | A documented trial or pilot by a named actor | Agency reports, evaluation reports, trial registries, news coverage of a launch |
| **Adopted** | Evidence that the intervention is in routine use beyond a pilot | Operating reports, procurement records, budgets, product documentation |

**Lead vs outcome.** A document that mentions both ingredients, or the intervention in general terms, is a **lead**, not an outcome. An outcome needs the document to show **this actor doing this intervention**, and the intervention must actually combine the A part and the B part. For example, "real-time crowding information" in an app does count only if it is derived from passenger counting. A crowding report without counting data does not.

## How Study 1's safeguards carry over
- **Time split.** Generation uses only pre-cutoff papers. Outcomes are searched after the cutoff. Study 1 used 2019 as the cutoff; Study 2 may need a later one (for example 2017), because adoption takes longer than publication. Window: cutoff year +1 to +5.
- **Blinding.** Outcome judges see the use case without the method that produced it, mixed with control use cases.
- **Known-outcome controls.** Use cases with documented pilots or adoptions after the cutoff, built from real deployments, test whether the outcome search can find adoption evidence at all.
- **Independent search audit.** A second searcher, without access to the pipeline's results, looks for evidence on a sample. Misses are attributed to methods after unblinding.
- **Hindsight diagnostic.** The model knows about real deployments after the cutoff. A no-context probe ("has actor type Z done W?") measures this.
- **Comparisons.** The same comparisons as Study 1: graph paths vs retrieval + brainstorm, the path-ranking ablation, and a popularity baseline. All share one writer template, now producing use cases instead of hypotheses.

## Evidence sources: what this environment can reach
| Source | Reachable here? | Notes |
|---|---|---|
| OpenAlex (includes some reports, grey literature, book chapters) | **Yes** | Good for proposals and evaluation reports, weak for deployments |
| General web pages (agency sites, news) | **Uncertain** | Depends on the environment's network policy; web search tools may be available but are not set up for reproducible, dated retrieval |
| Patent databases (for product-type use cases), such as PatentsView, Lens or Google Patents | **No, needs access** | Need an API key or cloud project. Filing date gives a clean timeline. Patents show intent, not adoption. |
| Policy-document indexes, such as Overton | **No, needs a subscription** | The best single source for "proposed" in policy |
| Trial and evaluation registries for public programmes | **Partly** | Field-dependent; transport has few formal registries |
| Procurement and budget records | **No** | National portals vary; would need a scoped country list |

The best path for transport and urban policy, given these limits: OpenAlex for proposals and evaluations, plus a scoped web search of named agencies' publications, saved as dated snapshots. For product-type use cases, patents would need an API key.

## Open decisions for you
1. **Who the actors are:** public agencies (policy), firms (products and operations), or both. This decides the evidence sources.
2. **Which cutoff year:** 2017 gives more time for adoption to happen; 2019 reuses the Study 1 corpus as is.
3. **Which fields:** transport plus urban policy is the most traceable (public agencies publish a lot). Economics use cases are mostly policy, which is harder to attribute to one actor.
4. **Which sources to fund or connect:** a patent API key, a policy-document index, or a web snapshot process.
5. **What counts as success:** for example, the share of shortlisted use cases reaching at least **piloted** within 5 years, with **proposed** and **adopted** reported alongside.

## How it depends on Study 1
Study 2 reuses the corpus, graph, retrieval and evaluation machinery. The parts that change are the writer prompt (use cases instead of hypotheses), the outcome search (practice evidence instead of papers) and the matching rule (actor + intervention + combination). Study 1's pilot shows which parts of the literature search can be trusted. Its known-match controls are the template for Study 2's known-outcome controls.
