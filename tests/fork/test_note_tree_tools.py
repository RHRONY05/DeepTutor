# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
from __future__ import annotations

import json
from pathlib import Path

import pytest

from deeptutor.capabilities.notes.tools import MoveNoteTool, NoteTreeTool, WriteNoteTool
from deeptutor.capabilities.notes.tree import move_page, render_tree, resolve_folder
from deeptutor.co_writer.storage import CoWriterStorage


class FakePaths:
    """Fake path service pointing to a temporary directory."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def get_co_writer_docs_dir(self) -> Path:
        return self.root / "documents"

    def get_co_writer_doc_root(self, did: str) -> Path:
        return self.get_co_writer_docs_dir() / f"doc_{did}"

    def get_co_writer_doc_manifest(self, did: str) -> Path:
        return self.get_co_writer_doc_root(did) / "manifest.json"


@pytest.fixture
def store(tmp_path: Path) -> CoWriterStorage:
    return CoWriterStorage(FakePaths(tmp_path))


@pytest.fixture(autouse=True)
def bind_storage(monkeypatch: pytest.MonkeyPatch, store: CoWriterStorage) -> None:
    monkeypatch.setattr(
        "deeptutor.capabilities.notes.tools.get_co_writer_storage",
        lambda: store,
    )


class TestResolveFolder:
    def test_creates_missing_pages_once_and_is_idempotent(self, store: CoWriterStorage) -> None:
        # First call creates missing hierarchy
        leaf_id = resolve_folder(store, "CT-02/Chapter 1")
        assert leaf_id is not None

        docs = store.list_documents()
        assert len(docs) == 2

        doc_by_title = {d.title: d for d in docs}
        assert "CT-02" in doc_by_title
        assert "Chapter 1" in doc_by_title
        assert doc_by_title["CT-02"].parent_id is None
        assert doc_by_title["Chapter 1"].parent_id == doc_by_title["CT-02"].id
        assert leaf_id == doc_by_title["Chapter 1"].id

        # Second call reuses existing pages case-insensitively
        leaf_id_2 = resolve_folder(store, "ct-02/chapter 1")
        assert leaf_id_2 == leaf_id
        assert len(store.list_documents()) == 2

    def test_parent_id_honoured_and_combined_with_folder(self, store: CoWriterStorage) -> None:
        root = store.create_document(title="CSE301", content="Course overview")
        folder_leaf = resolve_folder(store, "Labs/Lab 01", parent_id=root.id)

        doc_map = {d.id: d for d in store.list_documents()}
        leaf_doc = doc_map[folder_leaf]
        assert leaf_doc.title == "Lab 01"

        labs_doc = doc_map[leaf_doc.parent_id]
        assert labs_doc.title == "Labs"
        assert labs_doc.parent_id == root.id

    def test_unknown_parent_raises_value_error(self, store: CoWriterStorage) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            resolve_folder(store, "Subfolder", parent_id="bad_parent_123")

    def test_empty_folder_returns_parent_id(self, store: CoWriterStorage) -> None:
        assert resolve_folder(store, "") is None
        assert resolve_folder(store, "  ///  ") is None

        root = store.create_document(title="Root", content="")
        assert resolve_folder(store, "", parent_id=root.id) == root.id

    def test_max_depth_exceeded_raises_value_error(self, store: CoWriterStorage) -> None:
        deep_path = "/".join(f"level_{i}" for i in range(9))
        with pytest.raises(ValueError, match="exceed 8 levels"):
            resolve_folder(store, deep_path)

    def test_segment_max_length_exceeded_raises_value_error(self, store: CoWriterStorage) -> None:
        long_seg = "a" * 201
        with pytest.raises(ValueError, match="exceeds maximum length"):
            resolve_folder(store, f"normal/{long_seg}")


class TestWriteNoteTool:
    @pytest.mark.asyncio
    async def test_write_note_honours_parent_id(self, store: CoWriterStorage) -> None:
        parent = store.create_document(title="Topic", content="")
        tool = WriteNoteTool()
        result = await tool.execute(
            title="Summary",
            content="Key findings",
            parent_id=parent.id,
        )
        assert result.success is True
        data = json.loads(result.content)
        assert data["title"] == "Summary"
        assert data["parent_id"] == parent.id

        doc = store.load_document(data["id"])
        assert doc is not None
        assert doc.parent_id == parent.id

    @pytest.mark.asyncio
    async def test_write_note_with_folder(self, store: CoWriterStorage) -> None:
        tool = WriteNoteTool()
        result = await tool.execute(
            title="Lecture 1",
            content="Intro to AI",
            folder="AI/Week 1",
        )
        assert result.success is True
        data = json.loads(result.content)
        assert data["folder"] == "AI/Week 1"

        doc = store.load_document(data["id"])
        assert doc is not None

        # Parent should be Week 1
        parent = store.load_document(doc.parent_id)
        assert parent is not None
        assert parent.title == "Week 1"

        # Grandparent should be AI
        grandparent = store.load_document(parent.parent_id)
        assert grandparent is not None
        assert grandparent.title == "AI"
        assert grandparent.parent_id is None

    @pytest.mark.asyncio
    async def test_write_note_unknown_parent_returns_friendly_error(self) -> None:
        tool = WriteNoteTool()
        result = await tool.execute(
            title="Note",
            content="Content",
            parent_id="unknown_parent_999",
        )
        assert result.success is False
        assert "does not exist" in result.content


class TestRenderTree:
    def test_tree_rendering_outline_and_sorting(self, store: CoWriterStorage) -> None:
        # Create hierarchy
        # Z-Topic
        #   - Sub-2
        #   - Sub-1
        # A-Topic
        z = store.create_document(title="Z-Topic", content="")
        s2 = store.create_document(title="Sub-2", content="", parent_id=z.id)
        s1 = store.create_document(title="Sub-1", content="", parent_id=z.id)
        a = store.create_document(title="A-Topic", content="")

        rendered = render_tree(store)
        lines = rendered.splitlines()

        # A-Topic sorted before Z-Topic
        assert lines[0] == f"- A-Topic  [{a.id}]"
        assert lines[1] == f"- Z-Topic  [{z.id}]"
        # Sub-1 sorted before Sub-2
        assert lines[2] == f"  - Sub-1  [{s1.id}]"
        assert lines[3] == f"  - Sub-2  [{s2.id}]"

    def test_tree_rendering_treats_missing_parent_as_top_level(
        self, store: CoWriterStorage
    ) -> None:
        orphan = store.create_document(title="Orphan", content="")
        # Manually alter parent_id to point to non-existent document
        orphan.parent_id = "missing_id_123"
        store._write(orphan)

        rendered = render_tree(store)
        assert f"- Orphan  [{orphan.id}]" in rendered

    def test_tree_rendering_subtree(self, store: CoWriterStorage) -> None:
        root = store.create_document(title="Root", content="")
        child = store.create_document(title="Child", content="", parent_id=root.id)
        _other = store.create_document(title="Other", content="")

        rendered = render_tree(store, root_id=root.id)
        assert f"- Root  [{root.id}]" in rendered
        assert f"  - Child  [{child.id}]" in rendered
        assert "Other" not in rendered

    @pytest.mark.asyncio
    async def test_note_tree_tool(self, store: CoWriterStorage) -> None:
        doc = store.create_document(title="Single", content="")
        tool = NoteTreeTool()
        result = await tool.execute()
        assert result.success is True
        assert f"- Single  [{doc.id}]" in result.content

        # Subtree of nonexistent
        bad_result = await tool.execute(page_id="nonexistent")
        assert bad_result.success is False
        assert "not found" in bad_result.content


class TestMovePage:
    def test_move_page_to_another_parent(self, store: CoWriterStorage) -> None:
        p1 = store.create_document(title="Page 1", content="")
        p2 = store.create_document(title="Page 2", content="")

        move_page(store, p1.id, p2.id)

        loaded_1 = store.load_document(p1.id)
        assert loaded_1.parent_id == p2.id

    def test_move_page_to_top_level(self, store: CoWriterStorage) -> None:
        p1 = store.create_document(title="Page 1", content="")
        p2 = store.create_document(title="Page 2", content="", parent_id=p1.id)

        assert p2.parent_id == p1.id
        move_page(store, p2.id, None)

        loaded_2 = store.load_document(p2.id)
        assert loaded_2.parent_id is None

    def test_move_page_cycle_rejected(self, store: CoWriterStorage) -> None:
        # A -> B -> C
        a = store.create_document(title="A", content="")
        b = store.create_document(title="B", content="", parent_id=a.id)
        c = store.create_document(title="C", content="", parent_id=b.id)

        # Attempting to move A under C must fail
        with pytest.raises(ValueError, match="creates a cycle"):
            move_page(store, a.id, c.id)

        # A cannot be its own parent
        with pytest.raises(ValueError, match="own parent"):
            move_page(store, a.id, a.id)

    @pytest.mark.asyncio
    async def test_move_note_tool(self, store: CoWriterStorage) -> None:
        tool = MoveNoteTool()
        p1 = store.create_document(title="Note 1", content="")

        # Move to folder
        result = await tool.execute(page_id=p1.id, folder="Archive/2026")
        assert result.success is True
        data = json.loads(result.content)
        assert data["id"] == p1.id
        assert data["status"] == "moved"

        doc = store.load_document(p1.id)
        assert doc.parent_id is not None
        folder_doc = store.load_document(doc.parent_id)
        assert folder_doc.title == "2026"

        # Move to top level
        result_top = await tool.execute(page_id=p1.id)
        assert result_top.success is True
        doc_top = store.load_document(p1.id)
        assert doc_top.parent_id is None

        # Cycle rejected via tool
        child = store.create_document(title="Child", content="", parent_id=p1.id)
        result_cycle = await tool.execute(page_id=p1.id, parent_id=child.id)
        assert result_cycle.success is False
        assert "cycle" in result_cycle.content or "themselves" in result_cycle.content
