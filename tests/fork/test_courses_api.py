# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""FastAPI TestClient tests for deeptutor.api.routers.courses."""

from __future__ import annotations

import io
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
from deeptutor.services.course.exam_groups import EXAM_FILE, create_group

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_binding(root: Path) -> SimpleNamespace:
    """Return a fake WorkspaceBinding whose .root points at *root*."""
    return SimpleNamespace(root=root)


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    root.mkdir()
    return root


@pytest.fixture
def client(workspace_root: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Build a minimal FastAPI app with just the courses router.

    Monkeypatches:
      - ``get_content_workspace_service`` → returns a fake that:
          - ``binding_by_id("ws-1")`` → returns a binding pointing at workspace_root
          - ``list_workspaces()``      → returns two entries (workspace + system)
      - ``get_course_settings`` / ``set_course_settings`` work against tmp files
        (they are pure functions using path_service, so we patch at the router level)
    """

    class _FakeService:
        def binding_by_id(self, workspace_id: str):
            if workspace_id == "ws-1":
                return _make_binding(workspace_root)
            from deeptutor.services.workspace import WorkspaceError
            raise WorkspaceError(f"Unknown workspace: {workspace_id}")

        def list_workspaces(self):
            return [
                {"workspace_id": "ws-1", "display_name": "Algorithms", "kind": "workspace"},
                {"workspace_id": "ws-sys", "display_name": "System", "kind": "system"},
            ]

    fake_svc = _FakeService()
    monkeypatch.setattr(courses_router, "get_content_workspace_service", lambda: fake_svc)

    app = FastAPI()
    app.include_router(courses_router.router, prefix="/api/courses")
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------


def test_list_courses_returns_only_workspace_kind(client: TestClient) -> None:
    resp = client.get("/api/courses")
    assert resp.status_code == 200
    courses = resp.json()["courses"]
    # Only "workspace" kind (not system) should appear
    assert len(courses) == 1
    assert courses[0]["workspace_id"] == "ws-1"
    assert courses[0]["kind"] == "workspace"
    assert courses[0]["group_count"] == 0
    assert courses[0]["next_exam"] is None


def test_list_courses_includes_group_count_and_next_exam(
    client: TestClient, workspace_root: Path
) -> None:
    create_group(workspace_root, "CT-01", date="2099-12-01")
    create_group(workspace_root, "CT-02", date="2099-11-20")
    resp = client.get("/api/courses")
    assert resp.status_code == 200
    course = resp.json()["courses"][0]
    assert course["group_count"] == 2
    # Next exam = earliest future date
    assert course["next_exam"]["slug"] == "ct-02"


# ---------------------------------------------------------------------------
# Groups collection
# ---------------------------------------------------------------------------


def test_list_groups_empty(client: TestClient) -> None:
    resp = client.get("/api/courses/ws-1/groups")
    assert resp.status_code == 200
    assert resp.json()["groups"] == []


def test_create_group(client: TestClient) -> None:
    resp = client.post(
        "/api/courses/ws-1/groups",
        json={"name": "Quiz 1", "type": "quiz", "date": "2026-11-25", "syllabus": "Chapter 2"},
    )
    assert resp.status_code == 201
    g = resp.json()["group"]
    assert g["slug"] == "quiz-1"
    assert g["name"] == "Quiz 1"
    assert g["type"] == "quiz"


def test_create_group_invalid_type(client: TestClient) -> None:
    resp = client.post("/api/courses/ws-1/groups", json={"name": "X", "type": "bad"})
    assert resp.status_code == 400


def test_list_groups_after_create(client: TestClient) -> None:
    client.post("/api/courses/ws-1/groups", json={"name": "Alpha"})
    client.post("/api/courses/ws-1/groups", json={"name": "Beta"})
    resp = client.get("/api/courses/ws-1/groups")
    assert resp.status_code == 200
    assert len(resp.json()["groups"]) == 2


def test_workspace_not_found_returns_404(client: TestClient) -> None:
    resp = client.get("/api/courses/ws-missing/groups")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Single group CRUD
# ---------------------------------------------------------------------------


def test_get_group(client: TestClient) -> None:
    client.post("/api/courses/ws-1/groups", json={"name": "Mid Term"})
    resp = client.get("/api/courses/ws-1/groups/mid-term")
    assert resp.status_code == 200
    assert resp.json()["group"]["name"] == "Mid Term"


def test_get_group_not_found(client: TestClient) -> None:
    resp = client.get("/api/courses/ws-1/groups/ghost")
    assert resp.status_code == 404


def test_patch_group(client: TestClient) -> None:
    client.post("/api/courses/ws-1/groups", json={"name": "Lab"})
    resp = client.patch(
        "/api/courses/ws-1/groups/lab",
        json={"status": "preparing", "syllabus": "New syllabus"},
    )
    assert resp.status_code == 200
    g = resp.json()["group"]
    assert g["status"] == "preparing"
    assert g["syllabus"] == "New syllabus"


def test_patch_group_invalid_status(client: TestClient) -> None:
    client.post("/api/courses/ws-1/groups", json={"name": "Lab"})
    resp = client.patch("/api/courses/ws-1/groups/lab", json={"status": "nope"})
    assert resp.status_code == 400


def test_delete_group(client: TestClient) -> None:
    client.post("/api/courses/ws-1/groups", json={"name": "Temp"})
    resp = client.delete("/api/courses/ws-1/groups/temp")
    assert resp.status_code == 204
    assert client.get("/api/courses/ws-1/groups/temp").status_code == 404


def test_delete_group_non_empty_requires_force(
    client: TestClient, workspace_root: Path
) -> None:
    client.post("/api/courses/ws-1/groups", json={"name": "Lab"})
    # Add a file directly
    (workspace_root / "exams" / "lab" / "file.txt").write_bytes(b"data")
    resp = client.delete("/api/courses/ws-1/groups/lab")
    assert resp.status_code == 400
    resp_force = client.delete("/api/courses/ws-1/groups/lab?force=true")
    assert resp_force.status_code == 204


# ---------------------------------------------------------------------------
# File tree
# ---------------------------------------------------------------------------


def test_file_tree_empty_group(client: TestClient) -> None:
    client.post("/api/courses/ws-1/groups", json={"name": "Lab"})
    resp = client.get("/api/courses/ws-1/groups/lab/tree")
    assert resp.status_code == 200
    tree = resp.json()["tree"]
    # EXAM.md should appear
    names = [e["name"] for e in tree]
    assert EXAM_FILE in names


def test_file_tree_not_found(client: TestClient) -> None:
    resp = client.get("/api/courses/ws-1/groups/ghost/tree")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# File upload / delete
# ---------------------------------------------------------------------------


def test_upload_file(client: TestClient, workspace_root: Path) -> None:
    client.post("/api/courses/ws-1/groups", json={"name": "Lab"})
    resp = client.post(
        "/api/courses/ws-1/groups/lab/files",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 201
    assert (workspace_root / "exams" / "lab" / "notes.txt").read_bytes() == b"hello"


def test_upload_file_with_folder(client: TestClient, workspace_root: Path) -> None:
    client.post("/api/courses/ws-1/groups", json={"name": "Lab"})
    resp = client.post(
        "/api/courses/ws-1/groups/lab/files",
        files={"file": ("2023.pdf", io.BytesIO(b"pdf"), "application/pdf")},
        data={"folder": "pyq"},
    )
    assert resp.status_code == 201
    assert (workspace_root / "exams" / "lab" / "pyq" / "2023.pdf").read_bytes() == b"pdf"


def test_upload_traversal_rejected(client: TestClient) -> None:
    client.post("/api/courses/ws-1/groups", json={"name": "Lab"})
    resp = client.post(
        "/api/courses/ws-1/groups/lab/files",
        files={"file": ("../../evil.txt", io.BytesIO(b"bad"), "text/plain")},
    )
    assert resp.status_code == 400


def test_delete_uploaded_file(client: TestClient, workspace_root: Path) -> None:
    client.post("/api/courses/ws-1/groups", json={"name": "Lab"})
    client.post(
        "/api/courses/ws-1/groups/lab/files",
        files={"file": ("note.txt", io.BytesIO(b"x"), "text/plain")},
    )
    resp = client.delete("/api/courses/ws-1/groups/lab/files?path=note.txt")
    assert resp.status_code == 204
    assert not (workspace_root / "exams" / "lab" / "note.txt").exists()


def test_delete_missing_file_returns_404(client: TestClient) -> None:
    client.post("/api/courses/ws-1/groups", json={"name": "Lab"})
    resp = client.delete("/api/courses/ws-1/groups/lab/files?path=ghost.txt")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def test_get_settings_default(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        courses_router, "get_course_settings", lambda ws_id: {"default_persona": ""}
    )
    resp = client.get("/api/courses/ws-1/settings")
    assert resp.status_code == 200
    assert resp.json()["settings"]["default_persona"] == ""


def test_put_settings(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    stored: dict = {}

    def fake_set(ws_id: str, persona: str) -> dict:
        stored[ws_id] = persona
        return {"default_persona": persona}

    monkeypatch.setattr(courses_router, "get_course_settings", lambda ws_id: {"default_persona": stored.get(ws_id, "")})
    monkeypatch.setattr(courses_router, "set_course_settings", fake_set)

    resp = client.put("/api/courses/ws-1/settings", json={"default_persona": "socratic"})
    assert resp.status_code == 200
    assert resp.json()["settings"]["default_persona"] == "socratic"
    assert stored["ws-1"] == "socratic"
