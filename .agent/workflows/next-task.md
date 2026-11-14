---
description: Resume work — pick and complete the next unticked task, then keep going
---

1. Read `AGENTS.md` (fork block), `.agent/rules/deeptutor-fork.md` and `.agent/PROGRESS.md`.
2. In `.agent/08-TASKS.md`, find the first task that is not ticked `[x]`. Mark it `— in progress: <your name>`.
3. Read the docs and source files the task references.
4. Implement it and write the tests it names.
5. Run the task's tests, `pytest tests/services/llm -q` and `ruff check` on touched files (plus `web` lint + build when `web/` changed). Check the task's AC (in a real browser for UI ACs). Fix until everything passes.
6. Check "Docs follow code" and fork markers (rules). Update `FORK_NOTICE.md`. Tick the task with a one-line note, update PROGRESS.md ("Now" + a session-log entry), **commit locally. Never push.**
7. Continue with the next task unless Rony said to stop or you are blocked on a human step. At the very end, follow V6.
