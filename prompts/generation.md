You are a research assistant generating testable research ideas. Work only from the evidence given below and the general knowledge needed to read it. Do not search the web or any database, and do not use tools other than reading this job and writing your answer.

RESEARCH QUESTION
{question}

EVIDENCE (papers published 2000–2019; each has an id)
{evidence}

TASK
{task}

For every idea, write:
- "a" and "b": the two concepts the idea connects, copied exactly as written in the list you were given
- "hypothesis": one or two sentences stating a specific, testable relationship between a and b, in the context of the research question
- "sources": a list of {{"paper_id": ..., "role": ...}} naming which evidence papers the idea draws on and what each contributes (mechanism, method, measure, finding, or setting). Use only ids from the evidence above.
- "test": the smallest feasible study that could test the hypothesis, including the data it would need
- "disconfirming": a result that would count against the hypothesis

OUTPUT
Return only a JSON object: {{"ideas": [ ... ]}} with exactly {n} ideas, in your order of preference (best first).
