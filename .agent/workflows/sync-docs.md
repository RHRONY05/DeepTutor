---
description: Audit the .agent/ docs and FORK_NOTICE.md against the code and fix every place where they disagree
---

Use when a session starts after many small fixes, after merging upstream, or when Rony asks.

1. Read `AGENTS.md`, `.agent/rules/deeptutor-fork.md` ("Docs follow code") and `.agent/PROGRESS.md`.
2. Find what changed: `git log --oneline` since the last `docs: sync` commit (or since the start), every line under "Changes outside tasks" in `08-TASKS.md`, every "Decisions" line in PROGRESS.md, and `git diff upstream/main --stat`.
3. Compare:
   - **Files and wiring:** `git diff upstream/main --stat` vs `02-ARCHITECTURE.md` and the `FORK_NOTICE.md` table. Every modified upstream file has its header line and `fork(antigravity_acp)` markers.
   - **Provider logic:** `antigravity_acp_provider.py` / `acp_client.py` vs `07-ACP-PROVIDER.md` (spawn args, session pool size, prompt format, tool JSON protocol, safety handling, error texts, models, usage mapping).
   - **Tests:** `tests/services/llm/test_antigravity_acp_provider.py`, `tests/integration/test_antigravity_acp_live.py` vs `09-TESTING.md` (the `parse_tool_reply` worked examples must match the test fixtures).
   - **Scope:** `01-PRODUCT.md` stories and "Out of scope" vs what the code does.
4. Classify each difference: **doc is stale** → edit the doc in place. **Code is wrong** → report it as a bug (fix if small). **Unclear** → "Questions for the human" in `08-TASKS.md`.
5. After an upstream merge: re-run `pytest tests/services/llm -q`, check that the fork markers survived, and note the merged upstream commit in PROGRESS "Environment facts".
6. Commit locally as `docs: sync docs with code (<n> fixes)` with a PROGRESS session-log entry. Never push.
7. Report to Rony: a table `doc · what was stale · now says`, then bugs, then open questions.
