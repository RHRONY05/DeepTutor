# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Unit tests for deeptutor.services.course.exam_groups."""

from __future__ import annotations

import pytest

from deeptutor.services.course.exam_groups import (
    EXAM_FILE,
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_root(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# create_group
# ---------------------------------------------------------------------------


def test_create_group_basic(tmp_path):
    root = _make_root(tmp_path)
    g = create_group(root, "CT-01", "class_test", "2026-11-20", "Chapter 1")
    assert g["slug"] == "ct-01"
    assert g["name"] == "CT-01"
    assert g["type"] == "class_test"
    assert g["date"] == "2026-11-20"
    assert g["status"] == "planned"
    assert g["syllabus"] == "Chapter 1"
    assert g["topics"] == []
    assert g["progress"] == {"known": 0, "total": 0}
    assert (root / "exams" / "ct-01" / EXAM_FILE).exists()


def test_create_group_empty_name_raises(tmp_path):
    root = _make_root(tmp_path)
    with pytest.raises(ExamGroupError, match="empty"):
        create_group(root, "")


def test_create_group_invalid_type_raises(tmp_path):
    root = _make_root(tmp_path)
    with pytest.raises(ExamGroupError, match="type"):
        create_group(root, "X", exam_type="bad_type")


def test_create_group_invalid_date_raises(tmp_path):
    root = _make_root(tmp_path)
    with pytest.raises(ExamGroupError, match="date"):
        create_group(root, "X", date="20-11-2026")


def test_create_group_slug_uniqueness(tmp_path):
    root = _make_root(tmp_path)
    g1 = create_group(root, "CT-01")
    g2 = create_group(root, "CT-01")
    assert g1["slug"] != g2["slug"]
    assert g2["slug"].startswith("ct-01-")


def test_create_group_slug_max_length(tmp_path):
    root = _make_root(tmp_path)
    long_name = "A" * 100
    g = create_group(root, long_name)
    assert len(g["slug"]) <= 48


def test_create_group_slug_only_valid_chars(tmp_path):
    root = _make_root(tmp_path)
    g = create_group(root, "My Quiz (2026)!")
    import re
    assert re.fullmatch(r"[a-z0-9-]+", g["slug"])


# ---------------------------------------------------------------------------
# EXAM.md round-trip
# ---------------------------------------------------------------------------


def test_exam_md_round_trip(tmp_path):
    root = _make_root(tmp_path)
    topics = [{"title": "Search", "status": "known"}, {"title": "CSP", "status": "todo"}]
    create_group(root, "Mid", "mid_term", "2026-12-01", "Full syllabus here")
    update_group(root, "mid", topics=topics, status="preparing")
    g = get_group(root, "mid")
    assert g["name"] == "Mid"
    assert g["type"] == "mid_term"
    assert g["date"] == "2026-12-01"
    assert g["status"] == "preparing"
    assert g["syllabus"] == "Full syllabus here"
    assert g["topics"] == topics
    assert g["progress"] == {"known": 1, "total": 2}


# ---------------------------------------------------------------------------
# list_groups
# ---------------------------------------------------------------------------


def test_list_groups_empty(tmp_path):
    root = _make_root(tmp_path)
    assert list_groups(root) == []


def test_list_groups_sorted_by_date_then_name(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Beta", date="2026-12-05")
    create_group(root, "Alpha", date="2026-11-20")
    create_group(root, "Zeta", date="")
    groups = list_groups(root)
    slugs = [g["slug"] for g in groups]
    # Alpha < Beta (earlier date), Zeta (no date) last
    assert slugs.index("alpha") < slugs.index("beta")
    assert slugs[-1] == "zeta"


def test_list_groups_folder_without_exam_md(tmp_path):
    root = _make_root(tmp_path)
    # Manually create a folder with no EXAM.md
    orphan = root / "exams" / "orphan"
    orphan.mkdir(parents=True)
    groups = list_groups(root)
    assert len(groups) == 1
    assert groups[0]["slug"] == "orphan"
    assert groups[0]["name"] == "orphan"  # falls back to folder name


# ---------------------------------------------------------------------------
# get_group
# ---------------------------------------------------------------------------


def test_get_group_not_found(tmp_path):
    root = _make_root(tmp_path)
    with pytest.raises(ExamGroupError, match="not found"):
        get_group(root, "nonexistent")


# ---------------------------------------------------------------------------
# update_group
# ---------------------------------------------------------------------------


def test_update_group_name(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Old Name")
    g = update_group(root, "old-name", name="New Name")
    assert g["name"] == "New Name"


def test_update_group_invalid_status_raises(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "X")
    with pytest.raises(ExamGroupError, match="status"):
        update_group(root, "x", status="bad_status")


def test_update_group_invalid_topic_status_raises(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "X")
    with pytest.raises(ExamGroupError, match="topic status"):
        update_group(root, "x", topics=[{"title": "T", "status": "nope"}])


# ---------------------------------------------------------------------------
# delete_group
# ---------------------------------------------------------------------------


def test_delete_group_empty(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "ToDelete")
    delete_group(root, "todelete")
    assert not (root / "exams" / "todelete").exists()


def test_delete_group_non_empty_refuses_without_force(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "ToDelete")
    extra = root / "exams" / "todelete" / "notes.pdf"
    extra.write_bytes(b"data")
    with pytest.raises(ExamGroupError, match="force"):
        delete_group(root, "todelete", force=False)
    assert extra.exists()


def test_delete_group_non_empty_ok_with_force(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "ToDelete")
    extra = root / "exams" / "todelete" / "notes.pdf"
    extra.write_bytes(b"data")
    delete_group(root, "todelete", force=True)
    assert not (root / "exams" / "todelete").exists()


def test_delete_group_not_found_raises(tmp_path):
    root = _make_root(tmp_path)
    with pytest.raises(ExamGroupError, match="not found"):
        delete_group(root, "ghost")


# ---------------------------------------------------------------------------
# save_upload and path safety
# ---------------------------------------------------------------------------


def test_save_upload_basic(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Lab")
    save_upload(root, "lab", "notes.txt", b"hello")
    assert (root / "exams" / "lab" / "notes.txt").read_bytes() == b"hello"


def test_save_upload_with_subfolder(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Lab")
    save_upload(root, "lab", "pyq/2023.pdf", b"pdf-data")
    assert (root / "exams" / "lab" / "pyq" / "2023.pdf").read_bytes() == b"pdf-data"


def test_save_upload_size_cap(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Big")
    too_big = b"x" * (50 * 1024 * 1024 + 1)
    with pytest.raises(ExamGroupError, match="50 MB"):
        save_upload(root, "big", "huge.bin", too_big)


def test_save_upload_traversal_rejected(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Lab")
    with pytest.raises(ExamGroupError):
        save_upload(root, "lab", "../../../etc/passwd", b"evil")


def test_save_upload_absolute_path_rejected(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Lab")
    with pytest.raises(ExamGroupError):
        save_upload(root, "lab", "/etc/passwd", b"evil")


def test_save_upload_reserved_name_rejected(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Lab")
    for name in ("CON", "PRN", "NUL", "COM1", "LPT9", "con.txt", "prn.pdf"):
        with pytest.raises(ExamGroupError):
            save_upload(root, "lab", name, b"data")


def test_save_upload_dot_name_rejected(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Lab")
    with pytest.raises(ExamGroupError):
        save_upload(root, "lab", ".hidden", b"data")


def test_save_upload_exam_md_rejected(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Lab")
    for name in ("EXAM.md", "exam.md", "EXAM.MD"):
        with pytest.raises(ExamGroupError):
            save_upload(root, "lab", name, b"data")


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------


def test_delete_file(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Lab")
    save_upload(root, "lab", "slide.pdf", b"slide")
    delete_file(root, "lab", "slide.pdf")
    assert not (root / "exams" / "lab" / "slide.pdf").exists()


def test_delete_file_not_found(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Lab")
    with pytest.raises(ExamGroupError, match="not found"):
        delete_file(root, "lab", "ghost.txt")


# ---------------------------------------------------------------------------
# file_tree
# ---------------------------------------------------------------------------


def test_file_tree_empty(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Lab")
    tree = file_tree(root, "lab")
    # Only EXAM.md should be in the dir; it shows up in the tree
    names = [e["name"] for e in tree]
    assert EXAM_FILE in names


def test_file_tree_nested(tmp_path):
    root = _make_root(tmp_path)
    create_group(root, "Lab")
    save_upload(root, "lab", "pyq/2023.pdf", b"pdf")
    save_upload(root, "lab", "notes.txt", b"txt")
    tree = file_tree(root, "lab")
    names = [e["name"] for e in tree]
    assert "notes.txt" in names
    dirs = [e for e in tree if e["type"] == "dir"]
    assert any(d["name"] == "pyq" for d in dirs)
    pyq = next(d for d in dirs if d["name"] == "pyq")
    assert any(c["name"] == "2023.pdf" for c in pyq["children"])


def test_file_tree_not_found(tmp_path):
    root = _make_root(tmp_path)
    with pytest.raises(ExamGroupError, match="not found"):
        file_tree(root, "ghost")


@pytest.mark.parametrize("bad", ["..", ".", "", "a/b", "a\b", ".hidden", "CON", "c:x"])
def test_bad_slug_never_escapes_exams_dir(tmp_path, bad):
    from deeptutor.services.course.exam_groups import (
        ExamGroupError,
        delete_group,
        file_tree,
        get_group,
    )

    (tmp_path / "exams").mkdir()
    (tmp_path / "keep.txt").write_text("x")
    for fn in (get_group, file_tree):
        with pytest.raises(ExamGroupError):
            fn(tmp_path, bad)
    with pytest.raises(ExamGroupError):
        delete_group(tmp_path, bad, force=True)
    assert (tmp_path / "keep.txt").exists()
