# DeepTutor fork — always-on rules

If a rule conflicts with a task description, the rule wins. Stop and flag it in "Questions for the human" in `08-TASKS.md`.

## Workflow
- Start every session by reading `AGENTS.md` and `.agent/PROGRESS.md`.
- Pick work only from `.agent/08-TASKS.md`, in order, one task at a time. Mark it `— in progress: <agent>` when you start.
- Don't invent features outside `01-PRODUCT.md`. If something is missing or contradictory, choose the simpler option, note it in PROGRESS.md "Decisions made during the build", and continue.
- Definition of done for every task:
  - The tests the task names pass, plus `pytest tests/services/llm -q`, plus `ruff check` on every Python file you touched.
  - The task's acceptance criteria (AC) pass. UI ACs are checked in a real browser.
  - No `print` debugging left in `deeptutor/` (use `logging`), no commented-out code.
  - Task ticked `[x]` with a one-line note. PROGRESS.md updated ("Now" table + a session-log entry). **Committed locally** with a conventional message (`feat:`, `fix:`, `test:`, `chore:`, `docs:`).
  - **Docs updated** ("Docs follow code" below).
- Commit after every task. **Push to `origin` (public fork `RHRONY05/DeepTutor`) only when Rony asks.** Never push to `upstream`, never add other remotes or repos.
- Before ending any session: update PROGRESS.md.

## Upstream-friendly changes (this is a long-lived fork)
- Prefer **new files**. Touch upstream files only where `02-ARCHITECTURE.md` lists them, with the smallest possible edit.
- Every modified upstream file gets one header line `# Modified in the RH.RONY fork (Apache-2.0 §4b): <what>` (`// …` in TS/TSX). Put it on the first line, or right after a shebang or a `"use client"` directive if the file has one. Every fork edit inside it sits between `# fork(antigravity_acp) start` / `# fork(antigravity_acp) end`.
- Every new file starts with `# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.`
- Update `FORK_NOTICE.md` whenever you add or modify a file.
- Never reformat, rename or reorder upstream code you don't need to change. Never change `LICENSE`.
- Don't change upstream behaviour for other providers. The upstream test suite must not get new failures.

## Antigravity safety (from 07 §5, non-negotiable)
- Only the official, unmodified `agy` binary from PATH, started as `agy acp --sandbox --disable-telemetry` in an empty temp dir.
- Never `--dangerously-skip-permissions`. Always deny permission requests, refuse fs/terminal requests.
- Never read, copy or log Google/Antigravity credentials (`gemini:antigravity` in Windows Credential Manager, `credential-user-scope`, anything in `.gemini`). Never call Google endpoints directly. Never run `ag.cmd` or the account switcher.
- Live tests use `gemini-3.8-flash-low` and as few prompts as possible: they spend Rony's real quota.
- Claude side: only the built-in `claude_code` provider (Agent SDK → official CLI). Never read Claude tokens or set `CLAUDE_CODE_OAUTH_TOKEN`.

## Docs follow code
The `.agent/` pack must describe the code **as it is**.
- Any change to behaviour, files, settings or tests updates the owning doc **in the same commit**:

  | You changed | Update |
  |---|---|
  | scope, a limit, a user-visible behaviour | `01-PRODUCT.md` |
  | a file, dependency, wiring point, setting | `02-ARCHITECTURE.md` + `FORK_NOTICE.md` |
  | ACP protocol handling, sessions, tool JSON, safety, errors, models | `07-ACP-PROVIDER.md` (and its test fixtures) |
  | a test file or case | `09-TESTING.md` |
  | a decision the docs didn't cover | PROGRESS.md "Decisions" **and** the doc above |

- A change made outside a task gets one line under "Changes outside tasks" in `08-TASKS.md`.
- Edit docs in place so they read as the current truth. When unsure whether docs drifted, run `/sync-docs`.

## Code style
- Python: follow upstream (`ruff` config in `pyproject.toml`), type hints, `from __future__ import annotations`, `logging.getLogger(__name__)`.
- Pure logic (`parse_tool_reply`, prompt building, usage mapping, `agy models` parsing) lives in plain functions with unit tests.
- No new dependencies. Ask in "Questions for the human" if one seems needed.
- Windows first: resolve `agy` with `shutil.which`, use `asyncio.create_subprocess_exec` (never `shell=True`), send long text over stdin (never on the command line).

## Quality bar
- Every failure reaches the user as a friendly message (07 §6), never a stack trace. Nothing fails silently: log it.
- A stopped or timed-out turn never leaves a stuck session: the next message works.
