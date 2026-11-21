You are building a reference label set for evaluating a literature-matching system. Work only from the text given. Do not search the web or any database, and do not use tools other than reading this job and writing your answer.

For each item you get two concepts, A and B, and one paper (title and abstract). Decide which label fits:
- "explicit": the title or abstract shows the paper EXPLICITLY studies a relationship, effect, association, mechanism or method linking A and B. For example, it estimates the effect of one on the other, models their interaction, or applies a method named by one to the problem named by the other. Synonyms and close variants of a concept count as the concept.
- "mention_only": the paper refers to both A and B (or close variants) but does not study a link between them. For example, they appear in a list, as background, or in separate parts of the analysis.
- "not_both": the paper does not meaningfully involve both A and B.
- "unclear": the abstract is too short or ambiguous to decide.

For "explicit", copy the shortest exact phrase (at most 30 words) from the title or abstract that establishes the link. For the other labels, give a one-sentence reason.

ITEMS
{items}

OUTPUT
Return only a JSON object: {{"labels": [{{"item_id": ..., "label": ..., "quote_or_reason": ...}}, ...]}} with one label per item.
