# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

INSTRUCTION_HEADING = (
    "Course instructions from the student (follow them unless they conflict with the task format):"
)


def workspace_instruction_block(context_or_workspace: Any = None) -> str:
    """Return a formatted instruction block if instructions exist, else empty string.

    Resolve instructions from a passed UnifiedContext (context.runtime.workspace)
    when available, else from the current workspace scope (ContextVar).
    Never raises: logs and returns "" on any error.
    """
    try:
        instructions = ""

        # 1. Try resolving from context_or_workspace if passed
        if context_or_workspace is not None:
            # Case A: UnifiedContext or object with runtime.workspace
            runtime = getattr(context_or_workspace, "runtime", None)
            workspace = getattr(runtime, "workspace", None) if runtime is not None else None
            if workspace is not None:
                raw_instr = getattr(workspace, "instructions", "")
                instructions = str(raw_instr or "").strip()
                if not instructions:
                    ws_id = str(getattr(workspace, "workspace_id", "") or "").strip()
                    if ws_id:
                        try:
                            from deeptutor.services.workspace import get_content_workspace_service

                            service = get_content_workspace_service()
                            instructions = service.workspace_instructions(ws_id).strip()
                        except Exception:
                            pass

            # Case B: Object itself has an instructions attribute (e.g. WorkspaceRuntimeContext)
            if not instructions and hasattr(context_or_workspace, "instructions"):
                raw_instr = getattr(context_or_workspace, "instructions", "")
                instructions = str(raw_instr or "").strip()

            # Case C: Passed a string workspace_id
            if not instructions and isinstance(context_or_workspace, str):
                ws_id = context_or_workspace.strip()
                if ws_id:
                    try:
                        from deeptutor.services.workspace import get_content_workspace_service

                        service = get_content_workspace_service()
                        instructions = service.workspace_instructions(ws_id).strip()
                    except Exception:
                        pass

        # 2. If still empty, fall back to current workspace scope
        if not instructions:
            try:
                from deeptutor.services.workspace import get_content_workspace_service
                from deeptutor.services.workspace.context import current_workspace_id

                ws_id = current_workspace_id()
                service = get_content_workspace_service()
                instructions = service.workspace_instructions(ws_id or None).strip()
            except Exception:
                pass

        if not instructions:
            return ""

        return f"{INSTRUCTION_HEADING}\n{instructions}"
    except Exception as exc:
        logger.debug("Failed to resolve workspace instruction block: %s", exc, exc_info=True)
        return ""
