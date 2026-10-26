---
name: research-brief
description: Research a topic from one or more web pages and save a cited Markdown brief to /workspace/briefs. Use when asked to research, summarize a URL or article, compare sources, or "write a brief".
license: Apache-2.0
metadata:
  layer: context
---

# Research brief

## Steps

1. **Sources.** Use URLs the user gave. If none were given, ask for them or use well-known
   primary sources (official docs, project sites) and say which ones you chose.
2. **Fetch.** Call `web_fetch` for each URL (use `max_length` 15000; follow up with
   `start_index` if the page is cut off and the rest matters). Fetch at most 5 pages.
3. **Read critically.** Separate facts stated by the source from opinions. Note dates.
4. **Write.** Read `assets/brief-template.md` with `read_skill_file`, fill it, and save it with
   `fs_write_file` to `/workspace/briefs/<kebab-case-topic>.md`.
5. **Reply** with 3–5 key points and the path of the brief.

## Rules

- Every claim in the brief carries a numbered citation `[n]` that maps to the Sources list.
- Paraphrase; quote at most one short sentence per source.
- If a fetch fails, record it under "Gaps" instead of guessing the content.
