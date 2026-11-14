# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Unit tests for the exam_groups tool."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from deeptutor.core.tool_protocol import ToolResult
from deeptutor.services.course.exam_groups import create_group, save_upload
from deeptutor.services.workspace import WorkspaceError
from deeptutor.tools import exam_groups as exam_groups_module
from deeptutor.tools.exam_groups import ExamGroupsTool


@pytest.fixture
def workspace_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fixture that monkeypatches _binding to return tmp_path as workspace root."""
    root = tmp_path / "workspace"
    root.mkdir()
    binding = SimpleNamespace(root=root, workspace_id="ws-test")
    monkeypatch.setattr(exam_groups_module, "_binding", lambda kwargs: (None, binding))
    return root


@pytest.fixture
def tool() -> ExamGroupsTool:
    return ExamGroupsTool()


def test_tool_definition(tool: ExamGroupsTool) -> None:
    defn = tool.get_definition()
    assert defn.name == "exam_groups"
    assert "exams/<slug>/" in defn.description
    assert "EXAM.md" in defn.description
    assert "exam-prep" in defn.description
    param_names = [p.name for p in defn.parameters]
    assert "action" in param_names
    assert "slug" in param_names
    assert "name" in param_names
    assert "type" in param_names
    assert "date" in param_names
    assert "status" in param_names
    assert "syllabus" in param_names
    assert "topics" in param_names


@pytest.mark.asyncio
async def test_action_list_empty(tool: ExamGroupsTool, workspace_root: Path) -> None:
    res = await tool.execute(action="list")
    assert res.success is True
    data = json.loads(res.content)
    assert data == []


@pytest.mark.asyncio
async def test_action_list_with_groups(tool: ExamGroupsTool, workspace_root: Path) -> None:
    create_group(workspace_root, "CT-01", "class_test", "2026-11-20", "Ch 1")
    create_group(workspace_root, "Mid-term", "mid_term", "2026-12-01", "Ch 1-4")

    res = await tool.execute(action="list")
    assert res.success is True
    data = json.loads(res.content)
    assert len(data) == 2
    # Verify compact shape
    for item in data:
        assert set(item.keys()) == {
            "slug",
            "name",
            "type",
            "date",
            "status",
            "progress",
            "file_count",
        }
        assert "syllabus" not in item
        assert "topics" not in item


@pytest.mark.asyncio
async def test_action_create(tool: ExamGroupsTool, workspace_root: Path) -> None:
    res = await tool.execute(
        action="create",
        name="CT-02",
        type="class_test",
        date="2026-11-25",
        syllabus="Search algorithms & Games",
    )
    assert res.success is True
    data = json.loads(res.content)
    assert data["slug"] == "ct-02"
    assert data["name"] == "CT-02"
    assert data["type"] == "class_test"
    assert data["date"] == "2026-11-25"
    assert data["status"] == "planned"
    assert data["syllabus"] == "Search algorithms & Games"
    assert (workspace_root / "exams" / "ct-02" / "EXAM.md").exists()


@pytest.mark.asyncio
async def test_action_get(tool: ExamGroupsTool, workspace_root: Path) -> None:
    create_group(workspace_root, "CT-02", "class_test", "2026-11-25", "Syllabus text")
    save_upload(workspace_root, "ct-02", "slides.pdf", b"slides content")
    save_upload(workspace_root, "ct-02", "pyqs/2023.pdf", b"pyq content")

    res = await tool.execute(action="get", slug="ct-02")
    assert res.success is True
    data = json.loads(res.content)
    assert data["slug"] == "ct-02"
    assert data["syllabus"] == "Syllabus text"
    assert "file_tree" in data
    # Paths in file_tree must be relative to the workspace root: e.g. exams/ct-02/slides.pdf
    tree = data["file_tree"]
    file_paths = []

    def _collect(nodes: list[dict[str, Any]]) -> None:
        for n in nodes:
            file_paths.append(n["path"])
            if "children" in n:
                _collect(n["children"])

    _collect(tree)
    assert "exams/ct-02/slides.pdf" in file_paths
    assert "exams/ct-02/pyqs/2023.pdf" in file_paths
    assert "exams/ct-02/EXAM.md" in file_paths


@pytest.mark.asyncio
async def test_action_update(tool: ExamGroupsTool, workspace_root: Path) -> None:
    create_group(workspace_root, "Quiz 1", "quiz", "2026-11-18", "Intro")

    res = await tool.execute(
        action="update",
        slug="quiz-1",
        name="Quiz 01 (Updated)",
        status="preparing",
        syllabus="Intro + Ch 1",
    )
    assert res.success is True
    data = json.loads(res.content)
    assert data["name"] == "Quiz 01 (Updated)"
    assert data["status"] == "preparing"
    assert data["syllabus"] == "Intro + Ch 1"


@pytest.mark.asyncio
async def test_action_update_topics_merge(tool: ExamGroupsTool, workspace_root: Path) -> None:
    create_group(workspace_root, "CT-01", "class_test", "2026-11-20")
    # Set initial topics
    await tool.execute(
        action="update",
        slug="ct-01",
        topics=[
            {"title": "Uninformed search", "status": "learning"},
            {"title": "A* search", "status": "todo"},
        ],
    )

    # Perform update_topics with case-insensitive matching & new topic appended
    res = await tool.execute(
        action="update_topics",
        slug="ct-01",
        topics=[
            {"title": "uninformed search", "status": "known"},  # update existing
            {"title": "Adversarial search", "status": "todo"},  # append new
        ],
    )
    assert res.success is True
    data = json.loads(res.content)
    topics = data["topics"]
    assert len(topics) == 3
    # Existing title casing preserved, status updated
    assert topics[0] == {"title": "Uninformed search", "status": "known"}
    # Untouched existing topic kept
    assert topics[1] == {"title": "A* search", "status": "todo"}
    # Appended new topic
    assert topics[2] == {"title": "Adversarial search", "status": "todo"}
    # Progress recalculation
    assert data["progress"] == {"known": 1, "total": 3}


@pytest.mark.asyncio
async def test_errors_return_success_false(tool: ExamGroupsTool, workspace_root: Path) -> None:
    # Missing action
    res = await tool.execute()
    assert isinstance(res, ToolResult)
    assert res.success is False

    # Unknown action
    res = await tool.execute(action="destroy_everything")
    assert res.success is False
    assert "Unknown action" in res.content

    # Missing slug on get
    res = await tool.execute(action="get")
    assert res.success is False
    assert "slug is required" in res.content

    # Non-existent group on get
    res = await tool.execute(action="get", slug="non-existent")
    assert res.success is False
    assert "not found" in res.content

    # Missing name on create
    res = await tool.execute(action="create", name="")
    assert res.success is False

    # Invalid type on create
    res = await tool.execute(action="create", name="Test", type="invalid_exam_type")
    assert res.success is False

    # Invalid status on update
    create_group(workspace_root, "CT-03")
    res = await tool.execute(action="update", slug="ct-03", status="invalid_status")
    assert res.success is False

    # Invalid topics format on update_topics
    res = await tool.execute(action="update_topics", slug="ct-03", topics="not-a-list")
    assert res.success is False

    # Invalid topic status on update_topics
    res = await tool.execute(
        action="update_topics",
        slug="ct-03",
        topics=[{"title": "Search", "status": "bad_status"}],
    )
    assert res.success is False


@pytest.mark.asyncio
async def test_workspace_error_returns_success_false(
    tool: ExamGroupsTool, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raising_binding(kwargs: dict[str, Any]):
        raise WorkspaceError("Workspace catalog unavailable")

    monkeypatch.setattr(exam_groups_module, "_binding", _raising_binding)
    res = await tool.execute(action="list")
    assert isinstance(res, ToolResult)
    assert res.success is False
    assert "Workspace catalog unavailable" in res.content
