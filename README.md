# Cross-Field Research Discovery Engine

A research discovery engine and a preregistered benchmark testing whether following connections across papers (graph paths) produces better research ideas than retrieval followed by AI brainstorming.

**Status (22 Nov 2026):**
- The pilot and the matcher validation (Amendment 4) are complete.
- **No matcher passed.** Every candidate shares a judge with 84% precision on hard negatives, below the 90% gate. The holdout stays sealed and **the main run is on hold.**
- The lead result so far is methodological: retrospective scores, and even the direction of a method comparison, change with the matcher.

See [`results/MATCHER_VALIDATION.md`](results/MATCHER_VALIDATION.md) and [`results/MEASUREMENT_SENSITIVITY.md`](results/MEASUREMENT_SENSITIVITY.md).

## Key documents
- [`PROPOSAL.md`](PROPOSAL.md): research proposal (v3)
- [`prereg/PREREGISTRATION.md`](prereg/PREREGISTRATION.md): frozen design, plus Amendments 1–4a
- [`results/PILOT_RESULTS.md`](results/PILOT_RESULTS.md): pilot results, search validation, cost and power
- [`results/MATCHER_VALIDATION.md`](results/MATCHER_VALIDATION.md): Amendment 4 matcher comparison, selection decision, CIs, cost projection
- [`results/MEASUREMENT_SENSITIVITY.md`](results/MEASUREMENT_SENSITIVITY.md): how method estimates change with the matcher; pair-level vs hypothesis-level matching
- [`results/holdout_human_sheet.csv`](results/holdout_human_sheet.csv): blind sheet for human adjudication
- [`docs/IMPROVEMENTS_AND_PAPER_PLAN.md`](docs/IMPROVEMENTS_AND_PAPER_PLAN.md): review passes, improvements and path to a paper
- [`STUDY2_USE_CASES.md`](STUDY2_USE_CASES.md): Study 2 design, assumption-aware evidence-path transfer in urban mobility (not run; gated on reviewer recruitment)

## Layout
- `src/discovery/`: corpus (`corpus.py`, `openalex.py`), graph (`graph.py`), retrieval (`retrieval.py`), methods (`methods/candidates.py`), study pipeline (`study.py`), controls (`controls.py`), search audit (`search_audit.py`), analysis (`analysis.py`), power (`power.py`), prototype CLI (`cli.py`)
- `prompts/`: frozen prompt templates (hashes in `prereg/frozen_inputs*.json`)
- `jobs/`: LLM job prompts and outputs. Metadata lives in the `*_meta/` sidecars, which runners never read. Superseded rounds are in `jobs/superseded/`.
- `data/`: corpus manifest and IDs, questions, ideas, labels, search candidates (the full corpus and engine cache are gitignored)

## Reproduce
```bash
pip install -e . pytest
```
```bash
python -m discovery.corpus                 # rebuild the 60k-paper corpus (OpenAlex, fixed seed)
```
```bash
python -c "from discovery import engine; engine.build()"
```
```bash
python -m discovery.study ingest --set pilot && python -m discovery.study label --set pilot
```
```bash
python -m discovery.analysis --set pilot
```
```bash
pytest -q
```
LLM steps write job files when no `ANTHROPIC_API_KEY` is set. With a key set, `llm.run` calls the API directly.

## Prototype
```bash
discover guided --question "How could ride-hailing affect transit ridership?" --method G
```
```bash
discover explore --concepts "congestion pricing" "air quality"
```
```bash
discover export --ideas results/shortlist.json --out shortlist.md
```
