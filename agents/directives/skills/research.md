## Workflow

1. Formulate a focused initial search query from the user's question.
2. Call `web_search` with the query.
3. Read the results. If the answer is clear, synthesize and respond.
4. If results are incomplete or ambiguous, refine the query (different angle, not the same words) and call `web_search` once more.
5. Synthesize findings into a concise answer with source links.

## Rules

- Maximum 2 `web_search` calls per research task.
- Never repeat the exact same query — rephrase or narrow.
- Always include source URLs in the final answer.
- If results conflict, note the disagreement explicitly.
- Prefer recent sources over older ones.
- If no useful results found after 2 attempts, say so honestly and suggest the user try a more specific question.
