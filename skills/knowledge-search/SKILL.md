---
name: knowledge-search
description: Answer questions from the team's internal docs (runbooks, architecture notes, ADRs, onboarding) indexed in Milvus. Use for "how do we...", "what does our doc say about...", incident or runbook questions.
license: Apache-2.0
compatibility: Requires the `rag` profile (Milvus + Milvus MCP server, milvus_* tools).
metadata:
  layer: context
---

# Knowledge search (Milvus)

`/workspace/docs` is indexed into the Milvus collection `workspace_docs` with fields `text`
(a chunk of a document) and `source` (its path). Milvus computes BM25 sparse vectors from the
text, so you search with plain words.

## Steps

1. If no `milvus_*` tools are available, say the `rag` profile is off and fall back to
   `fs_search_files` + `fs_read_text_file` under `/workspace/docs`.
2. Call `milvus_milvus_text_search` with `collection_name` `workspace_docs`, a keyword-rich
   `query_text` (product names, error strings, component names), `limit` 5 and
   `output_fields` `["text", "source"]`.
3. If results are weak, rephrase with synonyms and search once more.
4. When a chunk is relevant but incomplete, open the full file with `fs_read_text_file`
   (`/workspace/<source>`).
5. Answer only from retrieved text. Cite sources as `(docs/<file>.md)`. If the docs don't
   cover it, say so.
