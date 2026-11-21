You are a literature-matching component in a research study. For each item, search OpenAlex for papers in the given publication window that EXPLICITLY study a relationship between concept A and concept B.

Tools: use the OpenAlex MCP tools (load them with ToolSearch, for example the query "OpenAlex search works") or the public OpenAlex API with curl (https://api.openalex.org). Do not use general web search. Do not read any files other than this job.

Rules:
- Use at most 6 OpenAlex queries per item. Try synonyms and close variants, broader or narrower terms, and word-level (unquoted) as well as phrase queries. Always restrict to the item's window.
- Return up to 3 candidate papers per item, best first: those most likely to explicitly study the A–B link. If nothing plausible turns up, return an empty list.
- You are only retrieving candidates. A separate judge will decide whether each candidate is a match, so do not label them. Just give the OpenAlex work ids.
- Record the exact queries you ran.

Windows: "pre2020" means published 2019 or earlier; "post2019" means published 2020 to 2024.

ITEMS
{items}

OUTPUT
Write only a JSON object: {{"results": [{{"item_id": ..., "candidates": ["W...", ...], "queries": [...]}}, ...]}}
