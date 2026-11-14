# PROGRESS — the fork's memory

> Fork addition. **Every agent reads this first and updates it before ending any session.**
> `08-TASKS.md` is the *plan*. This file is the *state*.

---

## Now
| | |
|---|---|
| **Phase** | Course workspaces (V7+) in progress |
| **Next task** | V11 instructions panel, V13 YouTube finder (agy running), then V14, V15 |
| **Blocked on** | — |
| **Last updated** | 2026-11-14 by Claude (orchestrating agy) |

## Human steps
Things only Rony can do. Agents add to this list; Rony ticks them.
- [ ] Before the first goal: run `/project-config` in Antigravity and clear its ❌ list.
- [ ] **Pin `agy` to the spare Google AI Pro account** (once, and again whenever you switch back). Close Antigravity first, because the switcher force-closes it:
  1. `cd C:\Users\Asus\AntigravitySwitch` → `.\ag.cmd use <spare>` (e.g. `jio2`).
  2. Check which account `agy` now uses: run `agy` in a terminal and look at the account shown at start-up or in its settings/`/` menu, or check the **usage/quota page of the spare account** after one `agy -p "hi" --output-format stream-json` call.
  3. Write the result under "Environment facts" → *agy account*.
  - Why: planning found only **one** Google login store on this PC (Credential Manager `gemini:antigravity` + `%APPDATA%\Antigravity\credential-user-scope`), which is exactly what the switcher swaps, and `agy` keeps no login of its own. So `agy` almost certainly follows the switcher. That means DeepTutor and the Antigravity desktop app always use **the same** account at the same time. While DeepTutor runs on the spare account, your desktop Antigravity coding is on the spare account too. Switch back with `.\ag.cmd use <main>` when you're done studying. *(Not proven by a behaviour test yet: running the switch would have closed your open Antigravity.)*
- [ ] Optional, for embeddings: create a free API key at Google AI Studio (on any Google account) and paste it in DeepTutor → Settings → Embedding → Gemini. Or install Ollama and pull `nomic-embed-text`. Needed for V5 AC 6.
- [ ] When the build is done: start DeepTutor, pick Antigravity in Settings, and study one CN chapter with it.

## Environment facts (no secrets here!)
| Item | Value |
|---|---|
| Repo | `D:\Projects\DeepTutor`, branch `main`, remote `upstream` only (HKUDS/DeepTutor @ `60fb3bdfd`, 2026-11-06, v1.7.2) |
| agy | 1.5.3 at `C:\Users\Asus\AppData\Local\agy\bin\agy` (ACP server reports 1.5.8) |
| agy data dir | `%USERPROFILE%\.gemini\antigravity-cli\` (each ACP/print session saves a conversation `.db` here) |
| agy account | — (human step above) |
| Python | 3.13.5 (system). Venv: — |
| Node / npm | — |
| Dev URLs | — |

## Measured (spike, 2026-11-14)
| Case | Result |
|---|---|
| ACP `initialize` / `session/new` | 0.9 s / 4.5 s |
| Turn latency (Flash Low–High) | 5–17 s; 120-word answer 9.8 s, first chunk at 8.2 s |
| Input tokens per turn | ~18.8–20.5k (fixed Antigravity overhead, not reducible) |
| Context across turns | yes |
| Print mode `-p` text, piped | prints nothing (bug), so never use it |
| Print mode `-p` stream-json | works, ~41 s |

## Decisions made during the build
Agents append one line per choice the docs didn't cover (newest last). If it changes a doc, update the doc too.
- 2026-11-14: Planning. See `AGENTS.md` fork block, "Key decisions".
- 2026-11-14: Course workspaces: exam groups are plain folders `exams/<slug>/EXAM.md` in the course workspace (no DB), so the existing workspace tools see them. Recorded in 10.
- 2026-11-14: No custom checklist card: `ask_user` (4×8 multi-select) is enough for a CT prerequisite list; checked live.
- 2026-11-14: Uploads keep only the file name of the client path (`../../x` → `x`); a bad `folder` is still rejected.
- 2026-11-14: Builds run `agy -p … --mode auto --sandbox` (accept-edits denies shell commands and ends the print turn). Claude-model quota ran out after one run; Gemini 3.8 Flash High used after that. agy print runs often hang or lose the stream on this network, so a watchdog runner restarts/resumes them.

## Session log
Newest at the bottom. One entry per task. Keep entries short.

```
### YYYY-MM-DD HH:MM — <agent> — <task ID>
Did: …
Tests: ruff ✅ unit ✅ (N passed) live ✅/skipped web build ✅/n.a.
Commits: … (local, not pushed)
Problems / surprises: …
Next: …
```

### 2026-11-14 — Claude (planning) — planning
Did: cloned HKUDS/DeepTutor (remote `upstream`), ran the `agy acp` spike (handshake, model switch, 3-turn context, streaming, token use, saved conversations), wrote the fork block in `AGENTS.md`, `CLAUDE.md`, `FORK_NOTICE.md` and the `.agent/` pack. Nothing committed.
Next: Rony runs `/project-config`, then the goal. Antigravity starts at V0.

### 2026-11-14 — Claude (orchestrator) + agy — V7–V10, V12
Did: plan (10-COURSE-WORKSPACES, V7–V15). V7 exam-groups backend + `/api/courses`; V8 exam-prep skill + `exam_groups` tool; V9 note folder tree tools; V10 Courses page; V12 course instructions in quiz/research prompts. Review fixes: exam-group id confinement (`..` could reach the workspace root), upload read cap, unrelated CitationManager change removed, sidebar link moved to the rendered shelf.
Tests: tests/fork 98 ✅, notes/co_writer/capabilities/tools/question/research suites ✅, tsc ✅, eslint 0 errors (i18n warnings). tests/modules failures are environmental (app running / WinError 87).
Live: Courses page, group create/topics/upload/tree in the browser ✅; chat "I have ZZ Test group…" → read_skill exam-prep → exam_groups → workspace_read → ask_user prerequisite checklist ✅.
Problems: "Study for this exam" prefill is lost in dev mode (React StrictMode double effect, same for upstream's Settings hand-off); check in the production build.
