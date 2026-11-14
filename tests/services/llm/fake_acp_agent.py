# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""A scriptable stand-in for `agy acp`, used by the antigravity_acp tests.

Speaks newline-delimited JSON-RPC on stdio. Behaviour comes from the JSON in
the FAKE_ACP_SCRIPT env var:
  replies:      list of reply texts, used in order for each session/prompt
  chunk_size:   split each reply into chunks of this many characters (default: whole)
  permission:   true -> ask for permission before the first reply
  fs_request:   true -> send an fs/read_text_file request before the first reply
  tool_update:  true -> emit a tool_call update before the first reply
  prompt_error: error message to return for session/prompt
  hang:         true -> never answer session/prompt
It appends every received message to FAKE_ACP_LOG (JSONL) so tests can assert.
"""

from __future__ import annotations

import json
import os
import sys
import threading

SCRIPT = json.loads(os.environ.get("FAKE_ACP_SCRIPT") or "{}")
LOG = os.environ.get("FAKE_ACP_LOG")
replies = list(SCRIPT.get("replies") or ["ok"])
pending: dict[int, threading.Event] = {}
answers: dict[int, dict] = {}
next_id = [1000]
lock = threading.Lock()
sessions = 0
prompts = 0


def send(obj: dict) -> None:
    with lock:
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()


def log(obj: dict) -> None:
    if LOG:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj) + "\n")


def ask(method: str, params: dict) -> dict:
    next_id[0] += 1
    rid = next_id[0]
    event = threading.Event()
    pending[rid] = event
    send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
    event.wait(10)
    return answers.get(rid, {})


def update(sid: str, upd: dict) -> None:
    send(
        {"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": sid, "update": upd}}
    )


def handle_prompt(msg: dict) -> None:
    global prompts
    sid = msg["params"]["sessionId"]
    first = prompts == 0
    prompts += 1
    if SCRIPT.get("hang"):
        return
    if first and SCRIPT.get("permission"):
        result = ask(
            "session/request_permission",
            {
                "sessionId": sid,
                "toolCall": {"title": "run_command rm -rf"},
                "options": [
                    {"optionId": "allow", "kind": "allow_once"},
                    {"optionId": "rej-always", "kind": "reject_always"},
                    {"optionId": "rej-once", "kind": "reject_once"},
                ],
            },
        )
        log({"permission_answer": result})
    if first and SCRIPT.get("fs_request"):
        log({"fs_answer": ask("fs/read_text_file", {"sessionId": sid, "path": "C:/secret.txt"})})
    if first and SCRIPT.get("tool_update"):
        update(sid, {"sessionUpdate": "tool_call", "title": "search_web"})
    if SCRIPT.get("prompt_error"):
        send(
            {
                "jsonrpc": "2.0",
                "id": msg["id"],
                "error": {"code": -32000, "message": SCRIPT["prompt_error"]},
            }
        )
        return
    text = replies.pop(0) if replies else "ok"
    size = int(SCRIPT.get("chunk_size") or 0) or len(text) or 1
    for i in range(0, len(text), size):
        update(
            sid,
            {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": text[i : i + size]},
            },
        )
    send(
        {
            "jsonrpc": "2.0",
            "id": msg["id"],
            "result": {
                "stopReason": "end_turn",
                "usage": {
                    "inputTokens": 100,
                    "outputTokens": 5,
                    "thoughtTokens": 2,
                    "totalTokens": 107,
                },
            },
        }
    )


def main() -> None:
    global sessions
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        log(msg)
        method = msg.get("method")
        if method is None:
            rid = msg.get("id")
            answers[rid] = msg.get("result") or {"error": msg.get("error")}
            if rid in pending:
                pending[rid].set()
            continue
        if method == "initialize":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": msg["id"],
                    "result": {"protocolVersion": 1, "agentCapabilities": {}},
                }
            )
        elif method == "session/new":
            sessions += 1
            send(
                {
                    "jsonrpc": "2.0",
                    "id": msg["id"],
                    "result": {
                        "sessionId": f"s{sessions}",
                        "models": {"currentModelId": "gemini-3.8-flash-high"},
                    },
                }
            )
        elif method in {"session/set_model", "session/close"}:
            send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
        elif method == "session/prompt":
            threading.Thread(target=handle_prompt, args=(msg,), daemon=True).start()
        elif method == "session/cancel":
            pass
        elif "id" in msg:
            send(
                {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "unknown"}}
            )


if __name__ == "__main__":
    main()
