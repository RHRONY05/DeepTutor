# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Courses API router — exam groups and per-course settings.

Mounted at ``/api/courses`` by the server.json route entry (order 850).

Endpoints
---------
GET  /api/courses
    List workspaces of kind "workspace" or "general" with group counts and
    next upcoming exam.

GET  /api/courses/{workspace_id}/groups
POST /api/courses/{workspace_id}/groups
GET  /api/courses/{workspace_id}/groups/{slug}
PATCH /api/courses/{workspace_id}/groups/{slug}
DELETE /api/courses/{workspace_id}/groups/{slug}?force=true

GET  /api/courses/{workspace_id}/groups/{slug}/tree
POST /api/courses/{workspace_id}/groups/{slug}/files   (multipart UploadFile)
DELETE /api/courses/{workspace_id}/groups/{slug}/files?path=...

GET /api/courses/{workspace_id}/settings
PUT /api/courses/{workspace_id}/settings

GET /api/courses/{workspace_id}/instructions
"""

from __future__ import annotations

import asyncio
from datetime import date as _date
import functools
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
import yaml

from deeptutor.services.course.exam_groups import (
    MAX_UPLOAD_BYTES,
    ExamGroupError,
    create_group,
    delete_file,
    delete_group,
    file_tree,
    get_group,
    list_groups,
    save_upload,
    update_group,
)
from deeptutor.services.course.settings import get_course_settings, set_course_settings
from deeptutor.services.workspace import WorkspaceError, get_content_workspace_service
from deeptutor.services.workspace.models import MAX_WORKSPACE_INSTRUCTIONS_CHARS

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _workspace_root(workspace_id: str):
    """Resolve workspace root path; raise 404/400 on error."""
    try:
        binding = get_content_workspace_service().binding_by_id(workspace_id)
        return binding.root
    except WorkspaceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _exam_error_to_http(exc: ExamGroupError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _next_exam(groups: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the next upcoming exam (closest future date), or None."""
    today = _date.today().isoformat()
    upcoming = [g for g in groups if g.get("date") and g["date"] >= today]
    if not upcoming:
        return None
    upcoming.sort(key=lambda g: g["date"])
    g = upcoming[0]
    return {"slug": g["slug"], "name": g["name"], "date": g["date"]}


# ---------------------------------------------------------------------------
# GET /api/courses — workspace list
# ---------------------------------------------------------------------------


@router.get("")
async def list_courses() -> dict:
    """Return workspaces of kind 'workspace' or 'general' with exam metadata."""
    svc = get_content_workspace_service()
    try:
        all_ws: list[dict[str, Any]] = await asyncio.to_thread(svc.list_workspaces)
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    courses: list[dict[str, Any]] = []
    for ws in all_ws:
        kind = ws.get("kind", "")
        if kind not in {"workspace", "general"}:
            continue
        workspace_id = ws["workspace_id"]
        try:
            binding = svc.binding_by_id(workspace_id)
            root = binding.root
            groups = await asyncio.to_thread(list_groups, root)
            next_exam = _next_exam(groups)
        except (WorkspaceError, ExamGroupError, OSError):
            groups = []
            next_exam = None

        courses.append(
            {
                "workspace_id": workspace_id,
                "display_name": ws.get("display_name", ""),
                "kind": kind,
                "group_count": len(groups),
                "next_exam": next_exam,
            }
        )

    return {"courses": courses}


# ---------------------------------------------------------------------------
# Groups collection
# ---------------------------------------------------------------------------


@router.get("/{workspace_id}/groups")
async def list_workspace_groups(workspace_id: str) -> dict:
    root = _workspace_root(workspace_id)
    try:
        groups = await asyncio.to_thread(list_groups, root)
    except ExamGroupError as exc:
        raise _exam_error_to_http(exc) from exc
    return {"groups": groups}


@router.post("/{workspace_id}/groups", status_code=201)
async def create_workspace_group(workspace_id: str, payload: dict) -> dict:
    root = _workspace_root(workspace_id)
    try:
        group = await asyncio.to_thread(
            create_group,
            root,
            payload.get("name", ""),
            payload.get("type", "other"),
            payload.get("date", ""),
            payload.get("syllabus", ""),
        )
    except ExamGroupError as exc:
        raise _exam_error_to_http(exc) from exc
    return {"group": group}


# ---------------------------------------------------------------------------
# Single group
# ---------------------------------------------------------------------------


@router.get("/{workspace_id}/groups/{slug}")
async def get_workspace_group(workspace_id: str, slug: str) -> dict:
    root = _workspace_root(workspace_id)
    try:
        group = await asyncio.to_thread(get_group, root, slug)
    except ExamGroupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"group": group}


@router.patch("/{workspace_id}/groups/{slug}")
async def patch_workspace_group(workspace_id: str, slug: str, payload: dict) -> dict:
    root = _workspace_root(workspace_id)
    # Only pass fields that were actually provided
    allowed = {"name", "type", "date", "status", "syllabus", "topics", "lessons"}
    fields = {k: v for k, v in payload.items() if k in allowed}
    try:
        group = await asyncio.to_thread(update_group, root, slug, **fields)
    except ExamGroupError as exc:
        raise _exam_error_to_http(exc) from exc
    return {"group": group}


@router.delete("/{workspace_id}/groups/{slug}", status_code=204)
async def delete_workspace_group(
    workspace_id: str,
    slug: str,
    force: bool = Query(default=False),
) -> None:
    root = _workspace_root(workspace_id)
    try:
        await asyncio.to_thread(delete_group, root, slug, force)
    except ExamGroupError as exc:
        # 400 for "not empty", 404 for "not found"
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc


# ---------------------------------------------------------------------------
# File tree
# ---------------------------------------------------------------------------


@router.get("/{workspace_id}/groups/{slug}/tree")
async def get_group_file_tree(workspace_id: str, slug: str) -> dict:
    root = _workspace_root(workspace_id)
    try:
        tree = await asyncio.to_thread(file_tree, root, slug)
    except ExamGroupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"tree": tree}


# ---------------------------------------------------------------------------
# File upload / delete
# ---------------------------------------------------------------------------


@router.post("/{workspace_id}/groups/{slug}/files", status_code=201)
async def upload_group_file(
    workspace_id: str,
    slug: str,
    file: UploadFile = File(...),
    folder: str = Form(default=""),
) -> dict:
    """Upload a file into the exam group directory.

    Use the optional *folder* form field for a relative sub-path prefix
    (e.g. ``pyq``). The resulting stored path is ``<folder>/<filename>``.
    """
    root = _workspace_root(workspace_id)

    # Read bytes in a thread to avoid blocking the event loop
    # Read at most one byte past the cap so oversized uploads fail fast.
    data: bytes = await asyncio.to_thread(file.file.read, MAX_UPLOAD_BYTES + 1)

    # Compose the target relative path (browsers may send a full client path)
    name = (file.filename or "upload").replace("\\", "/").rsplit("/", 1)[-1] or "upload"
    rel = f"{folder.strip('/')}/{name}".lstrip("/") if folder.strip("/") else name

    try:
        result = await asyncio.to_thread(save_upload, root, slug, rel, data)
    except ExamGroupError as exc:
        raise _exam_error_to_http(exc) from exc
    return result


@router.delete("/{workspace_id}/groups/{slug}/files", status_code=204)
async def delete_group_file(
    workspace_id: str,
    slug: str,
    path: str = Query(..., description="Relative path of the file to delete"),
) -> None:
    root = _workspace_root(workspace_id)
    try:
        await asyncio.to_thread(delete_file, root, slug, path)
    except ExamGroupError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc


# ---------------------------------------------------------------------------
# Per-workspace course settings
# ---------------------------------------------------------------------------


@router.get("/{workspace_id}/settings")
async def get_workspace_course_settings(workspace_id: str) -> dict:
    _workspace_root(workspace_id)  # 404 if unknown
    settings = await asyncio.to_thread(get_course_settings, workspace_id)
    return {"settings": settings}


@router.put("/{workspace_id}/settings")
async def put_workspace_course_settings(workspace_id: str, payload: dict) -> dict:
    _workspace_root(workspace_id)
    default_persona = str(payload.get("default_persona") or "")
    settings = await asyncio.to_thread(set_course_settings, workspace_id, default_persona)
    return {"settings": settings}


# ---------------------------------------------------------------------------
# Workspace instructions & course prompt metadata
# ---------------------------------------------------------------------------

_BASE_PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "agents" / "chat" / "prompts" / "en" / "agentic_chat.yaml"
)
_EXAM_PREP_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2] / "services" / "course" / "templates" / "exam_prep_instructions.md"
)


@functools.lru_cache(maxsize=1)
def _load_base_prompt() -> str:
    if not _BASE_PROMPT_PATH.exists():
        return ""
    try:
        with open(_BASE_PROMPT_PATH, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, dict):
            return str(data.get("general") or "").strip()
    except Exception:
        logger.warning("Could not read base prompt from %s", _BASE_PROMPT_PATH, exc_info=True)
    return ""


@functools.lru_cache(maxsize=1)
def _load_exam_prep_template() -> str:
    if not _EXAM_PREP_TEMPLATE_PATH.exists():
        return ""
    try:
        return _EXAM_PREP_TEMPLATE_PATH.read_text(encoding="utf-8")
    except Exception:
        logger.warning(
            "Could not read exam prep template from %s",
            _EXAM_PREP_TEMPLATE_PATH,
            exc_info=True,
        )
    return ""


@router.get("/{workspace_id}/instructions")
async def get_workspace_instructions(workspace_id: str) -> dict:
    _workspace_root(workspace_id)
    svc = get_content_workspace_service()
    workspace_instructions = await asyncio.to_thread(svc.workspace_instructions, workspace_id)
    settings = await asyncio.to_thread(get_course_settings, workspace_id)
    return {
        "base_prompt": _load_base_prompt(),
        "workspace_instructions": workspace_instructions,
        "max_instructions_chars": MAX_WORKSPACE_INSTRUCTIONS_CHARS,
        "default_persona": settings.get("default_persona", ""),
        "exam_prep_template": _load_exam_prep_template(),
    }

