You are checking whether published papers explicitly investigated a relationship between two concepts. Work only from the papers given. Do not search the web or any database, and do not use tools other than reading this job and writing your answer.

MATCHING RULE (fixed before the study)
A paper counts as a MATCH only if its title or abstract shows that it explicitly studies a relationship, effect, association, mechanism or method linking concept A and concept B: for example, it estimates the effect of one on the other, models how they interact, or applies a method named by one to the problem named by the other. A paper does NOT count if it merely mentions both concepts, lists them among many topics, or uses one only as background. Synonyms and close variants of a concept count as the concept.

For each item, look at the candidate papers in each window separately and decide:
- "match": true or false
- "paper_id": the id of the best matching paper (or null)
- "evidence": a short quote or paraphrase (max 25 words) from that paper's title/abstract showing the link (or null)
- "relation": for a match, one of "supports", "challenges", "tests_mixed", "unclear" describing what the paper finds about the A–B link

ITEMS
{items}

OUTPUT
Return only a JSON object: {{"judgments": [{{"item_id": ..., "window": "pre2020" or "post2019", "match": ..., "paper_id": ..., "evidence": ..., "relation": ...}}, ...]}} with one judgment per item per window that has candidates.
