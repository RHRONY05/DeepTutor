# 08 — Tasks

Rules: `rules/deeptutor-fork.md`. Work **in order V0 → V6**, one agent, one go. Each task depends on the ones before it.
Mark a task `— in progress: <agent>` when you start, tick `[x]` with a one-line note when done, add a
session-log entry in `PROGRESS.md` after **every** task, **commit locally** (never push), then continue.

```
V0 Preflight ─▶ V1 Env + Claude Code + fork notice ─▶ V2 ACP client + fake agent ─▶ V3 Provider core (text)
                                                                                         │
            V6 Final check + walkthrough ◀─ V5 Settings UI + app check ◀─ V4 Tool calls + wiring
```

---

- [ ] **V0 Preflight**
  - Read `AGENTS.md` (fork block + upstream part), every file in `.agent/`, and `deeptutor/services/llm/provider_core/claude_code_provider.py` + `sdk_bridge.py` + `tests/services/llm/test_claude_code_provider.py`.
  - If PROGRESS.md has no **Builder setup** table, run `/project-config` first. Stop on blocking ❌ items.
  - Check and record versions: `python --version` (3.11–3.14), `node -v` (≥ 20), `npm -v`, `git --version`, `agy --version`, `claude --version`, `git remote -v` (only `upstream`), `git status` (clean except the planning files).
  - **AC:** a preflight table in PROGRESS.md (item · ✅/❌ · note). The planning files are committed as `docs: add fork plan pack for antigravity_acp provider` (local commit, no push).

- [ ] **V1 Environment, Claude Code provider check, fork notice**
  - Create `.venv` and install from source per `02-ARCHITECTURE.md` (incl. `claude-agent-sdk`). Make sure `.venv/` is git-ignored (it is upstream, so check, don't edit).
  - `deeptutor init` with defaults, then `deeptutor start --dev`. Note the URLs in PROGRESS "Environment facts".
  - In the UI: Settings → Providers → add **Claude Code (subscription)** → Sync models → Language model `sonnet`, Task model `haiku`. Send "Reply with exactly: pong" in Chat.
  - `FORK_NOTICE.md` already exists (planning). Check it lists `AGENTS.md`, `CLAUDE.md`, `.agent/`, and keep it current from here on.
  - **Tests:** `pytest tests/services/llm -q` passes on the untouched code (baseline). Record the pass count.
  - **AC:** the app starts. Claude Code chat answers `pong` (if Claude Pro isn't active right now, mark this ⚠️ in PROGRESS and continue, it's not blocking). `FORK_NOTICE.md` exists. Baseline test count recorded (note any tests that already fail upstream).

- [ ] **V2 ACP client + fake agent**
  - `acp_client.py` per 02, and `tests/services/llm/fake_acp_agent.py` per 09 Layer 1.
  - API (suggested): `AcpClient.start(cmd, cwd)`, `await request(method, params, timeout)`, `notify(method, params)`, `on_notification(callback)`, `on_request(handler)` (returns result or raises `AcpMethodError(code, message)`), `await close()`. One reader task, one write lock, pending futures by id. EOF → fail all pending with `AcpProcessExited`.
  - **Tests:** unit tests for the client alone against the fake agent: request/response, notification routing, agent→client request answered, process exit fails pending, close is idempotent.
  - **AC:** `pytest tests/services/llm/test_antigravity_acp_provider.py -q -k client` green. No Antigravity-specific strings in `acp_client.py`.

- [ ] **V3 Provider core: text chat, sessions, streaming, safety**
  - `antigravity_acp_provider.py` per 07 §2, §3 (text only), §5, §6, §7, §8. No tool mode yet: if `tools` are passed, ignore them in this task.
  - `fetch_antigravity_models()`. `scripts/fork/agy_acp_smoke.py` (prints reply, seconds, usage).
  - **Tests:** 09 Layer 1 cases 2–17 and 21. Live: 09 Layer 2 tests 1, 2, 3, 5 (Rony's PC has `agy` signed in, so run them once with `DEEPTUTOR_LIVE_AGY=1`). Record latency and tokens in PROGRESS.
  - Decide system-prompt option A or B with `test_system_prompt_honoured` and record it in PROGRESS "Decisions" and in 07 §3 (edit it so it states the winner).
  - **AC:** `python scripts/fork/agy_acp_smoke.py "Reply with exactly: pong"` prints a reply containing `pong` and a usage line. Live tests 1, 2, 3, 5 pass. All unit tests green. `git grep -n "dangerously-skip-permissions" deeptutor` finds nothing.

- [ ] **V4 Tool calls via JSON + backend wiring**
  - 07 §4 (`parse_tool_reply`, prompt block, buffering, repair turn, fallback).
  - All registry/factory/adapter/capabilities/model-access/`fetch_models` edits from 02 "Modified upstream files" (backend only, not the UI), each with header line + `fork(antigravity_acp)` markers. Update `FORK_NOTICE.md`.
  - **Tests:** 09 Layer 1 cases 1, 18, 19, 20, Layer 3 `test_agentic_adapter_builds`, live Layer 2 test 4. Full `pytest tests/services/llm tests/agents/chat -q` green (no upstream regressions vs the V1 baseline).
  - **AC:** the live tool round-trip test passes. `get_runtime_provider(LLMConfig(binding="antigravity_acp", model="antigravity/gemini-3.8-flash-low", api_key="", provider_name="antigravity_acp"))` returns an `AntigravityAcpProvider`.

- [ ] **V5 Settings UI, model sync, real-app check**
  - `settings.py` (empty base URL allowed + catalog branch) and `ServiceConfigEditor.tsx` (`CLI_LOGIN_BINDINGS`). Any other UI list found by the `claude_code` grep (02). Header lines, markers, `FORK_NOTICE.md`.
  - **Tests:** an API test for the catalog route with `fetch_antigravity_models` monkeypatched (follow the existing settings router tests in `tests/api/`). `web` lint + build pass.
  - **AC (in the real app, desktop browser):**
    1. Settings → Providers → add **Antigravity (Google AI Pro subscription)**: no base URL or API key field is required. "Sync models" lists the three `gemini-3.8-flash-*` models.
    2. Language model = `gemini-3.8-flash-medium`, Task model = `gemini-3.8-flash-low`. In Chat, type "Explain the TCP three-way handshake in 5 lines." → a streamed answer appears. Then "Now explain the second step in more detail." → the answer refers to SYN-ACK (context kept).
    3. Press Stop during a long answer → it stops within ~5 s and the next message works.
    4. Turn on a tool (e.g. web search) and ask "Search the web for what RFC 9293 is." → the tool runs (visible in the Activity panel) and the answer mentions TCP.
    5. Switch Language model back to Claude Code → the next message answers (or a clear Claude login/limit message).
    6. Settings → Embedding: if Rony has added a Gemini key (human step), choose **Gemini** `gemini-embedding-001`, create a knowledge base from one small PDF or markdown file, and ask a question about it → the answer cites it. If no key yet, mark ⚠️ and list it as a human step.
    7. Temporarily rename the PATH lookup (monkeypatch in a test, **not** on the real system) or check the friendly-error unit tests. In the UI, the error text from 07 §6 shows as the assistant reply, not a stack trace.
  - Write the observed latency (first token, total) for AC 2 into PROGRESS.

- [ ] **V6 Final check and handoff**
  - Full `pytest -q` (compare with the V1 baseline: no new failures), `ruff check` on touched files, `web` lint + build.
  - `FORK_NOTICE.md` lists every added/modified file. Every modified upstream file has its header line. `git diff upstream/main --stat` matches the list.
  - Short section in `README.md`? **No.** Put the user-facing setup in `FORK_NOTICE.md` → "Using the subscription providers" (Claude Code, Antigravity, embeddings, how to switch, the account note from PROGRESS).
  - Final message to Rony: what was built, test results, measured latency/tokens, the code-flow walkthrough (a chat message in the UI → WebSocket → TurnEngine → agentic client → `AntigravityAcpProvider.chat_stream` → `AcpClient` → `agy acp` → chunks back to the UI, with file names), and what's left for him.
  - **AC:** everything green (or each failure shown to exist on the V1 baseline too). Walkthrough delivered. All commits local, nothing pushed.

---

## Changes outside tasks
Fixes and changes Rony asks for in chat, outside a task above. One line each, newest last: date · what changed · which docs were updated, or "no doc change: <why>".
- 2026-11-14 · Claude (in chat, at Rony's request) built most of V1–V5: env install + Claude Code setup, `acp_client.py`, `antigravity_acp_provider.py`, all backend wiring, `provider_probe` CLI-login fix, 24 unit tests, smoke script, plus a new **one-click "Connect a subscription" card** (`quick_connect.py`, `POST /api/settings/quick-connect`, `SubscriptionConnectCard.tsx`). Checked live in the app: Antigravity chat, follow-up context, task model. Docs updated: 07 §3, FORK_NOTICE, PROGRESS. **Not done yet:** `tests/integration/test_antigravity_acp_live.py`, V5 AC 3 (Stop button), AC 4 (a real DeepTutor tool in the UI), AC 6 (embeddings), V6 final pass, and nothing is committed. Antigravity should start at V0 and treat V1–V5 as "verify and fill the gaps", not rebuild.

## Questions for the human
(Agents add questions here; Rony answers inline.)
