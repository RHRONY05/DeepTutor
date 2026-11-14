# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Unit tests for course settings sidecar, default persona resolution, and instructions API."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError:
    pytest.skip("fastapi not installed", allow_module_level=True)

from deeptutor.api.routers import courses as courses_router
from deeptutor.services.course import settings as course_settings
from deeptutor.services.course.settings import (
    default_persona_for_current_workspace,
    get_course_settings,
    set_course_settings,
)
from deeptutor.services.workspace import WorkspaceError
from deeptutor.services.workspace.context import WorkspaceScope, workspace_context

# ---------------------------------------------------------------------------
# Sidecar round-trip tests
# ---------------------------------------------------------------------------


def test_course_settings_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings_file = tmp_path / "fork_courses.json"
    monkeypatch.setattr(course_settings, "_settings_file", lambda: settings_file)

    # File does not exist initially
    data = get_course_settings("ws-101")
    assert data == {"default_persona": ""}


def test_course_settings_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings_file = tmp_path / "fork_courses.json"
    monkeypatch.setattr(course_settings, "_settings_file", lambda: settings_file)

    # Set persona for ws-101
    res1 = set_course_settings("ws-101", "socratic")
    assert res1 == {"default_persona": "socratic"}

    # Set persona for ws-102
    set_course_settings("ws-102", "code_mentor")

    # Read back
    assert get_course_settings("ws-101") == {"default_persona": "socratic"}
    assert get_course_settings("ws-102") == {"default_persona": "code_mentor"}
    assert get_course_settings("ws-103") == {"default_persona": ""}

    # Overwrite ws-101
    set_course_settings("ws-101", "")
    assert get_course_settings("ws-101") == {"default_persona": ""}


def test_course_settings_corrupt_file_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_file = tmp_path / "fork_courses.json"
    settings_file.write_text("invalid json content {{{", encoding="utf-8")
    monkeypatch.setattr(course_settings, "_settings_file", lambda: settings_file)

    # Should not crash, returns default
    assert get_course_settings("ws-101") == {"default_persona": ""}


# ---------------------------------------------------------------------------
# default_persona_for_current_workspace tests
# ---------------------------------------------------------------------------


def test_default_persona_unset_workspace_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_file = tmp_path / "fork_courses.json"
    monkeypatch.setattr(course_settings, "_settings_file", lambda: settings_file)

    # With no active workspace scope
    assert default_persona_for_current_workspace() == ""


def test_default_persona_with_workspace_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_file = tmp_path / "fork_courses.json"
    monkeypatch.setattr(course_settings, "_settings_file", lambda: settings_file)

    set_course_settings("ws-math", "math_genius")

    scope = WorkspaceScope(
        workspace_id="ws-math",
        account_root=tmp_path,
        content_root=tmp_path,
    )
    with workspace_context(scope):
        assert default_persona_for_current_workspace() == "math_genius"

    # Outside the context scope, defaults to ""
    assert default_persona_for_current_workspace() == ""


def test_default_persona_error_resilience(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force get_course_settings to raise an error
    def _raise(*args, **kwargs):
        raise RuntimeError("database locked")

    monkeypatch.setattr(course_settings, "get_course_settings", _raise)
    monkeypatch.setattr(
        "deeptutor.services.workspace.context.current_workspace_id",
        lambda: "ws-error",
    )

    assert default_persona_for_current_workspace() == ""


# ---------------------------------------------------------------------------
# Instructions API route tests
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    ws_root = tmp_path / "workspace"
    ws_root.mkdir()

    class _FakeService:
        def binding_by_id(self, workspace_id: str):
            if workspace_id == "ws-1":
                return SimpleNamespace(root=ws_root)
            raise WorkspaceError(f"Unknown workspace: {workspace_id}")

        def workspace_instructions(self, workspace_id: str | None = None) -> str:
            if workspace_id == "ws-1":
                return "Focus on practice problems and step-by-step proofs."
            return ""

    monkeypatch.setattr(courses_router, "get_content_workspace_service", lambda: _FakeService())

    settings_file = tmp_path / "fork_courses.json"
    monkeypatch.setattr(course_settings, "_settings_file", lambda: settings_file)
    set_course_settings("ws-1", "exam_coach")

    app = FastAPI()
    app.include_router(courses_router.router, prefix="/api/courses")
    return TestClient(app)


def test_get_instructions_unknown_workspace(api_client: TestClient) -> None:
    resp = api_client.get("/api/courses/nonexistent-ws/instructions")
    assert resp.status_code == 404


def test_get_instructions_success(api_client: TestClient) -> None:
    resp = api_client.get("/api/courses/ws-1/instructions")
    assert resp.status_code == 200
    data = resp.json()

    assert "base_prompt" in data
    assert "DeepTutor" in data["base_prompt"]

    assert data["workspace_instructions"] == "Focus on practice problems and step-by-step proofs."
    assert data["max_instructions_chars"] == 10000
    assert data["default_persona"] == "exam_coach"

    assert "exam_prep_template" in data
    assert "exam-prep" in data["exam_prep_template"]
