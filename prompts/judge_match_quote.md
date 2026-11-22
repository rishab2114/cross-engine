You are checking whether published papers explicitly investigated a relationship between two concepts. Work only from the papers given. Do not search the web or any database, and do not use tools other than reading this job and writing your answer.

MATCHING RULE (strict, quote-anchored)
A paper is a MATCH only if you can copy an exact passage of at most 30 words from its title or abstract that STATES a relationship, effect, association, mechanism or method linking concept A and concept B. For example, the passage says one affects, predicts, explains, moderates or is used to measure, model or change the other. Synonyms and close variants of a concept count as the concept.

It is NOT a match if:
- both concepts appear but no passage links them (they are listed together, appear in separate sentences about different things, or serve only as background or setting)
- the link has to be inferred rather than read from the text

If you cannot quote such a passage, the answer is no match.

For each item, look at the candidate papers in each window separately and decide:
- "match": true or false
- "paper_id": the id of the best matching paper (or null)
- "quote": the exact passage (at most 30 words) that states the A–B link (required when match is true, otherwise null)
- "reason": for no match, one of "mention_only", "not_both", "no_link_stated"

ITEMS
{items}

OUTPUT
Return only a JSON object: {{"judgments": [{{"item_id": ..., "window": "pre2020" or "post2019", "match": ..., "paper_id": ..., "quote": ..., "reason": ...}}, ...]}} with one judgment per item per window that has candidates.
