# Modified in the RH.RONY fork (Apache-2.0 §4b): add folder tree support to write_note, NoteTreeTool, MoveNoteTool
import copy
import json

# fork(course_workspaces) start
from deeptutor.capabilities.notes.tree import move_page, render_tree, resolve_folder

# fork(course_workspaces) end
from deeptutor.co_writer.storage import get_co_writer_storage
from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.notes.proposals import propose


class NoteReadTool(BaseTool):
    def get_definition(self):
        return ToolDefinition(
            name="note_read",
            description="Read the open notebook page with block IDs, structure and Markdown. Large pages return an outline; read a specific block_id to inspect its body.",
            parameters=[
                ToolParameter(
                    name="block_id",
                    type="string",
                    description="Optional block ID to read",
                    required=False,
                )
            ],
        )

    async def execute(self, **kwargs):
        if not kwargs.get("_note_document_id"):
            return ToolResult(content="No notebook page is bound to this turn", success=False)
        try:
            doc = get_co_writer_storage().load_document(kwargs["_note_document_id"])
            if doc is None:
                raise ValueError("Page not found")
            from deeptutor.notes.blocks import walk_blocks

            state = kwargs.get("_note_read_state")
            if isinstance(state, dict):
                for block in walk_blocks(doc.blocks):
                    if not kwargs.get("block_id") or block["id"] == kwargs["block_id"]:
                        state[block["id"]] = copy.deepcopy(block)

            if kwargs.get("block_id"):
                target = next(
                    (b for b in walk_blocks(doc.blocks) if b["id"] == kwargs["block_id"]), None
                )
                if target is None:
                    raise ValueError("Block not found")
                payload = {"page_id": doc.id, "revision": doc.revision, "block": target}
            elif len(json.dumps(doc.blocks)) > 80000:
                payload = {
                    "id": doc.id,
                    "title": doc.title,
                    "revision": doc.revision,
                    "outline": [
                        {
                            "id": b["id"],
                            "type": b["type"],
                            "preview": str(b.get("content", b.get("props", {})))[:300],
                        }
                        for b in walk_blocks(doc.blocks)
                    ],
                }
            else:
                payload = doc.model_dump()
            return ToolResult(content=json.dumps(payload, ensure_ascii=False), success=True)
        except ValueError as exc:
            return ToolResult(content=str(exc), success=False)


class NoteSuggestTool(BaseTool):
    def get_definition(self):
        return ToolDefinition(
            name="note_suggest",
            description="Propose a block edit or teaching comment for user review. Does not change the page until accepted. Text-only parent replacements preserve existing child blocks; propose deletions of children separately.",
            parameters=[
                ToolParameter(
                    name="operation",
                    type="string",
                    description="Edit operation",
                    enum=["insert", "replace", "delete", "comment"],
                ),
                ToolParameter(
                    name="block_id",
                    type="string",
                    description="Target block ID; empty inserts at the end",
                    required=False,
                ),
                ToolParameter(
                    name="markdown",
                    type="string",
                    description="Suggested content in Markdown",
                    required=False,
                ),
                ToolParameter(
                    name="blocks",
                    type="array",
                    items={"type": "object"},
                    description="Optional complete BlockNote blocks, each with unique id, type, props, content and children. For interactive learning blocks use type learning, props kind (quiz or flashcards), data (JSON string with questions [{question, options, correct_answer, explanation}] or cards [{front, back}]), markdown (plain text projection), prompt. Timeline data uses events [{date,title,description}]; concept_map uses nodes and edges. Visualizations use kind=visualization and the complete validated visualization result in data. Media uses kind=media and workspace_items from the producing tool. Run code with exec only if mounted and report real output as a comment. Use Markdown for ordinary prose.",
                    required=False,
                ),
                ToolParameter(
                    name="explanation",
                    type="string",
                    description="Why this edit, or teaching feedback with sources",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs):
        if not kwargs.get("_note_document_id"):
            return ToolResult(content="No notebook page is bound to this turn", success=False)
        try:
            block_id = kwargs.get("block_id", "")
            expected = {}
            if block_id:
                state = kwargs.get("_note_read_state", {})
                if block_id not in state:
                    raise ValueError(
                        "Use note_read to read the target block before suggesting changes"
                    )
                expected["expected_original"] = state[block_id]
            result = propose(
                get_co_writer_storage(),
                kwargs["_note_document_id"],
                operation=kwargs["operation"],
                block_id=kwargs.get("block_id", ""),
                markdown=kwargs.get("markdown", ""),
                explanation=kwargs.get("explanation", ""),
                blocks=kwargs.get("blocks"),
                workspace_id=str(kwargs.get("_workspace_id") or ""),
                **expected,
            )
            return ToolResult(
                content=json.dumps(
                    {"suggestion_id": result["id"], "status": "pending_user_review"}
                ),
                success=True,
            )
        except (ValueError, KeyError) as exc:
            return ToolResult(content=str(exc), success=False)


class WriteNoteTool(BaseTool):
    def get_definition(self):
        return ToolDefinition(
            name="write_note",
            # fork(course_workspaces) start
            description="Create an authored notebook page, optionally filed in a folder tree. To preserve an original conversation use save_favorite. Existing pages are edited through reviewable note_suggest in their editor.",
            parameters=[
                ToolParameter(name="title", type="string", description="Page title"),
                ToolParameter(
                    name="content",
                    type="string",
                    description="Full authored Markdown, preserving citations and source links",
                ),
                ToolParameter(
                    name="parent_id",
                    type="string",
                    description="Optional parent page ID to file this note under",
                    required=False,
                ),
                ToolParameter(
                    name="folder",
                    type="string",
                    description="Optional folder path like 'CT-02/Chapter 1', created on demand under parent_id if both are given",
                    required=False,
                ),
            ],
            # fork(course_workspaces) end
        )

    async def execute(self, **kwargs):
        title, content = str(kwargs.get("title", "")), str(kwargs.get("content", ""))
        if not title.strip() or not content.strip() or len(content) > 200000:
            return ToolResult(
                content="Provide a title and content (up to 200000 characters)", success=False
            )
        # fork(course_workspaces) start
        parent_id = kwargs.get("parent_id")
        if parent_id is not None:
            parent_id = str(parent_id).strip() or None
        folder = kwargs.get("folder")
        if folder is not None:
            folder = str(folder).strip() or None

        storage = get_co_writer_storage()
        try:
            resolved_parent_id = parent_id
            if folder:
                resolved_parent_id = resolve_folder(storage, folder, parent_id=parent_id)
            elif resolved_parent_id:
                try:
                    parent_doc = storage.load_document(resolved_parent_id)
                except ValueError:
                    parent_doc = None
                if parent_doc is None:
                    return ToolResult(
                        content=f"Parent page '{resolved_parent_id}' does not exist",
                        success=False,
                    )
            doc = storage.create_document(
                title=title[:200], content=content, parent_id=resolved_parent_id
            )
            return ToolResult(
                content=json.dumps(
                    {
                        "id": doc.id,
                        "title": doc.title,
                        "url": f"/co-writer/{doc.id}",
                        "parent_id": doc.parent_id,
                        "folder": folder or "",
                    },
                    ensure_ascii=False,
                ),
                success=True,
            )
        except ValueError as exc:
            return ToolResult(content=str(exc), success=False)
        # fork(course_workspaces) end


class SearchNotesTool(BaseTool):
    def get_definition(self):
        return ToolDefinition(
            name="search_notes",
            description="Find authored notebook pages by title or full text; returns excerpts and page links. Empty query lists recent pages. Read a whole page with page_id.",
            parameters=[
                ToolParameter(
                    name="query", type="string", description="Text to find", required=False
                ),
                ToolParameter(
                    name="page_id", type="string", description="Page ID to read", required=False
                ),
            ],
        )

    async def execute(self, **kwargs):
        storage = get_co_writer_storage()
        try:
            if kwargs.get("page_id"):
                doc = storage.load_document(kwargs["page_id"])
                return ToolResult(
                    content=json.dumps(
                        {"title": doc.title, "content": doc.content}
                        if doc
                        else {"error": "Page not found"},
                        ensure_ascii=False,
                    ),
                    success=doc is not None,
                )
            query = str(kwargs.get("query", "")).casefold()
            results = []
            for summary in storage.list_documents():
                doc = storage.load_document(summary.id)
                if doc is None:
                    continue
                text = doc.title + "\n" + doc.content
                pos = text.casefold().find(query)
                if pos >= 0:
                    results.append(
                        {
                            "id": doc.id,
                            "title": doc.title,
                            "excerpt": text[max(0, pos - 100) : pos + 600],
                            "url": f"/co-writer/{doc.id}",
                        }
                    )
                if len(results) >= 20:
                    break
            return ToolResult(content=json.dumps(results, ensure_ascii=False), success=True)
        except ValueError as exc:
            return ToolResult(content=str(exc), success=False)


# fork(course_workspaces) start
class NoteTreeTool(BaseTool):
    def get_definition(self):
        return ToolDefinition(
            name="note_tree",
            description="Show the notes workspace as an indented folder tree outline. Specify page_id to view only a specific subtree.",
            parameters=[
                ToolParameter(
                    name="page_id",
                    type="string",
                    description="Optional page ID to show only its subtree",
                    required=False,
                )
            ],
        )

    async def execute(self, **kwargs):
        storage = get_co_writer_storage()
        page_id = kwargs.get("page_id")
        if page_id is not None:
            page_id = str(page_id).strip() or None
        try:
            tree_text = render_tree(storage, root_id=page_id)
            return ToolResult(content=tree_text, success=True)
        except ValueError as exc:
            return ToolResult(content=str(exc), success=False)


class MoveNoteTool(BaseTool):
    def get_definition(self):
        return ToolDefinition(
            name="move_note",
            description="Move a notebook page to a new parent folder or to the top level. Provide parent_id or folder, or leave both empty to move to top level.",
            parameters=[
                ToolParameter(
                    name="page_id",
                    type="string",
                    description="Page ID to move",
                    required=True,
                ),
                ToolParameter(
                    name="parent_id",
                    type="string",
                    description="Target parent page ID. Leave empty (with folder empty) to move to top level.",
                    required=False,
                ),
                ToolParameter(
                    name="folder",
                    type="string",
                    description="Target folder path like 'CT-02/Chapter 1', created on demand under parent_id if both given.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs):
        page_id = str(kwargs.get("page_id", "")).strip()
        if not page_id:
            return ToolResult(content="page_id is required", success=False)
        parent_id = kwargs.get("parent_id")
        if parent_id is not None:
            parent_id = str(parent_id).strip() or None
        folder = kwargs.get("folder")
        if folder is not None:
            folder = str(folder).strip() or None

        storage = get_co_writer_storage()
        try:
            target_parent_id = parent_id
            if folder:
                target_parent_id = resolve_folder(storage, folder, parent_id=parent_id)
            move_page(storage, page_id, target_parent_id)
            return ToolResult(
                content=json.dumps(
                    {"id": page_id, "parent_id": target_parent_id, "status": "moved"},
                    ensure_ascii=False,
                ),
                success=True,
            )
        except ValueError as exc:
            return ToolResult(content=str(exc), success=False)
# fork(course_workspaces) end
