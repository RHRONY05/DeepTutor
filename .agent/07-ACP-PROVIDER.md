# 07 — The `antigravity_acp` provider (core logic)

> Fork addition (not part of upstream DeepTutor). Planned by Claude, 2026-11-14.

DeepTutor's main LLM can be Gemini through Rony's **Google AI Pro** subscription by driving the
**official, unmodified Antigravity CLI** in its documented ACP server mode (`agy acp`). This file is
the contract for that provider. Model it on
`deeptutor/services/llm/provider_core/claude_code_provider.py` (same job, other vendor).

## 1. Facts from the spike (2026-11-14, `agy` 1.5.3 / ACP server 1.5.8, Windows 11)

Measured with a throwaway Python client (`initialize` → `session/new` → `session/set_model` → 2–3 × `session/prompt`):

| Item | Result |
|---|---|
| Transport | Newline-delimited JSON-RPC 2.0 over stdio. `protocolVersion: 1`. |
| `initialize` | 0.9 s. Returns `agentCapabilities` (`loadSession`, `promptCapabilities.image: true`, `sessionCapabilities: resume/close/load/list`), `_meta.antigravity.systemPrompt.append: true`, and `authMethods` (`oauth-personal`, `oauth-business`, `gemini-api-key`, `agent-platform`). No `authenticate` call was needed: it reused the cached login. |
| `session/new` | ~4.5 s. Returns `sessionId`, `models.availableModels` (`gemini-3.8-flash-high/medium/low`, `claude-sonnet-4-6`, `claude-opus-4-6-thinking`, `gpt-oss-120b-medium`), `currentModelId: gemini-3.8-flash-high`, `modes` (`default`, `accept-edits`, `auto`, `plan`), `configOptions`. |
| `session/set_model` | Works (`{"modelId": "gemini-3.8-flash-low"}` → `{}`). |
| Latency per turn | First turn 7–17 s, later turns 5–15 s, and a 120-word answer took 9.8 s. Cold start (process + session) adds ~5 s once. |
| Streaming | `session/update` → `agent_message_chunk` (`content.type: "text"`). Coarse: a 120-word answer came as 7 chunks, the first after 8.2 s. One-word answers come as 1 chunk. |
| Context across turns | **Yes.** Turn 1 "remember mango", turn 2 answered "mango", in the same session. |
| Token overhead | **~18.8–19.7k input tokens per turn**, growing with history (turn 2 ≈ 20.5k). `cachedReadTokens: 0`. `--include-default-customizations=false` did **not** reduce it. This is Antigravity's own agent prompt plus about 60 tools and the user's global skills, and it can't be removed. |
| Usage report | The `session/prompt` result carries `usage: {inputTokens, outputTokens, thoughtTokens, totalTokens, cachedReadTokens, cachedWriteTokens}`. Also `usage_update` notifications (`used`, `size: 1048576`). |
| Other updates | `user_message_chunk`, `available_commands_update` (slash commands + the user's skills), `session_info_update` (auto title), `config_option_update`. |
| Permission requests | None for these prompts. (The client still has to deny them. See §5.) |
| Side effect | **Every ACP session is saved as a conversation** in `%USERPROFILE%\.gemini\antigravity-cli\conversations\<sessionId>.db` (37 → 40 after 3 runs). This is the CLI's own store, separate from the desktop app's `.gemini\antigravity`. |
| Print-mode fallback | `agy -p … --output-format stream-json` works (41 s wall, ~19.6k tokens). The plain `text` format piped printed **nothing** and timed out (upstream bug #76). Never use text mode. |

## 2. Process and session model

- **One long-lived `agy acp` process per provider instance**, started lazily on first use:
  `[shutil.which("agy"), "acp", "--sandbox", "--disable-telemetry"]`, `cwd` = the provider's own
  empty `tempfile.TemporaryDirectory(prefix="dt-agy-provider-")`, stdin/stdout/stderr pipes, UTF-8.
  Never pass `--dangerously-skip-permissions`, `--cloud_code_endpoint`, `--app-data-dir` or any auth flag.
- One `asyncio` **owner task** reads stdout, routes responses by `id`, routes `session/update` to the
  session that owns `params.sessionId`, and answers agent→client requests (§5). Writes go through one
  `asyncio.Lock`. Stderr is drained into `logger.debug` (never shown to the user, never parsed for secrets).
- If the process exits, fail every pending request with a friendly error, drop all sessions, and
  restart it on the next call (at most once per call).
- **ACP sessions:** an `OrderedDict` LRU keyed by DeepTutor `deeptutor_session_id`, max **4**
  (same as `_SESSION_POOL_MAXSIZE` in the Claude provider). On eviction, send `session/close` (best effort).
  Each entry stores: `signature` (hash of model + system prompt + tool names), the list of non-system
  messages already sent, `last_response`, and an `asyncio.Lock` (one prompt at a time per session).
- **One-shot calls** (no `deeptutor_session_id`, e.g. titles and task models): `session/new` on the
  shared process, one `session/prompt`, then `session/close`.
- New session setup: `session/new {cwd: <provider temp dir>, mcpServers: []}`, then
  `session/set_model {modelId}` when the requested model differs from `currentModelId`.

## 3. Turning DeepTutor messages into ACP prompts

- **System prompt. Built (2026-11-14): option B** (system text sent once, wrapped in
  `<deeptutor_instructions>`, as the start of the first prompt). Option A was not tried. Re-test it only if B misbehaves.
  The original decision rule:
  - A: put `"_meta": {"antigravity": {"systemPrompt": {"append": "<system text>"}}}` in `session/new`.
    It works if the `system-prompt-honoured` integration test passes (system says "always answer in
    exactly 3 words", user says "hi", reply has 3 words).
  - B (if A fails or errors): send the system text once, as the first part of the first prompt,
    wrapped as `<deeptutor_instructions>…</deeptutor_instructions>` followed by the user message.
  - Record which one won in PROGRESS.md "Decisions".
- **Incremental turns** (same rule as `claude_code_provider._incremental_messages`): if the stored
  `messages` are a prefix of the new conversation (ignoring system), send only the new tail. Otherwise
  (edited or regenerated history, or a signature change), close the ACP session, open a new one, and send
  the whole conversation as one transcript prompt. Reuse `sdk_bridge._messages_to_prompt` /
  `_content_text` for the transcript text.
- **Tool results** (`role: "tool"`) are rendered as text in the next prompt:
  `Tool result (<name or tool_call_id>):\n<content>`. This is what the Claude provider does too.
- **Images:** out of scope for v1. Non-text parts become `[image omitted]`. Capability `supports_vision: False`.
- Every prompt is `[{"type": "text", "text": …}]`.

## 4. Tool calls through JSON replies

Antigravity can't host DeepTutor's tools, so tools are emulated with a strict reply format.

- When `tools` is non-empty and `tool_choice != "none"`, append this block to the prompt being sent
  (filled with the tools' `name`, `description` and JSON `parameters`):

  ```text
  <deeptutor_tools>
  You can call these DeepTutor tools. Do NOT use any of your own Antigravity tools.
  {one line per tool: - <name>: <description> | parameters: <compact JSON schema>}
  Reply with exactly ONE JSON object and nothing else, in one of these two shapes:
  {"type":"final","content":"<your answer to the user, markdown allowed>"}
  {"type":"tool_calls","calls":[{"name":"<tool name>","arguments":{...}}]}
  </deeptutor_tools>
  ```
  If `tool_choice` names one tool, add the line `You must call the tool <name>.`.
- In tool mode, **don't stream** chunks to `on_content_delta`. Buffer the reply, parse it, then emit the
  final `content` as one delta (so the UI still shows text).
- Parsing (`parse_tool_reply(text, tool_names) -> ParsedReply`, a pure function with unit tests):
  1. Strip whitespace and one surrounding ```` ```json … ``` ```` fence if present.
  2. If that fails, take the first `{` to the last `}` and `json.loads` it.
  3. `type == "final"` → `LLMResponse(content=content)`.
  4. `type == "tool_calls"` → each call needs a `name` in `tool_names` and a dict `arguments` →
     `ToolCallRequest(id=f"call_{uuid4().hex[:8]}", name, arguments)`, `finish_reason="tool_calls"`.
  5. Anything else (bad JSON, unknown tool, non-dict arguments) → **one repair turn** in the same
     session: `Your last reply did not follow the <deeptutor_tools> format. Reply again with only the JSON object.`
     If the repair also fails → return the raw text as `content` with `finish_reason="stop"` and log a warning.
- Without tools: plain text, streamed chunk by chunk.

## 5. Safety (non-negotiable)

- Only the official binary found on `PATH` (`agy` / `agy.exe`), unmodified, started as above.
- Never read, copy, log or pass the `gemini:antigravity` Credential Manager entry,
  `%APPDATA%\Antigravity\credential-user-scope`, or anything under `.gemini` except as the agy process itself does.
  Never call Google endpoints directly.
- Agent→client requests:
  - `session/request_permission` → pick the first option whose `kind` starts with `reject`
    (prefer `reject_once`), otherwise `{"outcome": {"outcome": "cancelled"}}`. Log the tool name at INFO.
  - `fs/*`, `terminal/*`, or any other method → JSON-RPC error `-32601 "not supported by this client"`.
    The client advertises `fs.readTextFile/writeTextFile: false` and `terminal: false` in `initialize`.
- `session/update` with `sessionUpdate: "tool_call"` (agent used one of its own tools without asking,
  e.g. web search) → log a warning with the tool's title and count it in
  `LLMResponse.provider_specific_fields["agy_tool_calls"]`. Don't fail the turn.
- Cancellation (DeepTutor stops a stream): send the notification `session/cancel {sessionId}`, wait up
  to 5 s for the prompt result (`stopReason: "cancelled"`), then drop the session.
- Timeout: `_PROMPT_TIMEOUT_S = 300` per `session/prompt` → cancel as above, return the error response.

## 6. Errors → friendly messages (returned as `LLMResponse(content=…, finish_reason="error")`, like `_friendly_error`)

| Situation | Message |
|---|---|
| `agy` not on PATH | "Antigravity CLI (`agy`) was not found. Install it from antigravity.google and run `agy` once to sign in." |
| `session/new` error mentioning auth/login/credentials, or `authMethods` with no cached login | "Antigravity CLI is not signed in. Run `agy` in a terminal and sign in with your Google AI Pro account." |
| Quota/limit error text (`RESOURCE_EXHAUSTED`, "quota", "limit") | "Your Antigravity quota for this account is used up. Wait for it to reset or switch to the Claude Code provider." |
| Process died / JSON-RPC error | "Antigravity CLI stopped unexpectedly: <short reason>. Try again." |
| Timeout | "Antigravity took longer than <n> s and was stopped." |

## 7. Models

- `fetch_antigravity_models()` → run `agy models` (timeout 20 s) and parse `<id>\t<display name>` lines.
  Keep only ids starting with `gemini-`. Fallback list: `gemini-3.8-flash-high`, `gemini-3.8-flash-medium`, `gemini-3.8-flash-low`.
- Default model `antigravity/gemini-3.8-flash-medium` (`strip_model_prefix=True` removes `antigravity/`).
  Recommended task model: `gemini-3.8-flash-low`.
- Claude and GPT models that agy lists are **not** offered. Google's docs only promise Gemini models to every ACP client.

## 8. Usage mapping

`LLMResponse.usage = {"prompt_tokens": inputTokens, "completion_tokens": outputTokens + thoughtTokens, "total_tokens": totalTokens}`.
Missing fields default to 0.

## 9. Fallback: print-mode shim (only if ACP breaks in a future `agy` update)

If the V3 integration tests can't pass because `agy acp` stops working, stop and add a question in
`08-TASKS.md`. Don't switch on your own. The planned fallback is a provider mode that runs
`agy -p <prompt> --output-format stream-json --model <id> --sandbox [--conversation <id>]` per turn,
parses `step_update.text_delta` / `result.response` / `result.conversation_id`, and keeps the
conversation id per DeepTutor session. ~40 s per turn. Never use `--output-format text`.
