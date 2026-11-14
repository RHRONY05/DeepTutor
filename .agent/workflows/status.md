---
description: Report fork status from PROGRESS.md and the task list
---

1. Read `.agent/PROGRESS.md` and `.agent/08-TASKS.md`.
2. Run `git status`, `git log --oneline -10` and `git log --oneline upstream/main..main | wc -l` (fork commits ahead of upstream).
3. Reply in at most 10 lines: tasks ticked (x / 7), done since the last session-log entry, in progress, next task, blockers, open human steps.
4. Do not change any files.
