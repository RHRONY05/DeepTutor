# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Keep course lesson pages as one long section in Immersive Reading.

Web pages are normally cut at their headings, so the reader shows one section at
a time. A lesson reads better as one scrolling page, like the original site: the
reader then lists the page's headings in Contents and jumps to them.
"""

from __future__ import annotations

from urllib.parse import urlsplit

# Sites whose pages are lessons (DSA course). Matched on the host and its subdomains.
WHOLE_PAGE_HOSTS = frozenset({"algomaster.io"})

# Larger pages are still cut into sections, so one unit stays a sane size.
MAX_WHOLE_PAGE_CHARS = 150_000


def keeps_whole_page(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return any(host == base or host.endswith("." + base) for base in WHOLE_PAGE_HOSTS)


def whole_page_units(url: str, markdown: str) -> tuple[str, ...] | None:
    """Return the page as a single unit when it is a lesson page, else None."""
    text = markdown.strip()
    if not text or len(text) > MAX_WHOLE_PAGE_CHARS or not keeps_whole_page(url):
        return None
    return (text,)
