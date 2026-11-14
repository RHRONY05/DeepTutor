# 02 — Architecture of the fork change

> Fork addition (not part of upstream DeepTutor).

## Repo and remotes
- Local clone: `D:\Projects\DeepTutor`, branch `main`.
- Remote `upstream` = `https://github.com/HKUDS/DeepTutor.git`. There is **no `origin`** yet, and nothing is ever pushed until Rony creates his own GitHub repo and asks.
- Pulling updates later: `git fetch upstream` → `git merge upstream/main` on `main`. Keep fork edits small and fenced (see "Fork markers") so merges stay easy.

## Stack (unchanged upstream)
Python ≥ 3.11 backend (`deeptutor/`, FastAPI + WebSocket), Next.js frontend (`web/`), pytest + pytest-asyncio, ruff.
Install from source per upstream README: `python -m pip install -r requirements/full.txt`, `python -m pip install -e . --no-deps`,
`python -m pip install "claude-agent-sdk>=0.2.174,<0.3"` (the `claude-code` extra), `( cd web && npm ci --legacy-peer-deps )`, `deeptutor init`, `deeptutor start --dev`.
Use a virtualenv at `D:\Projects\DeepTutor\.venv` (git-ignored). **No new Python or npm dependencies** for this change: the ACP client is plain `asyncio` + `json`.

## How a chat turn reaches a model (existing)
```
Settings (data/user/settings/*.json: provider + model)
  → provider_registry.ProviderSpec(backend=…)
  → services/llm/provider_factory.get_runtime_provider()        # plain LLM calls
  → runtime/agentic/client._NATIVE_ADAPTER_BUILDERS[backend]     # agent loop (tools)
  → LLMProvider.chat() / chat_stream()  →  LLMResponse(content, tool_calls, usage)
```

## Files this change touches

New files (header: `# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.`):

| File | What |
|---|---|
| `deeptutor/services/llm/provider_core/acp_client.py` | Minimal async ACP (JSON-RPC over stdio) client: spawn, request/response by id, notification routing, agent→client request handler hook, shutdown. No Antigravity specifics. |
| `deeptutor/services/llm/provider_core/antigravity_acp_provider.py` | `AntigravityAcpProvider(LLMProvider)`, session pool, prompt building, tool JSON protocol, error mapping, `fetch_antigravity_models()`, `parse_tool_reply()`. Spec: `07-ACP-PROVIDER.md`. |
| `tests/services/llm/test_antigravity_acp_provider.py` | Unit tests with a fake ACP agent (09-TESTING). |
| `tests/services/llm/fake_acp_agent.py` | Scriptable fake `agy acp` (a Python script that speaks ACP on stdio). |
| `tests/integration/test_antigravity_acp_live.py` | Live tests against the real `agy`, skipped unless `DEEPTUTOR_LIVE_AGY=1`. |
| `scripts/fork/agy_acp_smoke.py` | Tiny manual smoke test: one prompt through the provider, prints reply, latency, usage. |

Modified upstream files (each gets one header line `# Modified in the RH.RONY fork (Apache-2.0 §4b): <what>`, or `// …` in TS, and every fork edit inside the file sits between `# fork(antigravity_acp) start` / `# fork(antigravity_acp) end` comments):

| File | Change |
|---|---|
| `deeptutor/services/provider_registry.py` | New `ProviderSpec(name="antigravity_acp", keywords=("antigravity-acp","antigravity_acp","agy"), env_key="", display_name="Antigravity (Google AI Pro subscription)", backend="antigravity_acp", is_oauth=True, strip_model_prefix=True, supports_stream_options=False)` right after `claude_code`. Aliases `"antigravity-acp"`, `"agy"` → `"antigravity_acp"`. Extend the backend comment on line ~33. |
| `deeptutor/services/llm/provider_factory.py` | `elif backend == "antigravity_acp":` → `AntigravityAcpProvider(default_model=llm_config.model)`. |
| `deeptutor/services/llm/provider_core/__init__.py` | Lazy export `AntigravityAcpProvider` (same pattern as `ClaudeCodeProvider`). |
| `deeptutor/runtime/agentic/client.py` | `_build_antigravity_acp_adapter` → `_ProviderOpenAIAdapter(AntigravityAcpProvider(...))`. Add it to `_NATIVE_ADAPTER_BUILDERS` and `_NATIVE_TOOL_BACKENDS`. |
| `deeptutor/services/llm/capabilities.py` | Entry `"antigravity_acp": {supports_response_format: False, supports_streaming: True, supports_tools: True, supports_vision: False, system_in_messages: True, has_thinking_tags: False}`. Add to `SESSION_SCOPED_BINDINGS`. |
| `deeptutor/multi_user/model_access.py` | Add to `OWNER_BOUND_BINDINGS` (the subscription belongs to the machine owner). `rag/pipelines/lightrag/indexing_policy.py` imports this set, so no edit is needed there. |
| `deeptutor/services/llm/factory.py` | In `fetch_models` (next to the `claude_code` branch, ~line 742), the `antigravity_acp` branch → `fetch_antigravity_models()`. |
| `deeptutor/api/routers/settings.py` | Allow an empty `base_url` for `antigravity_acp`. Model catalog branch like `claude_code`. |
| `web/components/settings/ServiceConfigEditor.tsx` | Add `"antigravity_acp"` to `CLI_LOGIN_BINDINGS` (no base URL, no key, "Sync models"). |
| `AGENTS.md` | Fork block at the top (already added by planning). |

If `grep -rn "claude_code"` finds another place that lists CLI-login or OAuth backends (a set, a switch, a UI label), add `antigravity_acp` there too, the same way, and list it in PROGRESS.md "Decisions".

## Settings and env
- No secrets. No API key field for `antigravity_acp`.
- The prompt timeout is a module constant `_PROMPT_TIMEOUT_S = 300`, not a setting. Upstream ignores project `.env` files, so don't add one.
- Only test env: `DEEPTUTOR_LIVE_AGY=1` (set in the shell) turns on the live tests. Mention it in `FORK_NOTICE.md`.
- Embeddings (no code change): Settings → Embedding → **Gemini** → `gemini-embedding-001` with a free Google AI Studio API key (Rony adds it in the UI), or **Ollama** → `nomic-embed-text` if Ollama is installed. Pick one before the first index. Changing later means re-indexing.

## Course workspaces (V7+)
Files, wiring and data layout: see `10-COURSE-WORKSPACES.md`. Markers there are `fork(course_workspaces)`.

## Fork markers and licence (Apache-2.0)
- Keep `LICENSE` unchanged. `FORK_NOTICE.md` at the root names the fork, credits HKUDS/DeepTutor, and lists every modified and added file with a one-line reason. Every task that touches a file updates that list.
- If the project is renamed later, the credit to HKUDS/DeepTutor stays in `FORK_NOTICE.md` and the README.
