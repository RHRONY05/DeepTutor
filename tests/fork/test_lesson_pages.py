# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Course lesson pages import into Immersive Reading as one scrolling section."""

from __future__ import annotations

from pathlib import Path

import pytest

from deeptutor.reading.catalog_models import IngestionStatus
from deeptutor.reading.catalog_store import ReadingCatalogStore
from deeptutor.reading.fork_lessons import keeps_whole_page, whole_page_units
from deeptutor.reading.ingestion import ReadingIngestionService
from deeptutor.reading.store import ReadingStore
from deeptutor.tools.web_fetch import FetchOutcome

LESSON = (
    "# Single Number | DSA\n\n"
    "## Understanding the Problem\n\nEvery number appears twice except one.\n\n"
    "## Approach 1: Hash Map\n\nCount each number.\n\n"
    "## Approach 2: XOR\n\nPairs cancel out.\n"
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://algomaster.io/learn/dsa/single-number", True),
        ("https://www.algomaster.io/learn/dsa/x", True),
        ("https://notalgomaster.io/x", False),
        ("https://algomaster.io.evil.test/x", False),
        ("https://example.com/article", False),
    ],
)
def test_lesson_hosts(url: str, expected: bool) -> None:
    assert keeps_whole_page(url) is expected


def test_whole_page_units_limits() -> None:
    assert whole_page_units("https://algomaster.io/a", LESSON) == (LESSON.strip(),)
    assert whole_page_units("https://example.com/a", LESSON) is None
    assert whole_page_units("https://algomaster.io/a", "  ") is None
    assert whole_page_units("https://algomaster.io/a", "x" * 150_001) is None


async def _import(tmp_path: Path, url: str) -> tuple[ReadingStore, str]:
    root = tmp_path / "reading"
    reading, catalog = ReadingStore(root), ReadingCatalogStore(root)

    async def fetcher(fetch_url: str, **_kwargs):
        return FetchOutcome(ok=True, url=fetch_url, title="Single Number | DSA", markdown=LESSON)

    service = ReadingIngestionService(reading, catalog, web_fetcher=fetcher)
    queued = service.queue_url(url)
    ready = await service.process_url(queued.material_id)
    assert ready.status is IngestionStatus.READY
    return reading, ready.material_id


@pytest.mark.asyncio
async def test_lesson_page_is_one_section(tmp_path: Path) -> None:
    reading, material_id = await _import(tmp_path, "https://algomaster.io/learn/dsa/single-number")
    assert reading.manifest(material_id).unit_count == 1
    text = reading.unit_text(material_id, 1)
    assert "Understanding the Problem" in text and "Pairs cancel out." in text
    # No real outline: the reader shows the page's own headings instead.
    assert all(row.synthesised for row in reading.outline(material_id))


@pytest.mark.asyncio
async def test_other_pages_still_split_at_headings(tmp_path: Path) -> None:
    reading, material_id = await _import(tmp_path, "https://example.com/article")
    assert reading.manifest(material_id).unit_count > 1
