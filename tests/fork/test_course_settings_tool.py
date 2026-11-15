# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""course_settings tool: read, change and undo course instructions; set the default persona."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from deeptutor.services.course import settings as course_settings_store
from deeptutor.tools import course_settings as tool_module
from deeptutor.tools.course_settings import CourseSettingsTool


class FakeWorkspaces:
    def __init__(self) -> None:
        self.instructions = {"ws_dsa": "Teach with hints."}

    def workspace_instructions(self, workspace_id: str) -> str:
        return self.instructions.get(workspace_id, "")

    def update_workspace(self, workspace_id: str, *, instructions: str) -> dict:
        self.instructions[workspace_id] = instructions.strip()
        return {}


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeWorkspaces:
    workspaces = FakeWorkspaces()
    monkeypatch.setattr(tool_module, "get_content_workspace_service", lambda: workspaces)
    monkeypatch.setattr(tool_module, "_persona_names", lambda: ["dsa-mentor", "teacher"])
    monkeypatch.setattr(
        course_settings_store, "_settings_file", lambda: tmp_path / "fork_courses.json"
    )
    return workspaces


def run(**kwargs):
    return asyncio.run(CourseSettingsTool().execute(_workspace_id="ws_dsa", **kwargs))


def test_get_returns_instructions_and_personas(fake: FakeWorkspaces) -> None:
    result = run(action="get")
    assert result.success
    assert result.metadata["instructions"] == "Teach with hints."
    assert result.metadata["personas"] == ["dsa-mentor", "teacher"]
    assert result.metadata["can_undo"] is False


def test_update_then_undo_then_redo(fake: FakeWorkspaces) -> None:
    assert run(action="update_instructions", instructions="Use Python, not C++.").success
    assert fake.instructions["ws_dsa"] == "Use Python, not C++."

    undo = run(action="undo_instructions")
    assert undo.success and fake.instructions["ws_dsa"] == "Teach with hints."

    redo = run(action="undo_instructions")
    assert redo.success and fake.instructions["ws_dsa"] == "Use Python, not C++."


def test_undo_without_history_fails(fake: FakeWorkspaces) -> None:
    result = run(action="undo_instructions")
    assert not result.success
    assert "no earlier version" in result.content


def test_update_requires_text(fake: FakeWorkspaces) -> None:
    assert not run(action="update_instructions", instructions="  ").success
    assert fake.instructions["ws_dsa"] == "Teach with hints."


def test_set_default_persona_checks_the_name(fake: FakeWorkspaces) -> None:
    assert run(action="set_default_persona", persona="teacher").metadata["default_persona"] == (
        "teacher"
    )
    bad = run(action="set_default_persona", persona="ghost")
    assert not bad.success and "No persona named" in bad.content
    assert run(action="set_default_persona", persona="").metadata["default_persona"] == ""


def test_needs_a_course(fake: FakeWorkspaces) -> None:
    result = asyncio.run(CourseSettingsTool().execute(action="get"))
    assert not result.success
    assert "not in a course" in result.content


def test_unknown_action(fake: FakeWorkspaces) -> None:
    assert not run(action="delete_everything").success
