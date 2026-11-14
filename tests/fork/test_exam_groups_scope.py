# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Regression: exam_groups must read the chat's course, not the globally active workspace."""

from __future__ import annotations

from types import SimpleNamespace

from deeptutor.agents._shared.tool_runtime import bind_workspace_tool_runtime
from deeptutor.tools import exam_groups as exam_groups_module


def _context(workspace_id: str) -> SimpleNamespace:
    workspace = SimpleNamespace(workspace_id=workspace_id, root="/ws", output_dir="/ws/out")
    return SimpleNamespace(runtime=SimpleNamespace(workspace=workspace), language="en")


def test_runtime_passes_workspace_id_to_exam_groups() -> None:
    kwargs = bind_workspace_tool_runtime("exam_groups", {"action": "list"}, _context("ws-ai"))
    assert kwargs["_workspace_id"] == "ws-ai"
    assert kwargs["action"] == "list"


def test_tool_prefers_request_scope_over_active_workspace(monkeypatch) -> None:
    calls: list[str] = []

    class _Service:
        def binding_by_id(self, workspace_id: str):
            calls.append(workspace_id)
            return SimpleNamespace(root=workspace_id)

        def current_binding(self):
            raise AssertionError("must not fall back to the globally active workspace")

    monkeypatch.setattr(exam_groups_module, "get_content_workspace_service", lambda: _Service())
    import deeptutor.services.workspace.context as ctx

    monkeypatch.setattr(ctx, "current_workspace_id", lambda: "ws-scope")
    _, binding = exam_groups_module._binding({})
    assert binding.root == "ws-scope"
    _, binding = exam_groups_module._binding({"_workspace_id": "ws-explicit"})
    assert calls == ["ws-scope", "ws-explicit"]


def test_tool_tags_session_with_exam_group(tmp_path, monkeypatch) -> None:
    import asyncio

    from deeptutor.services.course.exam_groups import create_group
    from deeptutor.tools.exam_groups import ExamGroupsTool

    root = tmp_path / "ws"
    root.mkdir()
    create_group(root, "AI Quiz", exam_type="quiz")
    monkeypatch.setattr(
        exam_groups_module, "_binding", lambda kwargs: (None, SimpleNamespace(root=root))
    )
    written: list[tuple[str, dict, bool]] = []

    class _Store:
        async def update_session_preferences(self, session_id, prefs, *, touch=True):
            written.append((session_id, prefs, touch))
            return True

    import deeptutor.services.session as session_pkg

    monkeypatch.setattr(session_pkg, "get_session_store", lambda: _Store())
    tool = ExamGroupsTool()
    asyncio.run(tool.execute(action="list", _session_id="s1"))
    assert written == []
    asyncio.run(tool.execute(action="get", slug="ai-quiz", _session_id="s1"))
    assert written == [("s1", {"exam_group": "ai-quiz", "exam_group_name": "AI Quiz"}, False)]
