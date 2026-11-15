# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Practice groups: reading list, problem links, and links kept across status updates."""

from __future__ import annotations

from pathlib import Path

import pytest

from deeptutor.services.course.exam_groups import (
    ExamGroupError,
    create_group,
    get_group,
    update_group,
)

LINKS = [
    {"label": "LeetCode", "url": "https://leetcode.com/problems/single-number/"},
    {"label": "Lesson", "url": "https://example.test/single-number"},
]


def _practice_group(root: Path) -> str:
    slug = create_group(root, "03 · Bit Manipulation", "practice")["slug"]
    update_group(
        root,
        slug,
        lessons=[{"title": "Intro to bits", "url": "https://example.test/bits"}],
        topics=[{"title": "Single Number (Easy)", "status": "todo", "links": LINKS}],
    )
    return slug


def test_practice_group_keeps_lessons_and_links(tmp_path: Path) -> None:
    slug = _practice_group(tmp_path)
    group = get_group(tmp_path, slug)
    assert group["type"] == "practice"
    assert group["lessons"] == [{"title": "Intro to bits", "url": "https://example.test/bits"}]
    assert group["topics"][0]["links"] == LINKS


def test_status_update_without_links_keeps_links(tmp_path: Path) -> None:
    """The tutor sends only title + status; the problem's links must survive."""
    slug = _practice_group(tmp_path)
    group = update_group(
        tmp_path, slug, topics=[{"title": "single number (easy)", "status": "known"}]
    )
    assert group["topics"][0]["status"] == "known"
    assert group["topics"][0]["links"] == LINKS


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "file:///C:/secret.txt", "", "https://exa mple.com"]
)
def test_links_must_be_http(tmp_path: Path, url: str) -> None:
    slug = _practice_group(tmp_path)
    with pytest.raises(ExamGroupError):
        update_group(
            tmp_path,
            slug,
            topics=[{"title": "x", "status": "todo", "links": [{"label": "L", "url": url}]}],
        )
    with pytest.raises(ExamGroupError):
        update_group(tmp_path, slug, lessons=[{"title": "L", "url": url}])


def test_tool_update_topics_keeps_links(tmp_path: Path) -> None:
    from deeptutor.tools.exam_groups import ExamGroupsTool

    slug = _practice_group(tmp_path)
    result = ExamGroupsTool()._run_action(
        tmp_path,
        "update_topics",
        {"slug": slug, "topics": [{"title": "Single Number (Easy)", "status": "learning"}]},
    )
    assert result.metadata["topics"][0]["status"] == "learning"
    assert result.metadata["topics"][0]["links"] == LINKS
