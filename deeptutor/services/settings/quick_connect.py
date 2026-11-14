# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""One-click connection of the local subscription CLIs (Claude Code, Antigravity).

Both providers sign in through their own CLI, so "connecting" only means:
the CLI is on PATH, then a provider connection plus a main and a light model
exist in the model catalog, set as the chat model and the task model.
No credentials are read or stored. Existing entries are reused, never duplicated.
"""

from __future__ import annotations

from datetime import datetime, timezone
import shutil
from typing import Any
import uuid

QUICK_CONNECT: dict[str, dict[str, Any]] = {
    "claude_code": {
        "cli": "claude",
        "name": "Claude Code (subscription)",
        "main": ("sonnet", 200_000),
        "light": ("haiku", 200_000),
        "missing": "Claude Code CLI (`claude`) was not found. Install Claude Code and run `claude` once to sign in.",
    },
    "antigravity_acp": {
        "cli": "agy",
        "name": "Antigravity (Google AI Pro subscription)",
        "main": ("gemini-3.8-flash-medium", 1_048_576),
        "light": ("gemini-3.8-flash-low", 1_048_576),
        "missing": "Antigravity CLI (`agy`) was not found. Install it from antigravity.google and run `agy` once to sign in.",
    },
}


def cli_available(binding: str) -> bool:
    return bool(shutil.which(QUICK_CONNECT[binding]["cli"]))


def _ref(connection_id: str, binding: str) -> dict[str, str]:
    return {"connection_id": connection_id, "binding": binding, "default_base_url": ""}


def apply_quick_connect(
    catalog: dict[str, Any], binding: str, model_ids: list[str] | None = None
) -> dict[str, str]:
    """Mutate *catalog* in place. Returns the ids it selected."""
    spec = QUICK_CONNECT[binding]
    now = datetime.now(timezone.utc).isoformat()
    connections = catalog.setdefault("connections", [])
    connection = next((c for c in connections if c.get("provider") == binding), None)
    if connection is None:
        connection = {
            "id": f"conn-{uuid.uuid4()}",
            "name": spec["name"],
            "provider": binding,
            "source_service": "llm",
            "api_key": "",
            "base_url": "",
            "api_version": "",
            "api_format": "auto",
            "extra_headers": {},
        }
        connections.append(connection)
    connection["discovery"] = {
        "status": "connected",
        "models": [{"id": m, "services": ["llm"]} for m in (model_ids or [])],
        "checked_at": now,
    }
    conn_id = connection["id"]

    services = catalog.setdefault("services", {})
    llm = services.setdefault("llm", {})
    profiles = llm.setdefault("profiles", [])
    profile = next(
        (
            p
            for p in profiles
            if p.get("binding") == binding
            and (p.get("provider_ref") or {}).get("connection_id") == conn_id
        ),
        None,
    )
    if profile is None:
        profile = {
            "id": f"llm-profile-{uuid.uuid4()}",
            "name": spec["name"],
            "binding": binding,
            "provider_ref": _ref(conn_id, binding),
            "api_key": "",
            "base_url": "",
            "api_version": "",
            "models": [],
            "extra_headers": {},
            "api_format": "auto",
            "wire_api": "auto",
        }
        profiles.append(profile)

    def ensure_model(model: str, context: int) -> str:
        for entry in profile.setdefault("models", []):
            if entry.get("model") == model:
                return entry["id"]
        entry = {
            "id": f"llm-model-{uuid.uuid4()}",
            "model": model,
            "name": model,
            "provider_ref": _ref(conn_id, binding),
            "context_window": str(context),
            "context_window_source": "manual",
        }
        profile["models"].append(entry)
        return entry["id"]

    main_id = ensure_model(*spec["main"])
    light_id = ensure_model(*spec["light"])
    llm["active_profile_id"] = profile["id"]
    llm["active_model_id"] = main_id
    task = services.setdefault("task", {"active_profile_id": None, "active_model_id": None})
    task.setdefault("profiles", [])
    task["mode"] = "reference"
    task["selection"] = {"profile_id": profile["id"], "model_id": light_id}
    return {
        "connection_id": conn_id,
        "profile_id": profile["id"],
        "model_id": main_id,
        "task_model_id": light_id,
        "model": spec["main"][0],
        "task_model": spec["light"][0],
    }


__all__ = ["QUICK_CONNECT", "apply_quick_connect", "cli_available"]
