# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""YouTube finder tool — searches for educational videos and lectures with verified captions."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from deeptutor.core.tool_protocol import (
    BaseTool,
    ToolDefinition,
    ToolParameter,
    ToolPromptHints,
    ToolResult,
)
from deeptutor.tools.prompting import load_prompt_hints
from deeptutor.tools.web_search import web_search
from deeptutor.video_learning.service import (
    parse_youtube_url,
    resolve_youtube_captions,
)

logger = logging.getLogger(__name__)

# Channels and institutions known for high-quality educational/lecture material
KNOWN_EDUCATORS: tuple[str, ...] = (
    "mit",
    "mit opencourseware",
    "mitocw",
    "nptel",
    "nptelhrd",
    "stanford",
    "stanfordonline",
    "harvard",
    "harvard online",
    "berkeley",
    "cmu",
    "carnegie mellon",
    "iit",
    "freecodecamp",
    "freecodecamp.org",
    "3blue1brown",
    "khan academy",
    "khanacademy",
    "cs dojo",
    "abdul bari",
    "gate smashers",
    "gatesmashers",
    "neso academy",
    "nesoacademy",
    "jenny's lectures",
    "jenny's lectures cs/it",
    "statquest",
    "statquest with josh starmer",
    "crashcourse",
    "crash course",
    "edx",
    "coursera",
    "fireship",
    "computerphile",
    "numberphile",
    "traversy media",
    "the ameen channel",
    "corey schafer",
    "lex fridman",
    "sentdex",
    "kevin powell",
    "the coding train",
)

STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "about", "above", "after", "again", "against", "all", "am", "an",
        "and", "any", "are", "aren't", "as", "at", "be", "because", "been",
        "before", "being", "below", "between", "both", "but", "by", "can",
        "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
        "doesn't", "doing", "don't", "down", "during", "each", "few", "for",
        "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't",
        "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers",
        "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll",
        "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its",
        "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
        "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
        "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
        "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't",
        "so", "some", "such", "than", "that", "that's", "the", "their", "theirs",
        "them", "themselves", "then", "there", "there's", "these", "they",
        "they'd", "they'll", "they're", "they've", "this", "those", "through",
        "to", "too", "under", "until", "up", "very", "was", "wasn't", "we",
        "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's",
        "when", "when's", "where", "where's", "which", "while", "who", "who's",
        "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you",
        "you'd", "you'll", "you're", "you've", "your", "yours", "yourself",
        "yourselves",
        # Generic query words
        "video", "videos", "lecture", "lectures", "tutorial", "tutorials",
        "learn", "explained", "explanation", "introduction", "intro",
    }
)

MIN_RECOMMENDATION_SCORE: float = 35.0


def extract_keywords(topic: str) -> list[str]:
    """Tokenise a topic string into search keywords, filtering stopwords."""
    words = re.findall(r"[A-Za-z0-9_+#*.-]+", (topic or "").lower())
    cleaned: list[str] = []
    for w in words:
        w_stripped = w.strip(".-")
        if len(w_stripped) >= 2 and w_stripped not in STOPWORDS:
            cleaned.append(w_stripped)
    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for kw in cleaned:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    if not result:
        for w in words:
            if w not in seen:
                seen.add(w)
                result.append(w)
    return result


def build_timestamped_url(url: str, seconds: int) -> str:
    """Format a YouTube URL with an entry timestamp parameter (&t= or ?t=)."""
    if seconds <= 0:
        return url
    parsed = urlparse(url)
    t_val = f"{int(seconds)}s"
    query = parse_qs(parsed.query)
    query["t"] = [t_val]
    new_query = urlencode(query, doseq=True)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )


def format_timestamp(seconds: int | float) -> str:
    """Format seconds into mm:ss or hh:mm:ss."""
    s = max(0, int(seconds))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def format_duration(seconds: int | float) -> str:
    """Format duration in seconds into a friendly description."""
    s = max(0, int(seconds))
    if s == 0:
        return "Unknown duration"
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h}h {m}m" if m else f"{h}h"
    if m > 0:
        return f"{m}m {sec}s" if sec else f"{m}m"
    return f"{sec}s"


def score_candidate(
    topic: str,
    metadata: dict[str, Any],
    cues: list[dict[str, Any]],
) -> tuple[float, list[str], int]:
    """Pure scoring function for YouTube video candidates.

    Returns:
        (score, reasons, best_timestamp)
    """
    keywords = extract_keywords(topic)
    title = str(metadata.get("title") or "").strip()
    title_lower = title.lower()
    channel = str(
        metadata.get("author_name")
        or metadata.get("author")
        or metadata.get("channel")
        or ""
    ).strip()
    channel_lower = channel.lower()
    duration = int(float(metadata.get("lengthSeconds") or metadata.get("duration") or 0))

    reasons: list[str] = []
    penalties: list[str] = []

    # 1. Topic keyword coverage in transcript and best timestamp window
    coverage_score = 0.0
    density_score = 0.0
    best_timestamp = 0
    found_kws: list[str] = []

    if cues and keywords:
        full_text = " ".join(str(c.get("text") or "") for c in cues).lower()
        found_kws = [kw for kw in keywords if kw in full_text]
        coverage_ratio = len(found_kws) / len(keywords)
        coverage_score = coverage_ratio * 40.0

        total_hits = sum(full_text.count(kw) for kw in keywords)
        density_score = min(15.0, total_hits * 1.0)

        # Sliding window (60s) to find peak keyword explanation timestamp
        best_window_score = -1
        best_window_kws: list[str] = []
        for i, cue in enumerate(cues):
            start_i = float(cue.get("start") or 0)
            window_text = " ".join(
                str(c.get("text") or "")
                for c in cues[i:]
                if start_i <= float(c.get("start") or 0) < start_i + 60.0
            ).lower()
            w_hits = sum(window_text.count(kw) for kw in keywords)
            w_distinct = [kw for kw in keywords if kw in window_text]
            w_score = len(w_distinct) * 10 + w_hits
            if w_score > best_window_score:
                best_window_score = w_score
                best_timestamp = int(start_i)
                best_window_kws = w_distinct

        if best_window_kws:
            ts_formatted = format_timestamp(best_timestamp)
            reasons.append(
                f"covers {', '.join(best_window_kws[:3])} at {ts_formatted}"
            )
        elif found_kws:
            reasons.append(f"covers {', '.join(found_kws[:3])}")
    elif cues:
        # Cues present but no keywords matched
        coverage_score = 5.0

    # 2. Title match
    title_hits = [kw for kw in keywords if kw in title_lower] if keywords else []
    title_score = (len(title_hits) / len(keywords)) * 25.0 if keywords else 0.0
    if title_hits:
        reasons.append(f"Title directly matches {', '.join(title_hits)}")

    # 3. Duration sanity band (< 3 min and > 3 hours penalized)
    duration_adjustment = 0.0
    if duration > 0:
        if duration < 180:
            duration_adjustment = -25.0
            penalties.append("Penalized for short duration (<3 min)")
        elif duration > 10800:
            duration_adjustment = -15.0
            penalties.append("Penalized for excessive duration (>3 hours)")
        elif 300 <= duration <= 3600:
            duration_adjustment = 10.0
        elif 180 <= duration < 300 or 3600 < duration <= 10800:
            duration_adjustment = 5.0

    # 4. Educator channel bonus
    channel_bonus = 0.0
    educator_match = next((ed for ed in KNOWN_EDUCATORS if ed in channel_lower), None)
    if educator_match:
        channel_bonus = 15.0
        reasons.append(f"Trusted educator/institution ({channel})")
    elif channel:
        reasons.append(f"Channel: {channel}")

    # 5. Shorts and clickbait penalty
    clickbait_penalty = 0.0
    raw_tags = metadata.get("tags") or []
    tags_str = " ".join(str(t).lower() for t in raw_tags) if isinstance(raw_tags, Sequence) else ""
    meta_text = f"{title_lower} {tags_str}"

    is_shorts = (
        "#shorts" in meta_text
        or "shorts" in meta_text.split()
        or (0 < duration <= 60)
    )
    has_clickbait = any(
        pat in meta_text
        for pat in ["in 60 seconds", "in 1 minute", "in 30 seconds", "!!!", "shocking", "you won't believe"]
    )
    if is_shorts:
        clickbait_penalty -= 35.0
        penalties.append("Penalized as short-form video")
    if has_clickbait:
        clickbait_penalty -= 20.0
        penalties.append("Penalized for clickbait/superficial title")

    total_score = (
        coverage_score
        + density_score
        + title_score
        + duration_adjustment
        + channel_bonus
        + clickbait_penalty
    )
    final_score = max(0.0, min(100.0, total_score))

    # Compile final reasons: return top reasons (prioritizing any penalties if present)
    final_reasons = (penalties + reasons)[:3] if penalties else reasons[:3]

    return final_score, final_reasons, best_timestamp


def extract_youtube_candidates(search_results: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Collect candidate YouTube URLs from search citations, results, and text."""
    candidates: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    url_pattern = re.compile(r"https?://[^\s<>'\"`\)]+")

    def try_add(url: str, title: str = "") -> None:
        if not url:
            return
        try:
            req = parse_youtube_url(url)
            if req.video_id not in seen_ids:
                seen_ids.add(req.video_id)
                norm_url = url.strip().strip("`\"'")
                canonical_watch = f"https://www.youtube.com/watch?v={req.video_id}"
                chosen_url = norm_url if ("youtube.com/watch" in norm_url or "youtu.be" in norm_url) else canonical_watch
                candidates.append({
                    "video_id": req.video_id,
                    "url": chosen_url,
                    "title": title.strip(),
                })
        except Exception:
            pass

    for res in search_results:
        if not isinstance(res, dict):
            continue
        # Check citations
        for cit in res.get("citations") or []:
            if isinstance(cit, dict):
                try_add(str(cit.get("url") or ""), str(cit.get("title") or ""))
                if len(candidates) >= 8:
                    return candidates
        # Check raw search_results
        for sr in res.get("search_results") or []:
            if isinstance(sr, dict):
                try_add(str(sr.get("url") or ""), str(sr.get("title") or ""))
                if len(candidates) >= 8:
                    return candidates
        # Check answer text for links
        answer = str(res.get("answer") or "")
        for match in url_pattern.findall(answer):
            try_add(match)
            if len(candidates) >= 8:
                return candidates

    return candidates


def format_result_markdown(
    topic: str,
    recommended: list[dict[str, Any]],
    unverified: list[dict[str, Any]],
) -> str:
    """Render recommended and unverified videos into compact Markdown."""
    lines: list[str] = []
    if recommended:
        lines.append(f"### Recommended Lectures for '{topic}'\n")
        for i, item in enumerate(recommended, 1):
            title = item.get("title") or "YouTube Video"
            url = item["timestamped_url"]
            channel = item.get("channel") or "Unknown Channel"
            start_ts = format_timestamp(item["best_timestamp"])
            dur_sec = item.get("duration", 0)
            dur = format_duration(dur_sec) if dur_sec > 0 else "Unknown duration"
            reasons = item.get("reasons") or ["Covers lecture topic"]
            why_str = "; ".join(reasons[:3])

            lines.append(f"{i}. **[{title}]({url})**")
            lines.append(f"   - **Channel**: {channel}")
            lines.append(f"   - **Recommended start**: {start_ts} | **Duration**: {dur}")
            lines.append(f"   - **Why**: {why_str}")
            lines.append("")
    else:
        lines.append(
            f"No verified educational videos with suitable captions could be found for '{topic}'."
        )
        lines.append(
            f"💡 **Tip**: Try refining your search with a more specific phrase, e.g. `'{topic} lecture'` or `'{topic} tutorial'`."
        )
        lines.append("")

    if unverified:
        lines.append("### Unverified Candidates (Captions Unavailable)\n")
        lines.append(
            "_The following videos matched your search query but their captions could not be verified:_\n"
        )
        for item in unverified[:4]:
            title = item.get("title") or "YouTube Video"
            url = item["url"]
            channel = item.get("channel")
            channel_info = f" ({channel})" if channel else ""
            lines.append(f"- [{title}]({url}){channel_info}")
        lines.append("")

    return "\n".join(lines).strip()


class YouTubeFindTool(BaseTool):
    """Tool that finds and scores educational YouTube videos based on caption quality."""

    name = "youtube_find"

    def get_prompt_hints(self, language: str = "en") -> ToolPromptHints:
        return load_prompt_hints(self.name, language=language)

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="youtube_find",
            description=(
                "Search YouTube for high-quality educational videos and lectures for a learning topic. "
                "Use when the student asks for a video, or when a visual lecture would help. "
                "It checks captions before recommending; always tell the student why each video is "
                "recommended and where to start."
            ),
            parameters=[
                ToolParameter(
                    name="topic",
                    type="string",
                    description="What the student needs to learn (concept, algorithm, theory, or problem).",
                    required=True,
                ),
                ToolParameter(
                    name="level",
                    type="string",
                    description="Target learning level.",
                    required=False,
                    enum=["beginner", "intermediate", "exam-revision"],
                ),
                ToolParameter(
                    name="language",
                    type="string",
                    description="Preferred transcript language code (default 'en').",
                    required=False,
                    default="en",
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum number of recommended videos (1 to 5, default 3).",
                    required=False,
                    default=3,
                    minimum=1,
                    maximum=5,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        topic = str(kwargs.get("topic") or "").strip()
        if not topic:
            return ToolResult(
                content="Please specify a learning topic to search for YouTube videos.",
                success=False,
                metadata={"error": "missing_topic"},
            )

        level = str(kwargs.get("level") or "").strip() or None
        language = str(kwargs.get("language") or "en").strip() or "en"
        try:
            max_results = max(1, min(5, int(kwargs.get("max_results") or 3)))
        except (ValueError, TypeError):
            max_results = 3

        # Formulate search queries
        if level == "exam-revision":
            q1 = f"site:youtube.com {topic} exam revision lecture"
        elif level == "beginner":
            q1 = f"site:youtube.com {topic} beginner lecture"
        else:
            q1 = f"site:youtube.com {topic} lecture"
        q2 = f"{topic} explained youtube"

        # Step a: Run web search in a thread for 2 queries
        try:
            res1, res2 = await asyncio.gather(
                asyncio.to_thread(web_search, q1),
                asyncio.to_thread(web_search, q2),
                return_exceptions=True,
            )
        except Exception as exc:
            logger.exception("Unexpected error initiating web search for '%s': %s", topic, exc)
            return ToolResult(
                content=f"Could not perform search for '{topic}': {exc}",
                success=False,
                metadata={"error": str(exc)},
            )

        search_payloads: list[dict[str, Any]] = []
        for r, q in [(res1, q1), (res2, q2)]:
            if isinstance(r, Exception):
                logger.warning("Search query %r failed: %s", q, r)
            elif isinstance(r, dict):
                search_payloads.append(r)

        candidates = extract_youtube_candidates(search_payloads)
        if not candidates:
            return ToolResult(
                content=(
                    f"No YouTube videos found for '{topic}'. "
                    "Try using different or broader search keywords."
                ),
                success=True,
                metadata={
                    "topic": topic,
                    "level": level,
                    "language": language,
                    "recommendations": [],
                    "unverified": [],
                },
            )

        # Step b: Concurrently resolve captions and metadata (max 4 concurrent, 25s timeout each)
        sem = asyncio.Semaphore(4)

        async def _resolve_candidate(cand: dict[str, str]) -> dict[str, Any]:
            url = cand["url"]
            async with sem:
                try:
                    resolution = await asyncio.wait_for(
                        resolve_youtube_captions(url, language=[language, "en"]),
                        timeout=25.0,
                    )
                    meta = resolution.metadata if isinstance(resolution.metadata, dict) else {}
                    cues = resolution.cues if isinstance(resolution.cues, list) else []
                    captions_checked = bool(cues)
                    title = str(meta.get("title") or cand.get("title") or "YouTube Video").strip()
                    channel = str(
                        meta.get("author_name")
                        or meta.get("author")
                        or meta.get("channel")
                        or ""
                    ).strip()
                    duration = int(float(meta.get("lengthSeconds") or meta.get("duration") or 0))
                    view_count = int(float(meta.get("viewCount") or meta.get("views") or 0))

                    return {
                        **cand,
                        "title": title,
                        "channel": channel,
                        "duration": duration,
                        "view_count": view_count,
                        "metadata": meta,
                        "cues": cues,
                        "captions_checked": captions_checked,
                    }
                except Exception as exc:
                    logger.debug("Captions unavailable for %s: %s", url, exc)
                    return {
                        **cand,
                        "channel": "",
                        "duration": 0,
                        "view_count": 0,
                        "metadata": {},
                        "cues": [],
                        "captions_checked": False,
                    }

        resolved_candidates = await asyncio.gather(
            *[_resolve_candidate(cand) for cand in candidates]
        )

        # Step c: Score each candidate
        recommended: list[dict[str, Any]] = []
        unverified: list[dict[str, Any]] = []

        for cand in resolved_candidates:
            score, reasons, best_ts = score_candidate(topic, cand["metadata"], cand["cues"])
            cand["score"] = score
            cand["reasons"] = reasons
            cand["best_timestamp"] = best_ts
            cand["timestamped_url"] = build_timestamped_url(cand["url"], best_ts)

            if cand["captions_checked"] and score >= MIN_RECOMMENDATION_SCORE:
                recommended.append(cand)
            elif not cand["captions_checked"]:
                unverified.append(cand)

        recommended.sort(key=lambda item: item["score"], reverse=True)
        top_recommended = recommended[:max_results]

        # Step d: Build Markdown result and structured metadata
        content = format_result_markdown(topic, top_recommended, unverified)
        metadata = {
            "topic": topic,
            "level": level,
            "language": language,
            "max_results": max_results,
            "recommendations": [
                {
                    "video_id": item["video_id"],
                    "title": item["title"],
                    "channel": item["channel"],
                    "url": item["timestamped_url"],
                    "base_url": item["url"],
                    "timestamp": item["best_timestamp"],
                    "timestamp_formatted": format_timestamp(item["best_timestamp"]),
                    "duration": item["duration"],
                    "duration_formatted": format_duration(item["duration"]),
                    "score": item["score"],
                    "reasons": item["reasons"],
                    "captions_checked": True,
                }
                for item in top_recommended
            ],
            "unverified": [
                {
                    "video_id": item["video_id"],
                    "title": item["title"],
                    "channel": item["channel"],
                    "url": item["url"],
                    "captions_checked": False,
                }
                for item in unverified
            ],
        }

        return ToolResult(content=content, success=True, metadata=metadata)
