# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Unit tests for the antigravity_acp provider, against a fake `agy acp`."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from deeptutor.services.llm.config import LLMConfig
from deeptutor.services.llm.provider_core import antigravity_acp_provider as mod
from deeptutor.services.llm.provider_core.antigravity_acp_provider import (
    AntigravityAcpProvider,
    agy_command,
    map_usage,
    parse_agy_models,
    parse_tool_reply,
    strip_model_prefix,
)
from deeptutor.services.llm.provider_factory import get_runtime_provider
from deeptutor.services.provider_registry import find_by_name

FAKE = Path(__file__).with_name("fake_acp_agent.py")
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
        },
    }
]


@pytest.fixture
def fake_agy(monkeypatch, tmp_path):
    log = tmp_path / "acp.jsonl"

    def configure(**script):
        monkeypatch.setenv("FAKE_ACP_SCRIPT", json.dumps(script))
        monkeypatch.setenv("FAKE_ACP_LOG", str(log))
        monkeypatch.setattr(mod.shutil, "which", lambda name: "agy-fake")
        monkeypatch.setattr(mod, "agy_command", lambda exe: [sys.executable, str(FAKE)])

        def messages():
            if not log.exists():
                return []
            return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

        return messages

    return configure


def _prompts(messages):
    return [m for m in messages if m.get("method") == "session/prompt"]


# ---- registry / wiring -------------------------------------------------------


def test_registry_alias_and_factory() -> None:
    spec = find_by_name("agy")
    assert spec is not None and spec.name == "antigravity_acp" and spec.is_oauth
    provider = get_runtime_provider(
        LLMConfig(
            model="antigravity/gemini-3.8-flash-low",
            api_key="",
            binding="antigravity_acp",
            provider_name="antigravity_acp",
        )
    )
    assert isinstance(provider, AntigravityAcpProvider)


def test_agentic_adapter_is_registered_and_tool_capable() -> None:
    from deeptutor.runtime.agentic import client

    assert "antigravity_acp" in client._NATIVE_ADAPTER_BUILDERS
    assert "antigravity_acp" in client._NATIVE_TOOL_BACKENDS


def test_spawn_args_are_official_and_safe() -> None:
    cmd = agy_command("agy")
    assert cmd == ["agy", "acp", "--sandbox", "--disable-telemetry"]
    assert "--dangerously-skip-permissions" not in cmd


# ---- pure helpers --------------------------------------------------------------


def test_strip_model_prefix() -> None:
    assert strip_model_prefix("antigravity/gemini-3.8-flash-low") == "gemini-3.8-flash-low"
    assert strip_model_prefix("gemini-3.8-flash-low") == "gemini-3.8-flash-low"
    assert strip_model_prefix("") == "gemini-3.8-flash-medium"


def test_parse_agy_models_keeps_gemini_only() -> None:
    out = "Fetching available models...\ngemini-3.8-flash-low\tGemini 3.8 Flash (Low)\nclaude-sonnet-4-6\tClaude\n"
    assert parse_agy_models(out) == [("gemini-3.8-flash-low", "Gemini 3.8 Flash (Low)")]


def test_usage_mapping() -> None:
    assert map_usage(
        {"inputTokens": 10, "outputTokens": 3, "thoughtTokens": 2, "totalTokens": 15}
    ) == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert map_usage(None) == {}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"type":"final","content":"Hi"}', ("final", "Hi")),
        ('```json\n{"type":"final","content":"Hi"}\n```', ("final", "Hi")),
        (
            'Sure! {"type":"tool_calls","calls":[{"name":"web_search","arguments":{"query":"TCP"}}]}',
            ("calls", [("web_search", {"query": "TCP"})]),
        ),
        ('{"type":"tool_calls","calls":[{"name":"rm_rf","arguments":{}}]}', None),
        ('{"type":"tool_calls","calls":[{"name":"web_search","arguments":"TCP"}]}', None),
        ("not json at all", None),
    ],
)
def test_parse_tool_reply(text, expected) -> None:
    parsed = parse_tool_reply(text, {"web_search"})
    if expected is None:
        assert parsed is None
    elif expected[0] == "final":
        assert parsed is not None and parsed.content == expected[1] and not parsed.tool_calls
    else:
        assert parsed is not None
        assert [(c.name, c.arguments) for c in parsed.tool_calls] == expected[1]


# ---- provider against the fake agent ------------------------------------------


@pytest.mark.asyncio
async def test_stream_chunks_arrive_in_order_and_usage_maps(fake_agy) -> None:
    messages = fake_agy(replies=["Hello there, student"], chunk_size=4)
    provider = AntigravityAcpProvider("antigravity/gemini-3.8-flash-low")
    seen: list[str] = []

    async def on_delta(text: str) -> None:
        seen.append(text)

    try:
        response = await provider.chat_stream(
            [{"role": "user", "content": "hi"}], on_content_delta=on_delta
        )
    finally:
        await provider.aclose()
    assert response.content == "Hello there, student"
    assert "".join(seen) == "Hello there, student" and len(seen) > 1
    assert response.usage == {"prompt_tokens": 100, "completion_tokens": 7, "total_tokens": 107}
    sent = messages()
    init = next(m for m in sent if m.get("method") == "initialize")
    assert init["params"]["clientCapabilities"] == {
        "fs": {"readTextFile": False, "writeTextFile": False},
        "terminal": False,
    }
    assert any(m.get("method") == "session/set_model" for m in sent)
    assert any(m.get("method") == "session/close" for m in sent)  # one-shot closes


@pytest.mark.asyncio
async def test_session_reuse_sends_only_new_tail(fake_agy) -> None:
    messages = fake_agy(replies=["first answer", "second answer"])
    provider = AntigravityAcpProvider()
    convo = [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "Q1"}]
    try:
        first = await provider.chat(convo, deeptutor_session_id="s")
        convo += [
            {"role": "assistant", "content": first.content},
            {"role": "user", "content": "Q2"},
        ]
        second = await provider.chat(convo, deeptutor_session_id="s")
    finally:
        await provider.aclose()
    assert second.content == "second answer"
    prompts = [p["params"]["prompt"][0]["text"] for p in _prompts(messages())]
    assert "Be brief." in prompts[0] and "Q1" in prompts[0]
    assert "Q2" in prompts[1] and "Q1" not in prompts[1] and "first answer" not in prompts[1]
    assert len({p["params"]["sessionId"] for p in _prompts(messages())}) == 1


@pytest.mark.asyncio
async def test_history_change_starts_new_session(fake_agy) -> None:
    messages = fake_agy(replies=["a", "b"])
    provider = AntigravityAcpProvider()
    try:
        await provider.chat([{"role": "user", "content": "Q1"}], deeptutor_session_id="s")
        await provider.chat([{"role": "user", "content": "Q1 edited"}], deeptutor_session_id="s")
    finally:
        await provider.aclose()
    sessions = [p["params"]["sessionId"] for p in _prompts(messages())]
    assert len(set(sessions)) == 2


@pytest.mark.asyncio
async def test_permission_is_rejected_and_fs_refused(fake_agy) -> None:
    messages = fake_agy(replies=["done"], permission=True, fs_request=True, tool_update=True)
    provider = AntigravityAcpProvider()
    try:
        response = await provider.chat([{"role": "user", "content": "hi"}])
    finally:
        await provider.aclose()
    assert response.content == "done"
    assert response.provider_specific_fields.get("agy_tool_calls") == 1
    logged = messages()
    permission = next(m["permission_answer"] for m in logged if "permission_answer" in m)
    assert permission == {"outcome": {"outcome": "selected", "optionId": "rej-once"}}
    fs = next(m["fs_answer"] for m in logged if "fs_answer" in m)
    assert fs["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_tool_call_reply_becomes_tool_calls(fake_agy) -> None:
    messages = fake_agy(
        replies=[
            '{"type":"tool_calls","calls":[{"name":"web_search","arguments":{"query":"TCP"}}]}'
        ]
    )
    provider = AntigravityAcpProvider()
    seen: list[str] = []

    async def on_delta(text: str) -> None:
        seen.append(text)

    try:
        response = await provider.chat_stream(
            [{"role": "user", "content": "search"}], tools=TOOLS, on_content_delta=on_delta
        )
    finally:
        await provider.aclose()
    assert response.finish_reason == "tool_calls"
    assert [(c.name, c.arguments) for c in response.tool_calls] == [
        ("web_search", {"query": "TCP"})
    ]
    assert seen == []  # the JSON envelope is never streamed
    assert "<deeptutor_tools>" in _prompts(messages())[0]["params"]["prompt"][0]["text"]


@pytest.mark.asyncio
async def test_tool_mode_repairs_once_then_falls_back_to_text(fake_agy) -> None:
    messages = fake_agy(replies=["not json", "still not json"])
    provider = AntigravityAcpProvider()
    try:
        response = await provider.chat([{"role": "user", "content": "x"}], tools=TOOLS)
    finally:
        await provider.aclose()
    assert response.finish_reason == "stop" and response.content == "still not json"
    assert len(_prompts(messages())) == 2


@pytest.mark.asyncio
async def test_tool_mode_final_content_is_emitted_once(fake_agy) -> None:
    fake_agy(replies=['{"type":"final","content":"The answer"}'])
    provider = AntigravityAcpProvider()
    seen: list[str] = []

    async def on_delta(text: str) -> None:
        seen.append(text)

    try:
        response = await provider.chat_stream(
            [{"role": "user", "content": "x"}], tools=TOOLS, on_content_delta=on_delta
        )
    finally:
        await provider.aclose()
    assert response.content == "The answer" and seen == ["The answer"]


@pytest.mark.asyncio
async def test_missing_agy_is_a_friendly_error(monkeypatch) -> None:
    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    provider = AntigravityAcpProvider()
    try:
        response = await provider.chat([{"role": "user", "content": "hi"}])
    finally:
        await provider.aclose()
    assert response.finish_reason == "error"
    assert "was not found" in (response.content or "")


@pytest.mark.asyncio
async def test_quota_error_is_friendly(fake_agy) -> None:
    fake_agy(prompt_error="RESOURCE_EXHAUSTED: quota exceeded")
    provider = AntigravityAcpProvider()
    try:
        response = await provider.chat([{"role": "user", "content": "hi"}])
    finally:
        await provider.aclose()
    assert response.finish_reason == "error" and "quota" in (response.content or "")


@pytest.mark.asyncio
async def test_timeout_cancels_and_reports(fake_agy, monkeypatch) -> None:
    messages = fake_agy(hang=True)
    monkeypatch.setattr(mod, "_PROMPT_TIMEOUT_S", 1.0)
    provider = AntigravityAcpProvider()
    try:
        response = await provider.chat([{"role": "user", "content": "hi"}])
    finally:
        await provider.aclose()
    assert response.finish_reason == "error" and "longer than" in (response.content or "")
    assert any(m.get("method") == "session/cancel" for m in messages())


@pytest.mark.asyncio
async def test_model_catalog_falls_back_without_agy(monkeypatch) -> None:
    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    rows = await mod.fetch_antigravity_catalog()
    assert [r["id"] for r in rows] == [
        "gemini-3.8-flash-high",
        "gemini-3.8-flash-medium",
        "gemini-3.8-flash-low",
    ]


@pytest.mark.asyncio
async def test_probe_lists_cli_models_without_url(monkeypatch) -> None:
    from deeptutor.services.settings.provider_probe import probe_provider

    async def fake_catalog():
        return [{"id": "gemini-3.8-flash-low", "name": "Low"}]

    monkeypatch.setattr(mod, "fetch_antigravity_catalog", fake_catalog)
    result = await probe_provider("antigravity_acp", "")
    assert result["status"] == "connected"
    assert result["models"] == [{"id": "gemini-3.8-flash-low", "services": ["llm"]}]
