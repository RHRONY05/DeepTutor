# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
from __future__ import annotations

from collections import defaultdict
from typing import Any


def resolve_folder(storage: Any, folder: str, parent_id: str | None = None) -> str | None:
    """Resolve a slash-delimited folder path into a hierarchy of note pages.

    Missing segments are created on demand under the current parent. Returns
    the page ID of the final folder segment, or parent_id if folder is empty.
    """
    current_parent = str(parent_id).strip() or None if parent_id is not None else None
    if current_parent is not None:
        try:
            parent_doc = storage.load_document(current_parent)
        except ValueError:
            parent_doc = None
        if parent_doc is None:
            raise ValueError(f"Parent page '{current_parent}' does not exist")

    folder_str = str(folder).strip() if folder is not None else ""
    if not folder_str:
        return current_parent

    segments = [seg.strip() for seg in folder_str.split("/") if seg.strip()]
    if not segments:
        return current_parent

    if len(segments) > 8:
        raise ValueError("Folder depth cannot exceed 8 levels")

    for seg in segments:
        if len(seg) > 200:
            raise ValueError(f"Folder segment '{seg[:30]}...' exceeds maximum length of 200 characters")

    for seg in segments:
        matching_child_id: str | None = None
        for doc in storage.list_documents():
            if doc.parent_id == current_parent and (doc.title or "").strip().casefold() == seg.casefold():
                matching_child_id = doc.id
                break
        if matching_child_id is not None:
            current_parent = matching_child_id
        else:
            new_doc = storage.create_document(title=seg, content="", parent_id=current_parent)
            current_parent = new_doc.id

    return current_parent


def render_tree(storage: Any, root_id: str | None = None) -> str:
    """Render an indented outline of notes in the workspace.

    Format: '- Title  [id]' sorted by title, children under parents.
    Pages whose parent is missing are treated as top level. If root_id is
    provided, only that subtree is rendered.
    """
    target_root = str(root_id).strip() or None if root_id is not None else None
    root_doc = None
    if target_root is not None:
        try:
            root_doc = storage.load_document(target_root)
        except ValueError:
            root_doc = None
        if root_doc is None:
            raise ValueError(f"Page '{target_root}' not found")

    docs = storage.list_documents()
    doc_map = {d.id: d for d in docs}
    if root_doc is not None and root_doc.id not in doc_map:
        doc_map[root_doc.id] = root_doc

    children_by_parent: dict[str | None, list[Any]] = defaultdict(list)
    for d in doc_map.values():
        parent_key = d.parent_id if (d.parent_id and d.parent_id in doc_map) else None
        children_by_parent[parent_key].append(d)

    for key in children_by_parent:
        children_by_parent[key].sort(key=lambda d: ((d.title or "").casefold(), d.id))

    lines: list[str] = []
    seen: set[str] = set()

    def _render_children(parent_id: str, depth: int) -> None:
        for child in children_by_parent.get(parent_id, []):
            if child.id in seen:
                continue
            seen.add(child.id)
            title = (child.title or "Untitled").strip().replace("\n", " ")
            indent = "  " * depth
            lines.append(f"{indent}- {title}  [{child.id}]")
            _render_children(child.id, depth + 1)

    if target_root is not None and root_doc is not None:
        seen.add(root_doc.id)
        title = (root_doc.title or "Untitled").strip().replace("\n", " ")
        lines.append(f"- {title}  [{root_doc.id}]")
        _render_children(root_doc.id, 1)
    else:
        for top_doc in children_by_parent.get(None, []):
            if top_doc.id in seen:
                continue
            seen.add(top_doc.id)
            title = (top_doc.title or "Untitled").strip().replace("\n", " ")
            lines.append(f"- {title}  [{top_doc.id}]")
            _render_children(top_doc.id, 1)

    return "\n".join(lines)


def move_page(storage: Any, page_id: str, new_parent_id: str | None = None) -> Any:
    """Move a page to a new parent or to the top level (new_parent_id=None)."""
    pid = str(page_id).strip() if page_id is not None else ""
    if not pid:
        raise ValueError("page_id is required")

    new_parent = str(new_parent_id).strip() or None if new_parent_id is not None else None

    if pid == new_parent:
        raise ValueError("A page cannot be its own parent")

    try:
        doc = storage.load_document(pid)
    except ValueError:
        doc = None
    if doc is None:
        raise ValueError(f"Page '{pid}' does not exist")

    if new_parent is not None:
        try:
            parent_doc = storage.load_document(new_parent)
        except ValueError:
            parent_doc = None
        if parent_doc is None:
            raise ValueError(f"Target parent page '{new_parent}' does not exist")

    try:
        updated = storage.update_document(pid, parent_id=new_parent)
    except ValueError as exc:
        if "Pages cannot contain themselves" in str(exc):
            raise ValueError(
                f"Cannot move page '{pid}' under '{new_parent}': creates a cycle"
            ) from exc
        raise

    if updated is None:
        raise ValueError(f"Page '{pid}' does not exist")
    return updated


__all__ = [
    "move_page",
    "render_tree",
    "resolve_folder",
]
