# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Minimal Agent Client Protocol (ACP) client over stdio.

ACP is newline-delimited JSON-RPC 2.0 between a client (us) and an agent
process. This module knows nothing about a specific agent: it starts the
process, matches responses to requests by id, hands notifications to a
callback and answers agent->client requests through a handler.

Reading uses plain threads instead of asyncio subprocess pipes, so it works on
any event loop (Windows Selector loops have no subprocess support) and has no
line-length limit (ACP messages such as ``session/new`` can be large).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
import json
import logging
import subprocess
import threading
from typing import Any

logger = logging.getLogger(__name__)

NotificationHandler = Callable[[str, dict[str, Any]], None]
RequestHandler = Callable[[str, dict[str, Any]], Awaitable[Any]]


class AcpError(RuntimeError):
    """A JSON-RPC error returned by the agent, or one we send back."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"ACP error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


class AcpProcessExited(RuntimeError):
    """The agent process ended while requests were pending."""


class AcpClient:
    def __init__(
        self,
        cmd: list[str],
        cwd: str,
        *,
        on_notification: NotificationHandler | None = None,
        on_request: RequestHandler | None = None,
    ) -> None:
        self._cmd = cmd
        self._cwd = cwd
        self._on_notification = on_notification
        self._on_request = on_request
        self._proc: subprocess.Popen[bytes] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._next_id = 0
        self._write_lock = threading.Lock()
        self._exited = False
        self._exit_reason = ""
        self._tasks: set[asyncio.Task[Any]] = set()

    @property
    def alive(self) -> bool:
        return self._proc is not None and not self._exited and self._proc.poll() is None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # FileNotFoundError propagates so the caller can explain a missing CLI.
        self._proc = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
            self._cmd,
            cwd=self._cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
        )
        threading.Thread(target=self._read_stdout, name="acp-stdout", daemon=True).start()
        threading.Thread(target=self._read_stderr, name="acp-stderr", daemon=True).start()

    # ---- reader threads -------------------------------------------------

    def _read_stdout(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for raw in self._proc.stdout:
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                self._call_soon(self._dispatch, line)
        self._call_soon(self._mark_exited, "agent closed its output")

    def _read_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        for raw in self._proc.stderr:
            text = raw.decode("utf-8", errors="replace").rstrip()
            if text:
                logger.debug("acp stderr: %s", text[:500])

    def _call_soon(self, fn: Callable[..., Any], *args: Any) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        with suppress(RuntimeError):
            loop.call_soon_threadsafe(fn, *args)

    # ---- dispatch (event loop thread) -----------------------------------

    def _dispatch(self, line: str) -> None:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("acp: ignoring non-JSON line %r", line[:200])
            return
        if not isinstance(msg, dict):
            return
        method = msg.get("method")
        if method is None and "id" in msg:
            future = self._pending.pop(msg.get("id"), None)
            if future is None or future.done():
                return
            error = msg.get("error")
            if isinstance(error, dict):
                future.set_exception(
                    AcpError(
                        int(error.get("code") or -32000),
                        str(error.get("message") or "error"),
                        error.get("data"),
                    )
                )
            else:
                future.set_result(msg.get("result"))
            return
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        if "id" in msg:
            task = asyncio.ensure_future(self._answer(msg["id"], str(method), params))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        elif self._on_notification is not None:
            try:
                self._on_notification(str(method), params)
            except Exception:  # noqa: BLE001 - a bad handler must not kill the reader
                logger.exception("acp notification handler failed for %s", method)

    async def _answer(self, request_id: Any, method: str, params: dict[str, Any]) -> None:
        try:
            if self._on_request is None:
                raise AcpError(-32601, "not supported by this client")
            result = await self._on_request(method, params)
            reply: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "result": result}
        except AcpError as exc:
            reply = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": exc.code, "message": exc.message},
            }
        except Exception:  # noqa: BLE001
            logger.exception("acp request handler failed for %s", method)
            reply = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": "internal client error"},
            }
        with suppress(Exception):
            await self._write(reply)

    def _mark_exited(self, reason: str) -> None:
        if self._exited:
            return
        self._exited = True
        self._exit_reason = reason
        for future in self._pending.values():
            if not future.done():
                future.set_exception(AcpProcessExited(reason))
        self._pending.clear()

    # ---- sending ---------------------------------------------------------

    async def _write(self, obj: dict[str, Any]) -> None:
        if not self.alive:
            raise AcpProcessExited(self._exit_reason or "agent is not running")
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        await asyncio.to_thread(self._write_blocking, data)

    def _write_blocking(self, data: bytes) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        with self._write_lock:
            self._proc.stdin.write(data)
            self._proc.stdin.flush()

    async def request(
        self, method: str, params: dict[str, Any], *, timeout: float | None = None
    ) -> Any:
        assert self._loop is not None, "start() first"
        self._next_id += 1
        request_id = self._next_id
        future: asyncio.Future[Any] = self._loop.create_future()
        self._pending[request_id] = future
        try:
            await self._write(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            )
            if timeout is None:
                return await future
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(request_id, None)

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    async def close(self) -> None:
        proc = self._proc
        if proc is None:
            return
        self._mark_exited("client closed")
        with suppress(Exception):
            if proc.stdin is not None:
                proc.stdin.close()
        try:
            await asyncio.wait_for(asyncio.to_thread(proc.wait), 5)
        except (asyncio.TimeoutError, TimeoutError):
            with suppress(Exception):
                proc.kill()
        for task in list(self._tasks):
            task.cancel()


__all__ = ["AcpClient", "AcpError", "AcpProcessExited"]
