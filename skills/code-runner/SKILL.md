---
name: code-runner
description: Run Python code in an isolated OpenSandbox container, for data analysis of files in /workspace, checking calculations, or testing a snippet. Use whenever a task needs code to be executed rather than reasoned about.
license: Apache-2.0
compatibility: Requires the OpenSandbox MCP server (sandbox_* tools).
metadata:
  layer: action
---

# Code runner (OpenSandbox)

Code never runs in the agent or on the host. It runs in a throwaway OpenSandbox container that
cannot see `/workspace`, so you copy inputs in and results out.

## Steps

1. **Create a sandbox**: call `sandbox_sandbox_create` with image `python:3.12-slim` and
   `timeout_seconds` 600. Keep the returned `sandbox_id`.
2. **Copy inputs in**: read each input file from `/workspace` with `fs_read_text_file`, then
   write it into the sandbox under `/tmp/work/` with `sandbox_file_write`.
3. **Copy code in**: for CSV analysis, read `scripts/analyze_csv.py` with `read_skill_file` and
   write it to `/tmp/work/analyze_csv.py`. For other tasks write your own script to
   `/tmp/work/main.py`; standard library only unless you first run `pip install`.
4. **Run**: call `sandbox_command_run`, e.g.
   `python /tmp/work/analyze_csv.py /tmp/work/data.csv --group-by region --metric revenue`.
   Check the exit code and stderr; fix and re-run at most twice.
5. **Save results** (when the user wants a report): write Markdown with `fs_write_file` to
   `/workspace/reports/<name>.md`.
6. **Always clean up**: kill the sandbox with `sandbox_sandbox_kill`, even after errors.
7. **Reply** with the numbers that answer the question, and say they were computed in the sandbox.

## Rules

- Never paste secrets into the sandbox.
- Do not report numbers you did not get from an actual run.
