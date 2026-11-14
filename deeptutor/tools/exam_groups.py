# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Universal tool for inspecting, creating, and updating course exam groups."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.services.course.exam_groups import (
    ExamGroupError,
    create_group,
    file_tree,
    get_group,
    list_groups,
    update_group,
)
from deeptutor.services.workspace import WorkspaceError, get_content_workspace_service

logger = logging.getLogger(__name__)


def _binding(kwargs: dict[str, Any]):
    service = get_content_workspace_service()
    workspace_id = str(kwargs.get("_workspace_id") or "")
    if not workspace_id:
        # The request's course scope (?dt_workspace=), not the globally active one.
        from deeptutor.services.workspace.context import current_workspace_id

        workspace_id = current_workspace_id() or ""
    return service, (
        service.binding_by_id(workspace_id) if workspace_id else service.current_binding()
    )


_TAGGING_ACTIONS = {"get", "create", "update", "update_topics"}


async def _tag_session(kwargs: dict[str, Any], action: str, result: ToolResult) -> None:
    """File the conversation under the exam group it is working on (sidebar grouping)."""
    session_id = str(kwargs.get("_session_id") or "")
    meta = result.metadata if isinstance(result.metadata, dict) else {}
    slug = str(meta.get("slug") or "")
    if not session_id or not slug or not result.success or action not in _TAGGING_ACTIONS:
        return
    try:
        from deeptutor.services.session import get_session_store

        await get_session_store().update_session_preferences(
            session_id,
            {"exam_group": slug, "exam_group_name": str(meta.get("name") or slug)},
            touch=False,
        )
    except Exception:
        logger.debug("could not tag session %s with exam group %s", session_id, slug, exc_info=True)


def _relativize_tree(nodes: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    """Recursively prefix paths in the file tree with prefix (e.g. 'exams/<slug>')."""
    out: list[dict[str, Any]] = []
    for node in nodes:
        entry = dict(node)
        rel = node.get("path", "")
        entry["path"] = f"{prefix}/{rel}" if rel else prefix
        if "children" in node and isinstance(node["children"], list):
            entry["children"] = _relativize_tree(node["children"], prefix)
        out.append(entry)
    return out


class ExamGroupsTool(BaseTool):
    """Tool for managing exam groups in the active course workspace."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="exam_groups",
            description=(
                "Exam groups are folders exams/<slug>/ with EXAM.md containing syllabus and progress metadata. "
                "Use this tool for upcoming exams together with the exam-prep skill to list, inspect, create, "
                "or update exam groups and their topic progress."
            ),
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="Operation to perform: list, get, create, update, or update_topics.",
                    enum=["list", "get", "create", "update", "update_topics"],
                    required=True,
                ),
                ToolParameter(
                    name="slug",
                    type="string",
                    description="Folder slug of the exam group (e.g. 'ct-02'). Required for get, update, and update_topics.",
                    required=False,
                ),
                ToolParameter(
                    name="name",
                    type="string",
                    description="Display name for the exam group (e.g. 'CT-02', 'Mid-term'). Required for create.",
                    required=False,
                ),
                ToolParameter(
                    name="type",
                    type="string",
                    description="Exam type: class_test, quiz, viva, mid_term, term_final, assignment, or other.",
                    enum=["class_test", "quiz", "viva", "mid_term", "term_final", "assignment", "other"],
                    required=False,
                ),
                ToolParameter(
                    name="date",
                    type="string",
                    description="Exam date in ISO format YYYY-MM-DD, or empty string.",
                    required=False,
                ),
                ToolParameter(
                    name="status",
                    type="string",
                    description="Preparation status: planned, preparing, or done.",
                    enum=["planned", "preparing", "done"],
                    required=False,
                ),
                ToolParameter(
                    name="syllabus",
                    type="string",
                    description="Markdown text describing the exam syllabus and scope.",
                    required=False,
                ),
                ToolParameter(
                    name="topics",
                    type="array",
                    description="Array of topic objects with 'title' and 'status' (todo|learning|known|skipped).",
                    items={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["todo", "learning", "known", "skipped"],
                            },
                        },
                        "required": ["title", "status"],
                    },
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            res = _binding(kwargs)
            if isinstance(res, tuple):
                _, binding = res
            else:
                binding = res
            root = getattr(binding, "root", binding)
            if not isinstance(root, Path):
                root = Path(root)
        except WorkspaceError as exc:
            return ToolResult(content=f"Workspace error: {exc}", success=False, metadata={"error": str(exc)})
        except Exception as exc:
            return ToolResult(content=f"Workspace error: {exc}", success=False, metadata={"error": str(exc)})

        action = str(kwargs.get("action") or "").strip()
        if not action:
            return ToolResult(
                content="action parameter is required (list, get, create, update, update_topics).",
                success=False,
                metadata={"error": "missing action"},
            )

        try:
            result = await asyncio.to_thread(self._run_action, root, action, kwargs)
            await _tag_session(kwargs, action, result)
            return result
        except ExamGroupError as exc:
            return ToolResult(content=f"Exam group error: {exc}", success=False, metadata={"error": str(exc)})
        except WorkspaceError as exc:
            return ToolResult(content=f"Workspace error: {exc}", success=False, metadata={"error": str(exc)})
        except Exception as exc:
            logger.exception("Unexpected error in exam_groups tool")
            return ToolResult(content=f"Error: {exc}", success=False, metadata={"error": str(exc)})

    def _run_action(self, root: Path, action: str, kwargs: dict[str, Any]) -> ToolResult:
        if action == "list":
            groups = list_groups(root)
            compact = [
                {
                    "slug": g["slug"],
                    "name": g["name"],
                    "type": g["type"],
                    "date": g["date"],
                    "status": g["status"],
                    "progress": g["progress"],
                    "file_count": g["file_count"],
                }
                for g in groups
            ]
            return ToolResult(
                content=json.dumps(compact, ensure_ascii=False, indent=2),
                metadata={"groups": compact},
            )

        if action == "get":
            slug = str(kwargs.get("slug") or "").strip()
            if not slug:
                raise ExamGroupError("slug is required for get.")
            group = get_group(root, slug)
            tree = file_tree(root, slug)
            rel_tree = _relativize_tree(tree, f"exams/{slug}")
            payload = dict(group)
            payload["file_tree"] = rel_tree
            payload["files"] = rel_tree
            return ToolResult(
                content=json.dumps(payload, ensure_ascii=False, indent=2),
                metadata=payload,
            )

        if action == "create":
            name = str(kwargs.get("name") or "").strip()
            if not name:
                raise ExamGroupError("name is required for create.")
            exam_type = str(kwargs.get("type") or "other")
            date = str(kwargs.get("date") or "")
            syllabus = str(kwargs.get("syllabus") or "")
            group = create_group(root, name=name, exam_type=exam_type, date=date, syllabus=syllabus)

            extra_updates: dict[str, Any] = {}
            if "status" in kwargs and kwargs["status"]:
                extra_updates["status"] = kwargs["status"]
            if "topics" in kwargs and kwargs["topics"] is not None:
                extra_updates["topics"] = kwargs["topics"]
            if extra_updates:
                group = update_group(root, group["slug"], **extra_updates)

            return ToolResult(
                content=json.dumps(group, ensure_ascii=False, indent=2),
                metadata=group,
            )

        if action == "update":
            slug = str(kwargs.get("slug") or "").strip()
            if not slug:
                raise ExamGroupError("slug is required for update.")
            allowed = ("name", "type", "date", "status", "syllabus", "topics")
            fields = {k: kwargs[k] for k in allowed if k in kwargs and kwargs[k] is not None}
            group = update_group(root, slug, **fields)
            return ToolResult(
                content=json.dumps(group, ensure_ascii=False, indent=2),
                metadata=group,
            )

        if action == "update_topics":
            slug = str(kwargs.get("slug") or "").strip()
            if not slug:
                raise ExamGroupError("slug is required for update_topics.")
            incoming = kwargs.get("topics")
            if not isinstance(incoming, list):
                raise ExamGroupError("'topics' must be a list of objects with 'title' and 'status'.")

            current = get_group(root, slug)
            existing_topics: list[dict[str, Any]] = list(current.get("topics") or [])

            incoming_map: dict[str, dict[str, Any]] = {}
            for item in incoming:
                if not isinstance(item, dict):
                    raise ExamGroupError("Each topic must be a dict with 'title' and 'status'.")
                title = str(item.get("title") or "").strip()
                if not title:
                    raise ExamGroupError("Topic title must not be empty.")
                status = str(item.get("status") or "").strip()
                if not status:
                    raise ExamGroupError(f"Topic {title!r} must have a status.")
                incoming_map[title.lower()] = {"title": title, "status": status}

            merged: list[dict[str, Any]] = []
            seen: set[str] = set()

            for t in existing_topics:
                t_title = str(t.get("title") or "")
                key = t_title.strip().lower()
                if key in incoming_map:
                    merged.append({"title": t_title, "status": incoming_map[key]["status"]})
                    seen.add(key)
                else:
                    merged.append({"title": t_title, "status": str(t.get("status") or "todo")})
                    seen.add(key)

            for item in incoming:
                title = str(item.get("title") or "").strip()
                key = title.lower()
                if key not in seen:
                    merged.append({"title": title, "status": str(item.get("status") or "todo")})
                    seen.add(key)

            updated = update_group(root, slug, topics=merged)
            return ToolResult(
                content=json.dumps(updated, ensure_ascii=False, indent=2),
                metadata=updated,
            )

        raise ExamGroupError(
            f"Unknown action {action!r}. Must be one of: list, get, create, update, update_topics."
        )
