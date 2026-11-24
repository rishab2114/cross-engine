# Alien Space of Science: what we can reuse, what we redevelop

*Inspected 24 Nov 2026: `alejandrohdez00/alien-space-of-science` at `a55d660de75c99afe9e0948781cdb828fe3798eb` (MIT licence, © 2026 Alejandro Hernández Artiles). It is cloned for inspection only, outside the repository; nothing from it has been copied in yet. Paper: arXiv 2603.01092, read in full for the main text and Appendix A.*

## What the repository contains (≈ 7,500 lines of Python)

| Area | Files | Needs an LLM / money? | Verdict for Cross Engine |
|---|---|---|---|
| Coherence model | `generation/model.py` (`CausalTransformerLM`, 143 lines), `train_coherence.py`, `datasets/coherence.py`, `make_datasets.py` (random permutations of each paper's atoms) | No: PyTorch only | **Reuse as is**, retrained on our atoms with a smaller configuration for CPU |
| Availability model | `two_tower_model.py` (set encoder + author MLP, InfoNCE), `train_availability.py`, `make_availability.py` (subset/complement sampler, memory-mapped `rows.bin`/`complements.bin`), `availability_data.py` | No: PyTorch only | **Reuse as is**, retrained on our authors with a smaller configuration |
| Scoring and sampling | `scoring.py` (median of top-m author similarities; z-scored combination), `sample.py` (autoregressive or exhaustive pool, β sweep), `token_mapping.py` | No | **Reuse as is.** Exhaustive enumeration doesn't fit our vocabulary size, so we use sampled or question-restricted pools. |
| Database schema | `crawlers/db/schema.py`: `papers`, `authors`, `paper_authors` (SQLite) | No | **Rebuild** from OpenAlex authorships of our corpus |
| Atomization | `atomization/pipeline.py`, `stages/extract_blog.py`, `extract_ideas.py`, `rate_ideas.py`, `prompts.py` | **Yes:** Gemini via LiteLLM, reading PDFs | **Don't run** (paid). Free replacement below. |
| Clustering | `atomization/stages/cluster_atoms.py` (BGE embeddings + UMAP + HDBSCAN; Gemini writes cluster names), `reassign_noise.py` | Partly: naming uses an LLM | Reuse the clustering logic idea; name clusters by their top keywords instead of an LLM |
| Reconstruction | `generation/reconstruct.py`, `reconstruct_cli.py` (LiteLLM) | **Yes** (paid) | Replace with our own job-file subagent runner (plan usage, no money) when needed |
| Baselines | `generation/baselines/selection.py` | No | Reuse to check random and frequency baselines |

**Released artifacts** (Hugging Face `alejandrohdez/alien-models`, checked reachable): `coherence_model/`, `availability_model/` (with a 39,791 × 512 author bank) and a manifest, about 358 MB. These are trained on **LLM-research papers only**: right for a reproduction smoke test, wrong for economics and transport.

## Why we can't use their atoms directly
- Their 273 atoms describe LLM methods. None of our corpus maps onto them.
- Building atoms their way means running an LLM over full PDFs: 16k papers through Gemini in the original. That conflicts with free mode.

## Free redevelopment: "Alien-lite" for economics and transport

| Step | What we build | Reuses | Cost |
|---|---|---|---|
| 1. Atoms | **Keyword-cluster atoms.** Our ~15k OpenAlex keyword vocabulary is clustered into ~300–600 atoms using the existing LSA concept centroids (`engine.C`) and k-means or HDBSCAN. Each atom is named by its top keywords; no LLM. Raw keywords are kept as a second, finer-grained variant. | Our `engine.py` centroids; the upstream clustering idea | CPU |
| 2. Authors | **Authorships for the 60k corpus papers** from OpenAlex. Batches of 100 ids per list request means about 600 requests ≈ **$0.06**, inside the free tier and stopped by our $0.90/day cap. Written into the upstream SQLite schema. | `crawlers/db/schema.py` | ≈ $0.06 |
| 3. Datasets | Export `clusters_80.json`-format assignments (paper → atoms, with cluster −1 for none), then run upstream `make_datasets.py` and `make_availability.py` unchanged | upstream builders | CPU |
| 4. Models | Train `CausalTransformerLM` and `TwoTowerAvailabilityModel` with **CPU-sized settings** (for example 4 layers, d = 256, a capped per-author budget). Training logs record the settings. | upstream training scripts | CPU, hours |
| 5. Temporal test | **Replicate the paper's Fig. 3 in a new domain.** Everything is frozen on 2000–2019. Map a seeded sample of 2020–2024 economics and transport papers (keywords + authors, list requests) into the same atoms. Recovery@K of their atom pairs and triples is compared against chance, including the *strictly novel* ones, for each β. **Baselines:** coherence alone (β = 0), a **rarity** score (low frequency), a **popularity** score, and our G-path score. | upstream `scoring.py` and `sample.py` | ≈ $0.05 |
| 6. Smoke test | Run the released artifacts: `alien.py sample --top-k 20` on CPU, with checksums recorded | upstream as is | free |

**The question this answers** (a precondition for both `TRAINING_EXTENSION_PLAN.md` and Cross Engine's novelty filter): *in a less dense field than LLM research, does a learned author-availability score add anything beyond simple rarity in predicting which combinations appear next?*
- **If yes:** availability replaces our weak "zero co-occurrence" filter, and the training study's arm D is worth running.
- **If no:** that is a publishable negative replication, and the training plan should use rarity (arm C).

## Differences from the paper, stated up front
- **Atoms:** keyword clusters, not LLM-distilled method statements. They are coarser and less mechanistic, and they come from OpenAlex's current classifier, not a 2019-era one.
- **Authors:** OpenAlex author IDs, which carry their own disambiguation errors. Upstream used OpenReview and DBLP IDs.
- **Scale:** smaller models trained on CPU. The paper used 42.8M parameters for coherence and 4 A100 GPUs for availability.
- **Retrospective only:** a 5-year window (2020–2024) rather than their 1-year one.

## Integration plan (once approved)
- Vendor only the files we use under `third_party/alien_space/`, with `LICENSE`, the upstream commit hash and a `MODIFICATIONS.md`.
- Write a thin adapter `src/discovery/alien_adapt/` with `atoms.py`, `authors.py`, `export.py`, `train.py` and `temporal_eval.py`.
- Preregister the Alien-lite study (new amendment) before any temporal-recovery number is computed.
