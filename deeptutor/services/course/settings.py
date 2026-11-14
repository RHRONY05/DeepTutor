# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Course-workspace settings sidecar.

Stores per-workspace preferences in ``data/user/settings/fork_courses.json``
(keyed by workspace_id).

Schema::

    {
        "<workspace_id>": {
            "default_persona": "<name> | ''"
        }
    }
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import tempfile
import threading
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PERSONA = ""

_LOCK = threading.Lock()


def _settings_file() -> Path:
    from deeptutor.multi_user.paths import get_account_path_service

    return get_account_path_service().get_settings_file("fork_courses")


def _read_raw(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except Exception:
        logger.warning("Could not read %s, treating as empty.", path, exc_info=True)
    return {}


def _write_raw(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".fork_courses.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def get_course_settings(workspace_id: str) -> dict[str, Any]:
    """Return the settings dict for *workspace_id*.

    Always returns at least ``{"default_persona": ""}``.
    """
    path = _settings_file()
    with _LOCK:
        raw = _read_raw(path)
    ws = raw.get(workspace_id)
    if not isinstance(ws, dict):
        ws = {}
    return {"default_persona": str(ws.get("default_persona") or _DEFAULT_PERSONA)}


def set_course_settings(workspace_id: str, default_persona: str) -> dict[str, Any]:
    """Write *default_persona* for *workspace_id* and return the new settings."""
    path = _settings_file()
    with _LOCK:
        raw = _read_raw(path)
        entry = raw.get(workspace_id)
        if not isinstance(entry, dict):
            entry = {}
        entry["default_persona"] = str(default_persona)
        raw[workspace_id] = entry
        _write_raw(path, raw)
    return {"default_persona": entry["default_persona"]}


def default_persona_for_current_workspace() -> str:
    """Return the default persona configured for the active workspace, or ''."""
    try:
        from deeptutor.services.workspace.context import current_workspace_id

        ws_id = current_workspace_id()
        if not ws_id:
            return ""
        settings = get_course_settings(ws_id)
        return str(settings.get("default_persona") or "")
    except Exception:
        logger.warning(
            "Failed to resolve default persona for current workspace",
            exc_info=True,
        )
        return ""

