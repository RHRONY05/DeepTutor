# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Antigravity provider: Gemini through a Google AI Pro subscription.

Drives the official, unmodified Antigravity CLI in its documented ACP server
mode (``agy acp``), which signs in with whatever Google account the operator
used for ``agy``. No API key, no token handling: authentication stays inside
the CLI. Contract: ``.agent/07-ACP-PROVIDER.md``.

Safety: the CLI runs with ``--sandbox`` in an empty temp directory, every
permission request is denied, and file-system/terminal requests are refused.
DeepTutor's own tools are emulated with a strict JSON reply format because the
agent cannot host them.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
from typing import Any
import uuid

from deeptutor.services.llm.provider_core.acp_client import AcpClient, AcpError, AcpProcessExited
from deeptutor.services.llm.provider_core.base import LLMProvider, LLMResponse, ToolCallRequest
from deeptutor.services.llm.provider_core.sdk_bridge import _content_text, _messages_to_prompt

logger = logging.getLogger(__name__)

DEFAULT_ANTIGRAVITY_MODEL = "antigravity/gemini-3.8-flash-medium"
FALLBACK_ANTIGRAVITY_MODELS = (
    ("gemini-3.8-flash-high", "Gemini 3.8 Flash (High)"),
    ("gemini-3.8-flash-medium", "Gemini 3.8 Flash (Medium)"),
    ("gemini-3.8-flash-low", "Gemini 3.8 Flash (Low)"),
)
_SESSION_POOL_MAXSIZE = 4
_PROMPT_TIMEOUT_S = 300.0
_START_TIMEOUT_S = 60.0
_SESSION_NEW_TIMEOUT_S = 90.0
_LABEL = "Antigravity"
_NOT_FOUND = (
    "Antigravity CLI (`agy`) was not found. Install it from antigravity.google "
    "and run `agy` once in a terminal to sign in."
)


class AgyNotFound(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------------


def agy_command(executable: str) -> list[str]:
    """The only way this provider starts the CLI. Never skips permissions."""
    return [executable, "acp", "--sandbox", "--disable-telemetry"]


def strip_model_prefix(model: str | None) -> str:
    value = (model or "").strip() or DEFAULT_ANTIGRAVITY_MODEL
    if "/" in value:
        prefix, rest = value.split("/", 1)
        if prefix.lower().replace("-", "_") in {"antigravity", "antigravity_acp", "agy"}:
            value = rest
    return value


def parse_agy_models(output: str) -> list[tuple[str, str]]:
    """Parse ``agy models`` (``<id>\\t<name>`` lines), keeping Gemini models only."""
    models: list[tuple[str, str]] = []
    for line in output.splitlines():
        if "\t" not in line:
            continue
        model_id, name = (part.strip() for part in line.split("\t", 1))
        if model_id.startswith("gemini-"):
            models.append((model_id, name or model_id))
    return models


def map_usage(usage: Any) -> dict[str, int]:
    if not isinstance(usage, dict):
        return {}

    def num(key: str) -> int:
        value = usage.get(key)
        return int(value) if isinstance(value, (int, float)) else 0

    prompt = num("inputTokens")
    completion = num("outputTokens") + num("thoughtTokens")
    total = num("totalTokens") or prompt + completion
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}


def _tool_specs(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for tool in tools or []:
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        specs.append(
            {
                "name": name,
                "description": str(fn.get("description") or "").strip(),
                "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return specs


def build_tools_block(tools: list[dict[str, Any]] | None, tool_choice: Any = None) -> str:
    lines = [
        "<deeptutor_tools>",
        "You can call these DeepTutor tools. Do NOT use any of your own Antigravity tools.",
    ]
    for spec in _tool_specs(tools):
        params = json.dumps(spec["parameters"], ensure_ascii=False, separators=(",", ":"))
        lines.append(f"- {spec['name']}: {spec['description']} | parameters: {params}")
    lines += [
        "Reply with exactly ONE JSON object and nothing else, in one of these two shapes:",
        '{"type":"final","content":"<your answer to the user, markdown allowed>"}',
        '{"type":"tool_calls","calls":[{"name":"<tool name>","arguments":{...}}]}',
    ]
    forced = None
    if isinstance(tool_choice, dict):
        fn = tool_choice.get("function") if isinstance(tool_choice.get("function"), dict) else {}
        forced = fn.get("name") or tool_choice.get("name")
    if forced:
        lines.append(f"You must call the tool {forced}.")
    elif tool_choice == "required":
        lines.append("You must call at least one tool.")
    lines.append("</deeptutor_tools>")
    return "\n".join(lines)


@dataclass
class ParsedReply:
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)


def parse_tool_reply(text: str, tool_names: set[str]) -> ParsedReply | None:
    """Parse the JSON reply format. ``None`` means it did not follow the format."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        body = raw.split("\n", 1)[1] if "\n" in raw else ""
        if body.rstrip().endswith("```"):
            raw = body.rstrip()[:-3].strip()
    data: Any = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            with suppress(json.JSONDecodeError):
                data = json.loads(raw[start : end + 1])
    if not isinstance(data, dict):
        return None
    kind = data.get("type")
    if kind == "final":
        content = data.get("content")
        return ParsedReply(content=content if isinstance(content, str) else _content_text(content))
    if kind == "tool_calls":
        calls = data.get("calls")
        if not isinstance(calls, list) or not calls:
            return None
        parsed: list[ToolCallRequest] = []
        for call in calls:
            if not isinstance(call, dict):
                return None
            name = call.get("name")
            arguments = call.get("arguments", {})
            if name not in tool_names or not isinstance(arguments, dict):
                return None
            parsed.append(
                ToolCallRequest(id=f"call_{uuid.uuid4().hex[:8]}", name=name, arguments=arguments)
            )
        return ParsedReply(content=None, tool_calls=parsed)
    return None


def friendly_error(exc: BaseException) -> str:
    message = str(exc)
    lowered = message.lower()
    if isinstance(exc, (AgyNotFound, FileNotFoundError)):
        return f"Error calling {_LABEL}: {_NOT_FOUND}"
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return f"Error calling {_LABEL}: it took longer than {int(_PROMPT_TIMEOUT_S)} s and was stopped."
    if any(
        word in lowered for word in ("resource_exhausted", "quota", "rate limit", "limit reached")
    ):
        return (
            f"Error calling {_LABEL}: the Antigravity quota for this account is used up. "
            "Wait for it to reset or switch to another model."
        )
    if any(
        word in lowered for word in ("auth", "login", "sign in", "credential", "unauthenticated")
    ):
        return (
            f"Error calling {_LABEL}: Antigravity CLI is not signed in. Run `agy` in a terminal "
            "and sign in with your Google AI Pro account."
        )
    if isinstance(exc, AcpProcessExited):
        return (
            f"Error calling {_LABEL}: Antigravity CLI stopped unexpectedly ({message}). Try again."
        )
    return f"Error calling {_LABEL}: {message}"


def _split_system(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    system: list[str] = []
    conversation: list[dict[str, Any]] = []
    for message in messages:
        if str(message.get("role") or "") == "system":
            text = _content_text(message.get("content"))
            if text:
                system.append(text)
        else:
            conversation.append(message)
    return "\n\n".join(system), conversation


def _signature(model: str, system: str, tools: list[dict[str, Any]] | None) -> str:
    names = ",".join(sorted(spec["name"] for spec in _tool_specs(tools)))
    return hashlib.sha256(f"{model}\0{system}\0{names}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


@dataclass
class _Turn:
    queue: asyncio.Queue[str | None]
    chunks: list[str] = field(default_factory=list)
    agent_tool_calls: int = 0


@dataclass
class _Session:
    acp_id: str
    signature: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_response: str = ""
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class AntigravityAcpProvider(LLMProvider):
    """LLM provider backed by the local ``agy acp`` server."""

    def __init__(self, default_model: str | None = DEFAULT_ANTIGRAVITY_MODEL):
        super().__init__(api_key=None, api_base=None)
        self.default_model = default_model or DEFAULT_ANTIGRAVITY_MODEL
        self._workspace = tempfile.TemporaryDirectory(prefix="dt-agy-provider-")
        self._client: AcpClient | None = None
        self._client_lock = asyncio.Lock()
        self._sessions: OrderedDict[str, _Session] = OrderedDict()
        self._sessions_lock = asyncio.Lock()
        self._turns: dict[str, _Turn] = {}

    def get_default_model(self) -> str:
        return self.default_model

    # ---- LLMProvider API -------------------------------------------------

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        session_id = str(kwargs.pop("deeptutor_session_id", "") or "").strip()
        return await self._run(messages, tools, model, tool_choice, None, session_id)

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        on_content_delta: Callable[[str], Awaitable[None]] | None = None,
        on_reasoning_delta: Callable[[str], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        session_id = str(kwargs.pop("deeptutor_session_id", "") or "").strip()
        return await self._run(messages, tools, model, tool_choice, on_content_delta, session_id)

    async def aclose(self) -> None:
        async with self._sessions_lock:
            self._sessions.clear()
        client, self._client = self._client, None
        if client is not None:
            await client.close()
        with suppress(Exception):
            self._workspace.cleanup()

    # ---- core --------------------------------------------------------------

    async def _run(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str | None,
        tool_choice: Any,
        on_delta: Callable[[str], Awaitable[None]] | None,
        session_id: str,
    ) -> LLMResponse:
        model_id = strip_model_prefix(model or self.default_model)
        tool_mode = bool(_tool_specs(tools)) and tool_choice != "none"
        system, conversation = _split_system(messages)
        try:
            if session_id:
                return await self._run_session(
                    session_id,
                    model_id,
                    system,
                    conversation,
                    tools,
                    tool_choice,
                    tool_mode,
                    on_delta,
                )
            acp_id = await self._new_session(model_id)
            try:
                prompt = _first_prompt(system, conversation)
                return await self._answer(acp_id, prompt, tools, tool_choice, tool_mode, on_delta)
            finally:
                await self._close_session(acp_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - surfaced as a friendly reply
            logger.warning("Antigravity provider error: %s", exc)
            return LLMResponse(content=friendly_error(exc), finish_reason="error")

    async def _run_session(
        self,
        session_id: str,
        model_id: str,
        system: str,
        conversation: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        tool_choice: Any,
        tool_mode: bool,
        on_delta: Callable[[str], Awaitable[None]] | None,
    ) -> LLMResponse:
        signature = _signature(model_id, system, tools)
        session = await self._get_session(session_id, signature, model_id)
        async with session.lock:
            previous = session.messages
            if previous and (
                len(conversation) <= len(previous) or conversation[: len(previous)] != previous
            ):
                # Edited or regenerated history: never append to the old transcript.
                await self._drop_session(session_id, session)
                return await self._run_session(
                    session_id,
                    model_id,
                    system,
                    conversation,
                    tools,
                    tool_choice,
                    tool_mode,
                    on_delta,
                )
            if previous:
                delta = list(conversation[len(previous) :])
                if (
                    delta
                    and delta[0].get("role") == "assistant"
                    and _content_text(delta[0].get("content")) == session.last_response
                ):
                    delta.pop(0)
                prompt = _messages_to_prompt(delta) or _messages_to_prompt(conversation[-1:])
            else:
                prompt = _first_prompt(system, conversation)
            try:
                response = await self._answer(
                    session.acp_id, prompt, tools, tool_choice, tool_mode, on_delta
                )
            except BaseException:
                await self._drop_session(session_id, session)
                raise
            session.messages = list(conversation)
            session.last_response = response.content or ""
            return response

    async def _answer(
        self,
        acp_id: str,
        prompt: str,
        tools: list[dict[str, Any]] | None,
        tool_choice: Any,
        tool_mode: bool,
        on_delta: Callable[[str], Awaitable[None]] | None,
    ) -> LLMResponse:
        if not tool_mode:
            text, usage, extra = await self._prompt(acp_id, prompt, on_delta)
            return LLMResponse(
                content=text, usage=usage, finish_reason="stop", provider_specific_fields=extra
            )
        names = {spec["name"] for spec in _tool_specs(tools)}
        text, usage, extra = await self._prompt(
            acp_id, f"{prompt}\n\n{build_tools_block(tools, tool_choice)}", None
        )
        parsed = parse_tool_reply(text, names)
        if parsed is None:
            logger.info("Antigravity reply did not follow the tool format; asking once more")
            text, usage2, extra = await self._prompt(
                acp_id,
                "Your last reply did not follow the <deeptutor_tools> format. "
                "Reply again with only the JSON object.",
                None,
            )
            usage = {k: usage.get(k, 0) + usage2.get(k, 0) for k in set(usage) | set(usage2)}
            parsed = parse_tool_reply(text, names)
        if parsed is None:
            logger.warning("Antigravity tool reply unparseable twice; returning raw text")
            parsed = ParsedReply(content=text)
        if parsed.tool_calls:
            return LLMResponse(
                content=None,
                tool_calls=parsed.tool_calls,
                finish_reason="tool_calls",
                usage=usage,
                provider_specific_fields=extra,
            )
        if parsed.content and on_delta is not None:
            await on_delta(parsed.content)
        return LLMResponse(
            content=parsed.content,
            usage=usage,
            finish_reason="stop",
            provider_specific_fields=extra,
        )

    async def _prompt(
        self,
        acp_id: str,
        text: str,
        on_delta: Callable[[str], Awaitable[None]] | None,
    ) -> tuple[str, dict[str, int], dict[str, Any]]:
        client = await self._ensure_client()
        turn = _Turn(queue=asyncio.Queue())
        self._turns[acp_id] = turn
        request = asyncio.ensure_future(
            client.request(
                "session/prompt",
                {"sessionId": acp_id, "prompt": [{"type": "text", "text": text}]},
                timeout=_PROMPT_TIMEOUT_S,
            )
        )
        # Chunks arrive on stdout before the prompt's response, and both are
        # dispatched in order on this loop, so the sentinel always comes last.
        request.add_done_callback(lambda _f: turn.queue.put_nowait(None))
        try:
            while (chunk := await turn.queue.get()) is not None:
                if on_delta is not None:
                    await on_delta(chunk)
            result = request.result() or {}
        except BaseException as exc:
            request.cancel()
            if isinstance(exc, (asyncio.CancelledError, asyncio.TimeoutError, TimeoutError)):
                with suppress(Exception):
                    await client.notify("session/cancel", {"sessionId": acp_id})
            raise
        finally:
            self._turns.pop(acp_id, None)
        extra: dict[str, Any] = {"stop_reason": result.get("stopReason")}
        if turn.agent_tool_calls:
            extra["agy_tool_calls"] = turn.agent_tool_calls
        return "".join(turn.chunks), map_usage(result.get("usage")), extra

    # ---- sessions -------------------------------------------------------------

    async def _get_session(self, session_id: str, signature: str, model_id: str) -> _Session:
        stale: list[str] = []
        async with self._sessions_lock:
            existing = self._sessions.get(session_id)
            if existing and existing.signature == signature and self._client and self._client.alive:
                self._sessions.move_to_end(session_id)
                return existing
            if existing:
                self._sessions.pop(session_id, None)
                stale.append(existing.acp_id)
            session = _Session(acp_id=await self._new_session(model_id), signature=signature)
            self._sessions[session_id] = session
            while len(self._sessions) > _SESSION_POOL_MAXSIZE:
                idle = next(
                    (
                        k
                        for k, s in self._sessions.items()
                        if k != session_id and not s.lock.locked()
                    ),
                    None,
                )
                if idle is None:
                    break
                stale.append(self._sessions.pop(idle).acp_id)
        for acp_id in stale:
            await self._close_session(acp_id)
        return session

    async def _drop_session(self, session_id: str, session: _Session) -> None:
        async with self._sessions_lock:
            if self._sessions.get(session_id) is session:
                self._sessions.pop(session_id, None)
        await self._close_session(session.acp_id)

    async def _new_session(self, model_id: str) -> str:
        client = await self._ensure_client()
        result = await client.request(
            "session/new",
            {"cwd": self._workspace.name, "mcpServers": []},
            timeout=_SESSION_NEW_TIMEOUT_S,
        )
        acp_id = str((result or {}).get("sessionId") or "")
        if not acp_id:
            raise RuntimeError("Antigravity did not return a session id")
        current = ((result or {}).get("models") or {}).get("currentModelId")
        if model_id and model_id != current:
            await client.request(
                "session/set_model", {"sessionId": acp_id, "modelId": model_id}, timeout=30
            )
        return acp_id

    async def _close_session(self, acp_id: str) -> None:
        client = self._client
        if client is None or not client.alive:
            return
        with suppress(Exception):
            await client.request("session/close", {"sessionId": acp_id}, timeout=5)

    # ---- process ----------------------------------------------------------------

    async def _ensure_client(self) -> AcpClient:
        async with self._client_lock:
            if self._client is not None and self._client.alive:
                return self._client
            if self._client is not None:
                await self._client.close()
                self._client = None
                # Plain clear (no lock): callers may already hold _sessions_lock.
                self._sessions.clear()
            executable = shutil.which("agy")
            if not executable:
                raise AgyNotFound(_NOT_FOUND)
            client = AcpClient(
                agy_command(executable),
                self._workspace.name,
                on_notification=self._on_notification,
                on_request=self._on_request,
            )
            await client.start()
            try:
                await client.request(
                    "initialize",
                    {
                        "protocolVersion": 1,
                        "clientCapabilities": {
                            "fs": {"readTextFile": False, "writeTextFile": False},
                            "terminal": False,
                        },
                    },
                    timeout=_START_TIMEOUT_S,
                )
            except BaseException:
                await client.close()
                raise
            self._client = client
            return client

    def _on_notification(self, method: str, params: dict[str, Any]) -> None:
        if method != "session/update":
            return
        turn = self._turns.get(str(params.get("sessionId") or ""))
        update = params.get("update") if isinstance(params.get("update"), dict) else {}
        kind = update.get("sessionUpdate")
        if turn is None:
            return
        if kind == "agent_message_chunk":
            content = update.get("content") or {}
            if isinstance(content, dict) and content.get("type") == "text":
                text = str(content.get("text") or "")
                if text:
                    turn.chunks.append(text)
                    turn.queue.put_nowait(text)
        elif kind == "tool_call":
            turn.agent_tool_calls += 1
            logger.warning(
                "Antigravity used one of its own tools during a DeepTutor turn: %s",
                str(update.get("title") or update.get("kind") or "tool")[:120],
            )

    async def _on_request(self, method: str, params: dict[str, Any]) -> Any:
        if method == "session/request_permission":
            options = params.get("options") if isinstance(params.get("options"), list) else []
            rejects = [o for o in options if str(o.get("kind") or "").startswith("reject")]
            rejects.sort(key=lambda o: 0 if o.get("kind") == "reject_once" else 1)
            tool = params.get("toolCall") if isinstance(params.get("toolCall"), dict) else {}
            logger.info(
                "Denied Antigravity permission request: %s", str(tool.get("title") or "")[:120]
            )
            if rejects:
                return {"outcome": {"outcome": "selected", "optionId": rejects[0].get("optionId")}}
            return {"outcome": {"outcome": "cancelled"}}
        raise AcpError(-32601, "not supported by this client")


def _first_prompt(system: str, conversation: list[dict[str, Any]]) -> str:
    body = _messages_to_prompt(conversation)
    if not system:
        return body
    return f"<deeptutor_instructions>\n{system}\n</deeptutor_instructions>\n\n{body}"


async def fetch_antigravity_catalog() -> list[dict[str, str]]:
    """Gemini models the signed-in ``agy`` offers. No model request is made."""
    executable = shutil.which("agy")
    models: list[tuple[str, str]] = []
    if executable:
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                [executable, "models"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            models = parse_agy_models(completed.stdout or "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("agy model list unavailable (%s)", type(exc).__name__)
    if not models:
        models = list(FALLBACK_ANTIGRAVITY_MODELS)
    return [{"id": model_id, "name": name} for model_id, name in models]


async def fetch_antigravity_models() -> list[str]:
    return [row["id"] for row in await fetch_antigravity_catalog()]


__all__ = [
    "AntigravityAcpProvider",
    "DEFAULT_ANTIGRAVITY_MODEL",
    "agy_command",
    "build_tools_block",
    "fetch_antigravity_catalog",
    "fetch_antigravity_models",
    "friendly_error",
    "map_usage",
    "parse_agy_models",
    "parse_tool_reply",
    "strip_model_prefix",
]
