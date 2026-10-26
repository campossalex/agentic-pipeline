---
name: repo-onboarding
description: Explore a code repository in /workspace and write an AGENTS.md for it (build, test, layout, conventions). Use when asked to onboard, document, explain, or "get to know" a repo or project.
license: Apache-2.0
metadata:
  layer: context
---

# Repository onboarding

Produce an accurate `AGENTS.md` at the root of the target repository so that any coding agent
(and human) can work in it. Only write what you verified from files or git history.

## Steps

1. **Existing guidance.** Call `load_project_context` with the repo path. If an `AGENTS.md`
   already exists there, you will update it rather than replace it.
2. **Layout.** Use `fs_directory_tree` (or `fs_list_directory`) on the repo. Skip `.git`,
   virtualenvs, `node_modules`, build output.
3. **Build and test commands.** Read the manifest files that exist: `pyproject.toml`,
   `requirements*.txt`, `package.json`, `Makefile`, `Dockerfile`, CI config. Extract the exact
   install, run, lint and test commands. Do not invent commands that no file supports.
4. **Code conventions.** Read 2–3 representative source files and one test file. Note language
   version, frameworks, naming, error handling, how tests are structured.
5. **History.** Call `git_git_log` with `repo_path` set to the repo directory and `max_count` 10
   for recent activity and commit style.
6. **Write the file.** Read `references/agents-md-template.md` with `read_skill_file`, fill it,
   and save it with `fs_write_file` to `<repo>/AGENTS.md`.
7. **Report.** Reply with a short summary and the path written. Mention anything you could not
   verify (for example, no test command found).

## Rules

- Keep AGENTS.md under ~80 lines; it is loaded into every agent's context.
- Commands go in fenced code blocks, one per line, runnable from the repo root.
- Never include secrets, tokens or personal data found in files.
