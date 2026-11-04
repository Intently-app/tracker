# Hub

One task list for every project on every GitHub account. The board is
[Hub](https://github.com/users/Fa-d/projects/2).

- **Pick tasks for an agent:** add the label `agent:ready`. Then, in any agent CLI, say
  "work the hub queue" (the agent follows `AGENTS.md`).
- **See what's left:** the board's views, or the weekly digest issue (every Monday).
- **Prioritise and plan quarters:** either ask any agent CLI to "triage the hub" (rules in AGENTS.md),
  or run the "Triage" workflow (Actions tab) with any OpenAI-compatible LLM. Set the repo secrets
  `LLM_BASE_URL` and `LLM_API_KEY` once (a free Gemini key works:
  `https://generativelanguage.googleapis.com/v1beta/openai`, model `gemini-2.5-flash`). It posts
  suggested priorities and quarters as an issue and changes nothing.
- **Add a task or bug:** New issue → Task or Bug.

The rules every agent follows are in [AGENTS.md](AGENTS.md).
