# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Pure-function exam-group operations over a workspace root Path.

Storage layout::

    <root>/exams/<slug>/EXAM.md   — YAML frontmatter + Markdown syllabus
    <root>/exams/<slug>/<files>   — any user uploads

EXAM.md frontmatter schema::

    name: str
    type: class_test | quiz | viva | mid_term | term_final | assignment | other
    date: YYYY-MM-DD | ""
    status: planned | preparing | done
    topics: [{title: str, status: todo|learning|known|skipped, links?: [{label, url}]}]
    lessons: [{title: str, url: str}]   — optional reading list (practice groups)

A ``practice`` group is a self-study track (e.g. one DSA pattern) instead of an exam.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / validators
# ---------------------------------------------------------------------------

EXAM_FILE = "EXAM.md"
EXAMS_DIR = "exams"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_SLUG_LEN = 48

VALID_TYPES = frozenset(
    {"class_test", "quiz", "viva", "mid_term", "term_final", "assignment", "practice", "other"}
)
VALID_STATUSES = frozenset({"planned", "preparing", "done"})
VALID_TOPIC_STATUSES = frozenset({"todo", "learning", "known", "skipped"})
MAX_LINKS = 8
MAX_LESSONS = 50
_URL_RE = re.compile(r"^https?://[^\s]+$")

# Windows reserved device names (case-insensitive, without extension)
_WINDOWS_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
)

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class ExamGroupError(ValueError):
    """A bad exam-group input or operation."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _exams_dir(root: Path) -> Path:
    return root / EXAMS_DIR


def _group_dir(root: Path, slug: str) -> Path:
    """Return exams/<slug>, refusing anything that is not one plain folder name."""
    slug = str(slug or "")
    if (
        not slug
        or slug in {".", ".."}
        or slug.startswith(".")
        or any(ch in slug for ch in '/\\:*?"<>|')
        or Path(slug).stem.upper() in _WINDOWS_RESERVED
    ):
        raise ExamGroupError(f"Invalid exam group id {slug!r}.")
    exams = _exams_dir(root)
    target = exams / slug
    if target.resolve().parent != exams.resolve():
        raise ExamGroupError(f"Invalid exam group id {slug!r}.")
    return target


def _exam_md(root: Path, slug: str) -> Path:
    return _group_dir(root, slug) / EXAM_FILE


def _make_slug(name: str) -> str:
    """Derive a URL-safe slug from a name."""
    base = name.lower()
    base = _SLUG_RE.sub("-", base).strip("-")
    return base[:MAX_SLUG_LEN] or "group"


def _unique_slug(root: Path, base: str) -> str:
    """Return *base* if unused, else *base*-2, *base*-3, … under exams/."""
    taken = {d.name for d in _exams_dir(root).iterdir()} if _exams_dir(root).exists() else set()
    if base not in taken:
        return base
    n = 2
    while True:
        candidate = f"{base[: MAX_SLUG_LEN - len(str(n)) - 1]}-{n}"
        if candidate not in taken:
            return candidate
        n += 1


def _parse_exam_md(path: Path) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body_text) from an EXAM.md file."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1]) or {}
            body = parts[2].lstrip("\n")
            return fm, body
    return {}, text


def _write_exam_md(path: Path, fm: dict[str, Any], body: str) -> None:
    """Atomically write EXAM.md with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False) + "---\n" + body
    fd, tmp_name = tempfile.mkstemp(prefix=".exam-", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _group_dict(root: Path, slug: str) -> dict[str, Any]:
    """Read a group directory and return the public dict."""
    gdir = _group_dir(root, slug)
    exam_path = _exam_md(root, slug)

    if exam_path.exists():
        fm, body = _parse_exam_md(exam_path)
    else:
        fm, body = {}, ""

    name: str = fm.get("name") or slug
    exam_type: str = fm.get("type") or "other"
    date: str = str(fm.get("date") or "")
    status: str = fm.get("status") or "planned"
    topics: list[dict[str, Any]] = fm.get("topics") or []
    if not isinstance(topics, list):
        topics = []
    lessons = fm.get("lessons") or []
    if not isinstance(lessons, list):
        lessons = []

    # progress
    total = len(topics)
    known = sum(1 for t in topics if isinstance(t, dict) and t.get("status") == "known")

    # file_count: everything that's NOT EXAM.md
    file_count = 0
    if gdir.exists():
        for item in gdir.rglob("*"):
            if item.is_file() and item.name != EXAM_FILE:
                file_count += 1

    updated_at = ""
    if exam_path.exists():
        mtime = exam_path.stat().st_mtime
        updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    return {
        "slug": slug,
        "name": name,
        "type": exam_type,
        "date": date,
        "status": status,
        "syllabus": body,
        "topics": topics,
        "lessons": lessons,
        "progress": {"known": known, "total": total},
        "file_count": file_count,
        "updated_at": updated_at,
    }


def _validate_type(value: str) -> str:
    if value not in VALID_TYPES:
        raise ExamGroupError(
            f"Invalid type {value!r}. Must be one of: {', '.join(sorted(VALID_TYPES))}."
        )
    return value


def _validate_status(value: str) -> str:
    if value not in VALID_STATUSES:
        raise ExamGroupError(
            f"Invalid status {value!r}. Must be one of: {', '.join(sorted(VALID_STATUSES))}."
        )
    return value


def _validate_date(value: str) -> str:
    if not value:
        return ""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ExamGroupError(
            f"Invalid date {value!r}. Expected ISO format YYYY-MM-DD or empty."
        ) from exc
    return value


def _validate_topics(topics: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in topics:
        if not isinstance(item, dict):
            raise ExamGroupError("Each topic must be a dict with 'title' and 'status'.")
        ts = str(item.get("status") or "todo")
        if ts not in VALID_TOPIC_STATUSES:
            raise ExamGroupError(
                f"Invalid topic status {ts!r}. Must be one of: "
                f"{', '.join(sorted(VALID_TOPIC_STATUSES))}."
            )
        topic: dict[str, Any] = {"title": str(item.get("title") or ""), "status": ts}
        if "links" in item:
            links = _validate_links(item.get("links"))
            if links:
                topic["links"] = links
        out.append(topic)
    return out


def _checked_url(value: Any) -> str:
    url = str(value or "").strip()
    if not _URL_RE.match(url):
        raise ExamGroupError(f"Links must be http(s) URLs, got {url!r}.")
    return url


def _validate_links(raw: Any) -> list[dict[str, str]]:
    """Return a topic's links as [{label, url}]; only http(s) URLs are accepted."""
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_LINKS:
        raise ExamGroupError(f"'links' must be a list of at most {MAX_LINKS} items.")
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ExamGroupError("Each link must be a dict with 'label' and 'url'.")
        label = str(item.get("label") or "Link").strip()[:60] or "Link"
        out.append({"label": label, "url": _checked_url(item.get("url"))})
    return out


def _validate_lessons(raw: Any) -> list[dict[str, str]]:
    """Return a group's reading list as [{title, url}]."""
    if not isinstance(raw, list) or len(raw) > MAX_LESSONS:
        raise ExamGroupError(f"'lessons' must be a list of at most {MAX_LESSONS} items.")
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ExamGroupError("Each lesson must be a dict with 'title' and 'url'.")
        title = str(item.get("title") or "Lesson").strip()[:200] or "Lesson"
        out.append({"title": title, "url": _checked_url(item.get("url"))})
    return out


# ---------------------------------------------------------------------------
# Path confinement
# ---------------------------------------------------------------------------


def _assert_safe_filename(slug: str, filename: str) -> None:
    """Raise ExamGroupError if *filename* is not safe to store under a slug dir."""
    # Reject EXAM.md as upload target
    if filename.upper() == EXAM_FILE.upper() or Path(filename).name.upper() == EXAM_FILE.upper():
        raise ExamGroupError(f"'{EXAM_FILE}' cannot be overwritten via file upload.")

    # Normalise path separators
    normalised = filename.replace("\\", "/")
    pure = PurePosixPath(normalised)

    # Absolute paths or empty
    if not normalised or pure.is_absolute():
        raise ExamGroupError("Filename must be a non-empty relative path.")

    # Drive letters (Windows) e.g. "C:"
    if re.match(r"^[A-Za-z]:", normalised):
        raise ExamGroupError("Drive-letter paths are not allowed.")

    for part in pure.parts:
        # Traversal
        if part == "..":
            raise ExamGroupError("Path traversal ('..') is not allowed.")
        # Names starting with '.'
        if part.startswith("."):
            raise ExamGroupError(f"Names starting with '.' are not allowed: {part!r}.")
        # Windows reserved names (strip extension for check)
        stem = Path(part).stem.upper()
        if stem in _WINDOWS_RESERVED:
            raise ExamGroupError(f"Windows reserved filename not allowed: {part!r}.")


def _confined_path(root: Path, slug: str, rel: str) -> Path:
    """Resolve *rel* inside the slug directory and verify confinement."""
    _assert_safe_filename(slug, rel)
    slug_dir = _group_dir(root, slug).resolve()
    target = (slug_dir / rel).resolve()
    try:
        target.relative_to(slug_dir)
    except ValueError as exc:
        raise ExamGroupError("Path escapes the exam group directory.") from exc
    return target


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_groups(root: Path) -> list[dict[str, Any]]:
    """Return all exam groups under *root*, sorted by date then name.

    A folder without EXAM.md is listed with defaults (name = folder name).
    """
    exams = _exams_dir(root)
    if not exams.exists():
        return []

    groups: list[dict[str, Any]] = []
    for entry in exams.iterdir():
        if entry.is_dir():
            try:
                groups.append(_group_dict(root, entry.name))
            except Exception:
                logger.warning("Failed to read exam group %s", entry.name, exc_info=True)

    def sort_key(g: dict[str, Any]) -> tuple[int, str, str]:
        d = g["date"]
        return (0 if d else 1, d or "", g["name"].lower())

    groups.sort(key=sort_key)
    return groups


def get_group(root: Path, slug: str) -> dict[str, Any]:
    """Return the group dict for *slug*, or raise ExamGroupError if not found."""
    gdir = _group_dir(root, slug)
    if not gdir.exists() or not gdir.is_dir():
        raise ExamGroupError(f"Exam group '{slug}' not found.")
    return _group_dict(root, slug)


def create_group(
    root: Path,
    name: str,
    exam_type: str = "other",
    date: str = "",
    syllabus: str = "",
) -> dict[str, Any]:
    """Create a new exam group and return its dict."""
    if not name or not name.strip():
        raise ExamGroupError("Group name must not be empty.")
    name = name.strip()
    _validate_type(exam_type)
    _validate_date(date)

    slug = _unique_slug(root, _make_slug(name))
    fm: dict[str, Any] = {
        "name": name,
        "type": exam_type,
        "date": date,
        "status": "planned",
        "topics": [],
    }
    _write_exam_md(_exam_md(root, slug), fm, syllabus)
    logger.info("Created exam group '%s' (slug=%s)", name, slug)
    return _group_dict(root, slug)


def update_group(root: Path, slug: str, **fields: Any) -> dict[str, Any]:
    """Update allowed fields on an existing group.

    Allowed field keys: name, type, date, status, syllabus, topics, lessons.
    A topic sent without ``links`` keeps the links of the existing topic with the same title,
    so a status update (by the tutor or the UI) never drops a problem's links.
    """
    gdir = _group_dir(root, slug)
    if not gdir.exists():
        raise ExamGroupError(f"Exam group '{slug}' not found.")

    exam_path = _exam_md(root, slug)
    if exam_path.exists():
        fm, body = _parse_exam_md(exam_path)
    else:
        fm, body = {}, ""

    if "name" in fields:
        v = str(fields["name"]).strip()
        if not v:
            raise ExamGroupError("Group name must not be empty.")
        fm["name"] = v

    if "type" in fields:
        fm["type"] = _validate_type(str(fields["type"]))

    if "date" in fields:
        fm["date"] = _validate_date(str(fields["date"]))

    if "status" in fields:
        fm["status"] = _validate_status(str(fields["status"]))

    if "syllabus" in fields:
        body = str(fields["syllabus"])

    if "topics" in fields:
        raw = fields["topics"]
        if not isinstance(raw, list):
            raise ExamGroupError("'topics' must be a list.")
        topics = _validate_topics(raw)
        old_links = {
            str(t.get("title") or "").strip().lower(): t["links"]
            for t in fm.get("topics") or []
            if isinstance(t, dict) and t.get("links")
        }
        for topic in topics:
            if "links" not in topic:
                links = old_links.get(topic["title"].strip().lower())
                if links:
                    topic["links"] = links
        fm["topics"] = topics

    if "lessons" in fields:
        fm["lessons"] = _validate_lessons(fields["lessons"])

    _write_exam_md(exam_path, fm, body)
    return _group_dict(root, slug)


def delete_group(root: Path, slug: str, force: bool = False) -> None:
    """Delete an exam group directory.

    Refuses (raises ExamGroupError) when files other than EXAM.md exist
    unless *force* is True.
    """
    gdir = _group_dir(root, slug)
    if not gdir.exists() or not gdir.is_dir():
        raise ExamGroupError(f"Exam group '{slug}' not found.")

    extra: list[Path] = [p for p in gdir.rglob("*") if p.is_file() and p.name != EXAM_FILE]
    if extra and not force:
        raise ExamGroupError(
            f"Exam group '{slug}' contains {len(extra)} file(s) besides {EXAM_FILE}. "
            "Use force=True to delete anyway."
        )

    import shutil

    shutil.rmtree(gdir)
    logger.info("Deleted exam group '%s' (force=%s)", slug, force)


def save_upload(
    root: Path,
    slug: str,
    filename: str,
    data: bytes,
) -> dict[str, Any]:
    """Save uploaded bytes as *filename* (may include subfolder) inside the slug dir.

    Returns a minimal dict with the saved path info.
    """
    gdir = _group_dir(root, slug)
    if not gdir.exists() or not gdir.is_dir():
        raise ExamGroupError(f"Exam group '{slug}' not found.")

    if len(data) > MAX_UPLOAD_BYTES:
        raise ExamGroupError(
            f"File '{filename}' is {len(data):,} bytes, which exceeds the 50 MB limit."
        )

    target = _confined_path(root, slug, filename)
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(prefix=".up-", dir=target.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)

    logger.info("Saved upload %s/%s (%d bytes)", slug, filename, len(data))
    return {"slug": slug, "path": filename, "size": len(data)}


def delete_file(root: Path, slug: str, rel_path: str) -> None:
    """Delete a file inside the slug dir identified by its relative path."""
    gdir = _group_dir(root, slug)
    if not gdir.exists() or not gdir.is_dir():
        raise ExamGroupError(f"Exam group '{slug}' not found.")

    target = _confined_path(root, slug, rel_path)
    if not target.exists():
        raise ExamGroupError(f"File '{rel_path}' not found in exam group '{slug}'.")
    if not target.is_file():
        raise ExamGroupError(f"'{rel_path}' is not a file.")
    target.unlink()

    # Remove empty ancestor directories up to (but not including) slug dir
    slug_dir = _group_dir(root, slug).resolve()
    parent = target.parent
    while parent.resolve() != slug_dir:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent

    logger.info("Deleted file %s/%s", slug, rel_path)


def file_tree(root: Path, slug: str) -> list[dict[str, Any]]:
    """Return a nested list describing all files/dirs under the slug dir.

    Format: [{name, path, type: 'file'|'dir', size, children: [...]}]
    Children is present only for dirs.
    """
    gdir = _group_dir(root, slug)
    if not gdir.exists() or not gdir.is_dir():
        raise ExamGroupError(f"Exam group '{slug}' not found.")

    def _build(directory: Path, rel_prefix: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        try:
            children = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return entries

        for item in children:
            rel = f"{rel_prefix}/{item.name}" if rel_prefix else item.name
            if item.is_dir():
                entries.append(
                    {
                        "name": item.name,
                        "path": rel,
                        "type": "dir",
                        "size": 0,
                        "children": _build(item, rel),
                    }
                )
            elif item.is_file():
                try:
                    size = item.stat().st_size
                except OSError:
                    size = 0
                entries.append({"name": item.name, "path": rel, "type": "file", "size": size})
        return entries

    return _build(gdir, "")
