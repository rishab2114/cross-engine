You are executing pre-written LLM jobs for a research study. Each job is a JSON file whose "prompt" field is a complete, self-contained task.

For each job file listed below, in order:
1. Read the job file and its "prompt" field.
2. Carry out that prompt exactly as written, as if it had been sent to you as a user message. Use only the text in the prompt and your own reasoning.
3. Write your answer, which is only the JSON object the prompt asks for and nothing else, to the output path given for that job.

Strict rules:
- Do NOT use web search, web fetch, OpenAlex or any other database or MCP tool, or run any code. Use only the Read tool on the listed job files and the Write tool for the output files.
- Do NOT read any other files in the repository (other jobs, outputs, results, data or code). Each job must be answered independently from its own prompt.
- Do not skip items or shorten the requested number of ideas or judgments.
- After writing all outputs, reply with one short line: the output paths you wrote.

JOBS (job file -> output file)
{jobs}
