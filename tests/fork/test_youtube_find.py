# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Unit tests for the YouTube finder tool."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from deeptutor.tools.builtin import BUILTIN_TOOL_NAMES, USER_TOGGLEABLE_TOOL_NAMES
from deeptutor.tools.youtube_find import (
    KNOWN_EDUCATORS,
    MIN_RECOMMENDATION_SCORE,
    YouTubeFindTool,
    build_timestamped_url,
    extract_keywords,
    extract_youtube_candidates,
    format_duration,
    format_timestamp,
    score_candidate,
)
from deeptutor.video_learning.service import ProviderResolution, TimedMediaError


def test_extract_keywords() -> None:
    topic = "The A* Search Algorithm & Heuristics in Artificial Intelligence!"
    keywords = extract_keywords(topic)
    assert "a*" in keywords
    assert "search" in keywords
    assert "algorithm" in keywords
    assert "heuristics" in keywords
    assert "artificial" in keywords
    assert "intelligence" in keywords
    # Stopwords filtered out
    assert "the" not in keywords
    assert "in" not in keywords


def test_build_timestamped_url_both_styles() -> None:
    # YouTube watch style: &t=120s
    yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    stamped_yt = build_timestamped_url(yt_url, 120)
    assert stamped_yt == "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120s"

    # youtu.be style: ?t=75s
    short_url = "https://youtu.be/dQw4w9WgXcQ"
    stamped_short = build_timestamped_url(short_url, 75)
    assert stamped_short == "https://youtu.be/dQw4w9WgXcQ?t=75s"

    # Zero or negative seconds leaves URL unchanged
    assert build_timestamped_url(yt_url, 0) == yt_url
    assert build_timestamped_url(short_url, -10) == short_url


def test_format_timestamp_and_duration() -> None:
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(760) == "12:40"
    assert format_timestamp(3665) == "1:01:05"

    assert format_duration(0) == "Unknown duration"
    assert format_duration(90) == "1m 30s"
    assert format_duration(1800) == "30m"
    assert format_duration(3660) == "1h 1m"


def test_score_candidate_keywords_and_timestamp() -> None:
    topic = "A* search heuristic"
    metadata = {
        "title": "A* Search Algorithm and Heuristics",
        "author_name": "CS Lectures",
        "lengthSeconds": 1200,
    }
    cues = [
        {"start": 10.0, "end": 20.0, "text": "Welcome everyone to computer science."},
        {"start": 60.0, "end": 80.0, "text": "Today we explore pathfinding and search trees."},
        {
            "start": 150.0,
            "end": 170.0,
            "text": "The A* search algorithm uses a heuristic function h(n).",
        },
        {"start": 171.0, "end": 190.0, "text": "An admissible heuristic guarantees optimality."},
    ]

    score, reasons, best_ts = score_candidate(topic, metadata, cues)
    assert score >= MIN_RECOMMENDATION_SCORE
    # The best window starts at 150s where A*, search, and heuristic are discussed
    assert best_ts == 150
    assert any("02:30" in r for r in reasons)
    assert any("Title directly matches" in r for r in reasons)


def test_score_candidate_duration_penalties() -> None:
    topic = "Graph search algorithms"
    cues = [
        {"start": 10.0, "end": 30.0, "text": "Graph search algorithms are fundamental."}
    ]

    # Normal duration (20 minutes)
    score_normal, _, _ = score_candidate(
        topic, {"title": "Graph search", "lengthSeconds": 1200}, cues
    )
    # Too short (< 3 minutes)
    score_short, penalties_short, _ = score_candidate(
        topic, {"title": "Graph search", "lengthSeconds": 90}, cues
    )
    # Too long (> 3 hours)
    score_long, penalties_long, _ = score_candidate(
        topic, {"title": "Graph search", "lengthSeconds": 15000}, cues
    )

    assert score_short < score_normal
    assert score_long < score_normal
    assert any("short duration" in p.lower() for p in penalties_short)
    assert any("excessive duration" in p.lower() for p in penalties_long)


def test_score_candidate_shorts_and_clickbait_penalty() -> None:
    topic = "Sorting algorithms"
    cues = [{"start": 5.0, "end": 15.0, "text": "Sorting algorithms quicksort bubblesort."}]

    score_normal, _, _ = score_candidate(
        topic, {"title": "Sorting Algorithms Lecture", "lengthSeconds": 1500}, cues
    )
    score_shorts, penalties, _ = score_candidate(
        topic,
        {"title": "Sorting in 60 seconds #shorts !!!", "lengthSeconds": 55},
        cues,
    )

    assert score_shorts < score_normal
    assert any("short-form" in p.lower() or "clickbait" in p.lower() for p in penalties)


def test_score_candidate_channel_bonus() -> None:
    topic = "Linear Algebra"
    cues = [{"start": 10.0, "end": 30.0, "text": "Linear algebra and vector spaces."}]

    score_mit, reasons_mit, _ = score_candidate(
        topic,
        {"title": "Linear Algebra Lecture 1", "author_name": "MIT OpenCourseWare", "lengthSeconds": 2400},
        cues,
    )
    score_regular, _, _ = score_candidate(
        topic,
        {"title": "Linear Algebra Lecture 1", "author_name": "RandomVlogger99", "lengthSeconds": 2400},
        cues,
    )

    assert score_mit > score_regular
    assert any("Trusted educator" in r for r in reasons_mit)


def test_extract_youtube_candidates_dedupe() -> None:
    payloads = [
        {
            "citations": [
                {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "title": "Watch Link"},
                {"url": "https://youtu.be/dQw4w9WgXcQ", "title": "Short Link Duplicate"},
                {"url": "https://www.wikipedia.org/wiki/Search_algorithm", "title": "Not YouTube"},
            ],
            "search_results": [
                {"url": "https://www.youtube.com/watch?v=g024lzsk1GQ", "title": "Computerphile A*"},
            ],
            "answer": (
                "Also check out this tutorial: https://www.youtube.com/watch?v=ySN5Wnu88nE and "
                "https://youtu.be/dQw4w9WgXcQ again."
            ),
        }
    ]

    candidates = extract_youtube_candidates(payloads)
    ids = [c["video_id"] for c in candidates]
    # Deduplicated by video ID
    assert len(ids) == 3
    assert ids == ["dQw4w9WgXcQ", "g024lzsk1GQ", "ySN5Wnu88nE"]


@pytest.mark.asyncio
async def test_youtube_find_tool_recommendations(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = YouTubeFindTool()

    # Mock web_search
    fake_search_res = {
        "citations": [
            {
                "url": "https://www.youtube.com/watch?v=mit11111111",
                "title": "MIT 6.034 Artificial Intelligence: Search",
            },
            {
                "url": "https://www.youtube.com/watch?v=short222222",
                "title": "A* search in 30 seconds #shorts",
            },
        ],
        "search_results": [],
        "answer": "",
    }
    monkeypatch.setattr("deeptutor.tools.youtube_find.web_search", lambda *args, **kwargs: fake_search_res)

    # Mock resolve_youtube_captions
    async def mock_captions(url: str, language: Any = None) -> ProviderResolution:
        if "mit11111111" in url:
            return ProviderResolution(
                metadata={
                    "title": "MIT 6.034 Artificial Intelligence: Search",
                    "author_name": "MIT OpenCourseWare",
                    "lengthSeconds": 3000,
                },
                cues=[
                    {"start": 100.0, "end": 120.0, "text": "Let us consider A* search and heuristic functions."},
                    {"start": 121.0, "end": 140.0, "text": "An admissible heuristic is crucial."},
                ],
            )
        else:
            return ProviderResolution(
                metadata={
                    "title": "A* search in 30 seconds #shorts",
                    "author_name": "QuickVids",
                    "lengthSeconds": 30,
                },
                cues=[
                    {"start": 0.0, "end": 10.0, "text": "A* search is fast bye!"},
                ],
            )

    monkeypatch.setattr("deeptutor.tools.youtube_find.resolve_youtube_captions", mock_captions)

    result = await tool.execute(topic="A* search", max_results=3)
    assert result.success is True
    recs = result.metadata["recommendations"]
    assert len(recs) == 1
    assert recs[0]["video_id"] == "mit11111111"
    assert recs[0]["channel"] == "MIT OpenCourseWare"
    assert "MIT 6.034" in result.content
    assert "&t=100s" in recs[0]["url"]


@pytest.mark.asyncio
async def test_youtube_find_tool_unverified_captions(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = YouTubeFindTool()

    fake_search_res = {
        "citations": [
            {
                "url": "https://www.youtube.com/watch?v=nocaption11",
                "title": "Uncaptioned Lecture",
            }
        ],
        "search_results": [],
        "answer": "",
    }
    monkeypatch.setattr("deeptutor.tools.youtube_find.web_search", lambda *args, **kwargs: fake_search_res)

    # Captions return empty cues
    async def mock_captions(url: str, language: Any = None) -> ProviderResolution:
        return ProviderResolution(
            metadata={"title": "Uncaptioned Lecture", "author_name": "Some Prof"},
            cues=[],
            transcript_source="unavailable",
        )

    monkeypatch.setattr("deeptutor.tools.youtube_find.resolve_youtube_captions", mock_captions)

    result = await tool.execute(topic="Advanced Calculus")
    assert result.success is True
    assert len(result.metadata["recommendations"]) == 0
    unverified = result.metadata["unverified"]
    assert len(unverified) == 1
    assert unverified[0]["video_id"] == "nocaption11"
    assert "Unverified Candidates (Captions Unavailable)" in result.content
    assert "Uncaptioned Lecture" in result.content


@pytest.mark.asyncio
async def test_youtube_find_tool_exception_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = YouTubeFindTool()

    fake_search_res = {
        "citations": [
            {
                "url": "https://www.youtube.com/watch?v=failearly11",
                "title": "Broken Network Video",
            }
        ],
        "search_results": [],
        "answer": "",
    }
    monkeypatch.setattr("deeptutor.tools.youtube_find.web_search", lambda *args, **kwargs: fake_search_res)

    async def mock_captions(url: str, language: Any = None) -> ProviderResolution:
        raise TimedMediaError("Network timeout connecting to caption provider.")

    monkeypatch.setattr("deeptutor.tools.youtube_find.resolve_youtube_captions", mock_captions)

    # Should not crash; candidate is placed under unverified
    result = await tool.execute(topic="Quantum Mechanics")
    assert result.success is True
    assert len(result.metadata["unverified"]) == 1
    assert result.metadata["unverified"][0]["video_id"] == "failearly11"


@pytest.mark.asyncio
async def test_youtube_find_tool_missing_topic() -> None:
    tool = YouTubeFindTool()
    result = await tool.execute(topic="")
    assert result.success is False
    assert "Please specify a learning topic" in result.content


def test_youtube_find_tool_registered_and_toggleable() -> None:
    tool = YouTubeFindTool()
    defn = tool.get_definition()
    assert defn.name == "youtube_find"
    assert "youtube_find" in BUILTIN_TOOL_NAMES
    assert "youtube_find" in USER_TOGGLEABLE_TOOL_NAMES

    hints = tool.get_prompt_hints("en")
    assert hints.short_description
    assert hints.when_to_use
