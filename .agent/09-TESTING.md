# 09 — Testing

> Fork addition. Scaled to a backend provider: no browser e2e suite and no Lighthouse (this change adds no pages).
> UI checks are manual ACs in a real browser (08-TASKS V5).

## Commands
- Unit + existing suite: `.venv\Scripts\python -m pytest tests/services/llm -q`, then the full `.venv\Scripts\python -m pytest -q` before the final task.
- Lint/format: `.venv\Scripts\python -m ruff check deeptutor tests` and `ruff format --check` on the touched files.
- Frontend (only V5 touches it): `cd web && npm run lint && npm run build`. Use whatever script names `web/package.json` defines. Don't invent new ones.
- Live (real `agy`, costs a little Antigravity quota): `set DEEPTUTOR_LIVE_AGY=1` then `pytest tests/integration/test_antigravity_acp_live.py -q -s`.

## Layer 1 — Unit (`tests/services/llm/test_antigravity_acp_provider.py`)
Use `tests/services/llm/fake_acp_agent.py`: a standalone Python script that speaks ACP on stdio and is
started in place of `agy` (monkeypatch `shutil.which` / the provider's command builder). It reads a
JSON "script" from an env var and replies accordingly: canned `initialize`/`session/new` results (copy the
shapes in 07 §1), `agent_message_chunk` sequences, a `session/request_permission` request, an
`fs/read_text_file` request, a `tool_call` update, an error, a hang, or an exit.

Cases (one test each, names are suggestions):
1. `test_registry_alias_and_factory`: `find_by_name("agy")` → `antigravity_acp`, `is_oauth`, factory returns `AntigravityAcpProvider` (copy `test_claude_code_registry_alias_and_factory`).
2. `test_spawn_args_are_official_and_safe`: command is `[<agy>, "acp", "--sandbox", "--disable-telemetry"]`, cwd is an empty temp dir, and the args never contain `--dangerously-skip-permissions`.
3. `test_initialize_declares_no_fs_or_terminal`.
4. `test_stream_chunks_reach_on_content_delta_in_order`.
5. `test_session_reuse_sends_only_new_tail` (2 turns, second prompt contains only the new user message).
6. `test_history_change_starts_new_session_with_full_transcript`.
7. `test_permission_request_is_rejected` (picks the `reject_once` option; with no reject option → `cancelled`).
8. `test_fs_and_terminal_requests_get_method_not_found`.
9. `test_agent_tool_call_update_is_counted_not_fatal`.
10. `test_set_model_called_when_model_differs`.
11. `test_one_shot_closes_its_session`.
12. `test_lru_evicts_and_closes_fifth_session`.
13. `test_cancel_sends_session_cancel`.
14. `test_timeout_returns_error_response` (shrink the timeout constant via monkeypatch).
15. `test_process_exit_fails_pending_and_restarts_next_call`.
16. `test_missing_agy_friendly_error`, `test_auth_error_friendly`, `test_quota_error_friendly`.
17. `test_usage_mapping`.
18. `parse_tool_reply` table test with these worked examples (they are fixtures, keep them in sync with 07 §4):

| Input | Expected |
|---|---|
| `{"type":"final","content":"Hi"}` | final, content `Hi` |
| ```` ```json\n{"type":"final","content":"Hi"}\n``` ```` | final, content `Hi` |
| `Sure! {"type":"tool_calls","calls":[{"name":"web_search","arguments":{"query":"TCP"}}]}` | 1 call `web_search` with `{"query":"TCP"}` |
| `{"type":"tool_calls","calls":[{"name":"rm_rf","arguments":{}}]}` (unknown tool) | invalid → repair |
| `{"type":"tool_calls","calls":[{"name":"web_search","arguments":"TCP"}]}` | invalid → repair |
| `not json at all` | invalid → repair |

19. `test_tool_mode_repair_then_fallback_to_text` (fake replies bad, then bad again → raw text, `finish_reason="stop"`).
20. `test_tool_mode_does_not_stream_json_envelope` (`on_content_delta` gets only the final content once).
21. `test_model_catalog_parses_agy_models_and_falls_back`.

## Layer 2 — Integration, live (`tests/integration/test_antigravity_acp_live.py`, skipped unless `DEEPTUTOR_LIVE_AGY=1`)
Use `gemini-3.8-flash-low` to save quota. Each test ≤ 3 prompts.
1. `test_live_one_prompt`: "Reply with exactly: pong" → reply contains `pong`. Record latency + usage in the test output.
2. `test_live_context_carries`: mango test from 07 §1.
3. `test_system_prompt_honoured`: decides system-prompt option A vs B (07 §3).
4. `test_live_tool_call_roundtrip`: one fake tool `get_course_name` (no args). Prompt: "Use the tool to find my course name, then tell me." Expect a `tool_calls` response, feed back the result `Computer Networks`, expect the final answer to contain `Computer Networks`.
5. `test_live_streaming_has_chunks`: ~120-word answer → `on_content_delta` called ≥ 2 times.

## Layer 3 — Agent loop / app integration
- Existing tests in `tests/services/llm/` and `tests/agents/chat/` still pass (nothing upstream broken).
- `tests/services/llm/test_antigravity_acp_provider.py::test_agentic_adapter_builds` → `_NATIVE_ADAPTER_BUILDERS["antigravity_acp"]` returns an adapter, and `antigravity_acp` is in `_NATIVE_TOOL_BACKENDS`.

## Layer 4 — Manual in the real app (V5 AC)
Desktop browser at the local dev URL `deeptutor start --dev` prints. Steps in 08-TASKS V5.

## Test data and safety
- No real Google or Anthropic credentials in tests. The fake agent never touches `.gemini`.
- Live tests only run when Rony sets the env var. Never in CI.
