# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Manual smoke test: prompts through AntigravityAcpProvider, prints reply, time, usage.

Usage: python scripts/fork/agy_acp_smoke.py ["prompt"] [model]
Spends a little real Antigravity quota on whichever Google account `agy` uses.
"""

from __future__ import annotations

import asyncio
import sys
import time

from deeptutor.services.llm.provider_core.antigravity_acp_provider import AntigravityAcpProvider


async def main() -> None:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Reply with exactly: pong"
    model = sys.argv[2] if len(sys.argv) > 2 else "antigravity/gemini-3.8-flash-low"
    provider = AntigravityAcpProvider(default_model=model)
    chunks: list[str] = []

    async def on_delta(text: str) -> None:
        chunks.append(text)

    try:
        started = time.monotonic()
        first = await provider.chat_stream(
            [{"role": "user", "content": prompt}],
            on_content_delta=on_delta,
            deeptutor_session_id="smoke",
        )
        print(
            f"turn 1 ({time.monotonic() - started:.1f}s, {len(chunks)} chunks): {first.content!r}"
        )
        print(f"usage: {first.usage}  finish: {first.finish_reason}")
        if first.finish_reason == "error":
            return
        started = time.monotonic()
        second = await provider.chat(
            [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": first.content},
                {"role": "user", "content": "What did I ask you a moment ago? One short sentence."},
            ],
            deeptutor_session_id="smoke",
        )
        print(f"turn 2 ({time.monotonic() - started:.1f}s): {second.content!r}")
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_course_name",
                    "description": "Returns the name of the course the student is studying.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        started = time.monotonic()
        third = await provider.chat(
            [{"role": "user", "content": "Use the tool to find my course name, then tell me."}],
            tools=tools,
        )
        print(
            f"tool turn ({time.monotonic() - started:.1f}s): finish={third.finish_reason} calls={[(c.name, c.arguments) for c in third.tool_calls]} content={third.content!r}"
        )
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
