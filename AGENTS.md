<!-- Modified in the RH.RONY fork (Apache-2.0 §4b): fork block added at the top. Upstream text below is unchanged. -->
<!-- fork(antigravity_acp) start -->
# Fork: start here (RH.RONY's DeepTutor)

This checkout is **RH.RONY's long-lived fork** of HKUDS/DeepTutor (see [FORK_NOTICE.md](FORK_NOTICE.md)).
Current fork work: an **`antigravity_acp` LLM provider**, so the tutor runs on a Google AI Pro subscription
through the official Antigravity CLI (`agy acp`), next to upstream's built-in Claude Code provider.

**Planned by** Claude. **Built by** an AI agent (Antigravity), end to end. Rony checks the result; he doesn't write code.

## Read in this order
0. [.agent/PROGRESS.md](.agent/PROGRESS.md): where the work is now (read first, update before you stop)
1. [.agent/rules/deeptutor-fork.md](.agent/rules/deeptutor-fork.md): always-on rules (non-negotiable)
2. [.agent/01-PRODUCT.md](.agent/01-PRODUCT.md): what the change does, user stories, out of scope
3. [.agent/02-ARCHITECTURE.md](.agent/02-ARCHITECTURE.md): files touched, wiring, setup, fork markers
4. [.agent/07-ACP-PROVIDER.md](.agent/07-ACP-PROVIDER.md): the provider contract and spike facts
5. [.agent/09-TESTING.md](.agent/09-TESTING.md): unit, live integration and manual checks
6. [.agent/08-TASKS.md](.agent/08-TASKS.md): the task list (V0 → V6)
7. `.agent/workflows/`: `/project-config` (once), `/next-task`, `/status`, `/sync-docs`
8. Then the upstream architecture guide below.

## Key decisions (already made, do not re-open)
| Topic | Decision |
|---|---|
| User | Exactly one person, local only (Windows 11). No hosting, no multi-user setup. |
| Claude | Upstream's built-in `claude_code` provider (Agent SDK → official Claude Code CLI, Rony's own login). No code change. |
| Gemini | New `antigravity_acp` provider driving the **unmodified** `agy acp` (ACP over stdio). Print-mode shim only if ACP breaks, and only after asking. |
| Safety | `--sandbox`, empty temp cwd, deny all permission requests, no fs/terminal for the agent, never touch credentials or Google endpoints. |
| Tools | Emulated with a strict JSON reply protocol (07 §4). |
| Embeddings | No code change. Gemini `gemini-embedding-001` (free AI Studio key) or Ollama `nomic-embed-text`. |
| Fork hygiene | New files over edits. Marked edits in upstream files. `FORK_NOTICE.md` lists every change. Upstream tests must not regress. |
| Git | Commit locally after every task. Remotes: `origin` = public fork `RHRONY05/DeepTutor`, `upstream` = HKUDS. **Push to `origin` only when Rony asks.** |
| Docs follow code | Any change updates the owning `.agent/` doc in the same commit (map in the rules). `/sync-docs` repairs drift. |

## Status
- [x] Planning + ACP spike (2026-11-14)
- [ ] Build V0 → V6
- [x] Course workspaces V7–V13 + V15 (2026-11-15; V14 per-course memory deferred). Design: [.agent/10-COURSE-WORKSPACES.md](.agent/10-COURSE-WORKSPACES.md)

---
<!-- fork(antigravity_acp) end -->

# DeepTutor — Agent-Native Architecture

## Overview

DeepTutor is an **agent-native** intelligent learning companion organized
around a two-layer plugin model — single-shot **Tools** invoked by the
LLM, and multi-stage **Capabilities** that take over a turn — exposed
through three entry points: CLI, WebSocket API, and Python SDK. All three
enter the durable turn application service before the shared turn engine
routes a normalized context to the selected capability.

## Architecture

```
Entry Points:  CLI (Typer)  |  WebSocket /ws  |  Python SDK
                    ↓                   ↓                   ↓
              ┌─────────────────────────────────────────────────┐
              │          TurnApplicationService                 │
              │   persists, coordinates, and replays turns      │
              └──────────────────────┬──────────────────────────┘
                                     ↓
              ┌─────────────────────────────────────────────────┐
              │       TurnEngine → ChatOrchestrator              │
              │   routes UnifiedContext → selected Capability    │
              │   (defaults to `chat`)                           │
              └──────────┬──────────────┬───────────────────────┘
                         │              │
              ┌──────────▼──┐  ┌────────▼──────────┐
              │ ToolRegistry │  │ CapabilityRegistry │
              │  (Level 1)   │  │   (Level 2)        │
              └──────────────┘  └────────────────────┘
```

`TurnApplicationService` owns durable turn state and replay through the
session store and runtime coordinator. Each execution uses a per-turn
`StreamBus`; the orchestrator emits events, the turn runtime persists them,
and adapters replay them to consumers. Runtime settings live in
`data/user/settings/*.json` — project-root `.env` files are intentionally
ignored.

### Level 1 — Tools

Single-function tools the LLM picks on demand. Eight user-toggleable tools
surface in `/settings/tools`:

| Tool                 | Description                                   |
| -------------------- | --------------------------------------------- |
| `brainstorm`         | Breadth-first idea exploration with rationale |
| `web_search`         | Web search with citations                     |
| `paper_search`       | arXiv preprint search                         |
| `zotero_search`      | Search a configured Zotero library            |
| `reason`             | Dedicated deep-reasoning LLM call             |
| `geogebra_analysis`  | Analyze math images into GeoGebra commands    |
| `imagegen`           | Generate images                               |
| `videogen`           | Generate videos                               |

`USER_TOGGLEABLE_TOOL_NAMES` in `deeptutor/tools/builtin/__init__.py` is the
authoritative toggle list. Other built-ins are **context-gated** or
capability-owned: `CONFIGURABLE_BUILTIN_TOOL_NAMES` declares the context-gated
surface, while `deeptutor/agents/_shared/tool_composition.py` owns the mount
rules (`ToolMountFlags`) and the always-available workspace tools. Examples
include `rag`, memory and notebook tools, `read_skill`, deferred MCP/CLI tools,
`exec`, `ask_user`, and mastery navigation. `--tool` selects from the
user-toggleable whitelist; it does not bypass context or capability gates.

### Level 2 — Capabilities

Multi-stage pipelines that own the turn:

| Capability       | Stages                                                |
| ---------------- | ----------------------------------------------------- |
| `chat`           | exploring → responding (single agentic loop, default) |
| `ask_questions`  | responding (chat loop forced through `ask_user`)      |
| `deep_solve`     | responding (chat loop + solve planning tools)         |
| `deep_question`  | ideation → generation                                 |
| `deep_research`  | rephrasing → decomposing → researching → reporting    |
| `visualize`      | analyzing → generating → reviewing (SVG / Chart.js / Mermaid / HTML; or routes to Manim sub-stages via `render_type`) |
| `math_animator`  | concept_analysis → concept_design → code_generation → code_retry → summary → render_output |
| `mastery_path`   | responding (Guided Learning — chat loop + mastery tools, gated per topic type) |
| `immersive_reading` | responding (document- or timestamp-grounded media reading loop) |
| `video_lesson`   | code_generation → render_check → render_output (Remotion lesson played live in the browser, with TTS narration) |

All capabilities converge on `emit_capability_result()` in
`deeptutor/agents/_shared/capability_result.py` so every turn emits the same envelope
(response payload + `cost_summary` from `UsageTracker`). Status copy and
prompts are i18n'd via `capabilities/prompts/{en,zh}/<name>.yaml`.

## CLI Usage

```bash
# Install from the current dev source checkout
python -m pip install -r requirements/full.txt
python -m pip install -e . --no-deps

# Alternative in 1.7.0: choose one in a separate wheel environment
python -m pip install "deeptutor[full]"  # Full app, CLI + Web/API
python -m pip install deeptutor         # Core CLI/SDK (chat + ask_questions)
python -m pip install deeptutor-cli     # Compatibility alias for core

# Run any capability
deeptutor run chat "Explain Fourier transform"
deeptutor run deep_solve "Solve x^2=4" --kb my-kb
deeptutor run visualize "Animate sine wave" --config render_mode=manim_video

# Interactive REPL
deeptutor chat
# (inside the REPL: /regenerate or /retry re-runs the last user message)

# Partners (IM-connected companions)
deeptutor partner list

# Knowledge bases, memory, server
deeptutor kb list
deeptutor kb create my-kb --doc textbook.pdf
deeptutor memory show
deeptutor serve --port 8001       # API server only
deeptutor start                   # backend + frontend together
```

Examples beyond core require their owning modules; use `deeptutor module list`
to inspect installed/enabled/ready states and `deeptutor plugin list` to discover
registered capabilities and tools. Source Web startup also needs Node.js 22 LTS
and `npm ci --legacy-peer-deps` in `web/`. CLI-only source users can skip frontend
setup, but still need the full Python dependencies. Follow
[Agent Setup](docs-for-dev/AGENT_SETUP.md) for credentials and verification.

## Key Files

| Path                                       | Purpose                              |
| ------------------------------------------ | ------------------------------------ |
| `deeptutor/runtime/orchestrator.py`        | `ChatOrchestrator` — unified entry   |
| `deeptutor/runtime/launcher.py`            | Backend + frontend lifecycle / port discovery |
| `deeptutor/runtime/registry/`              | Tool + Capability registries         |
| `deeptutor/runtime/bootstrap/builtin_capabilities.py` | Built-in capability class paths |
| `deeptutor/services/config/runtime_settings.py` | JSON settings + process-env overrides |
| `deeptutor/services/subagent/`             | Local/remote agent connectors; register each backend in `registry.py` and its model options in `models.py` (Grok CLI uses native `streaming-json`) |
| `deeptutor/core/stream.py`, `deeptutor/runtime/stream_bus.py` | StreamEvent protocol + async fan-out |
| `deeptutor/core/tool_protocol.py`          | `BaseTool` + `ToolDefinition`         |
| `deeptutor/core/capability_protocol.py`    | `TurnCapability` + `CapabilityManifest` |
| `deeptutor/core/context.py`                | `UnifiedContext` dataclass            |
| `deeptutor/tools/builtin/__init__.py`      | All built-in tool wrappers           |
| `deeptutor/capabilities/`                  | Built-in capability implementations  |
| `deeptutor/app/`                           | `DeepTutorApp` SDK facade + durable application service |
| `deeptutor_cli/main.py`                    | Typer CLI entry point                |
| `deeptutor/api/routers/unified_ws.py`      | Unified WebSocket endpoint           |
| `apps/desktop/`                            | Open DeepTutor desktop apps for MacOS and Windows (Electron shell + bundled core; per-target builds in `platforms/`) |

## Dependency Layers

The 1.7.0 layout is modular; 1.6.15 and earlier packages use the
previous layout. Core owns the CLI, SDK and shared runtime; feature wheels must
match its version. `deeptutor-cli` is a metadata-only compatibility alias.
For development, use source or [local wheels](docs-for-dev/MODULES.md).

Module manifests own dependency groups; generated requirements files support
source, Docker and CI installs. `pyproject.toml` stores extra templates under
`tool.deeptutor.optional-dependencies`; `build_metadata.py` resolves same-version
wheel pins. Source checkouts expose all modules and install external dependencies
through `requirements/full.txt`, followed by `pip install -e . --no-deps`.
Use the source helper for optional extras rather than installing feature wheels
over the checkout:

```bash
python scripts/install_extras.py partners       # Partner channel SDKs
python scripts/install_extras.py matrix         # Matrix channel without E2EE/libolm
python scripts/install_extras.py matrix-e2e     # Matrix with end-to-end encryption
python scripts/install_extras.py math-animator  # Manim; also needs system LaTeX/ffmpeg
python scripts/install_extras.py dev            # Test / lint tooling
python scripts/install_extras.py all            # Full + Manim + dev dependencies
```

Stop DeepTutor before module changes. Source supports `module enable/disable`;
wheel environments also support `module install/uninstall`. Upgrading a legacy
`deeptutor-cli` installation requires uninstalling it before installing the new
packages, preserving the same `DEEPTUTOR_HOME`; see the setup guide. Validate
with `python -m pip check`, `deeptutor module list`, and the setup readiness checks.

## Desktop Release Requirement

Starting with the release after v1.7.1, publish the Intel Mac (`macos-x64`)
DMG together with the Apple Silicon (`macos-arm64`) DMG and Windows installer
and portable ZIP for every version. Wait for the Desktop Release workflow,
including `verify-release`, and verify the downloads on the actual GitHub
Release before reporting completion. If any platform fails, fix and rerun it;
do not silently omit Intel Mac or treat a partial desktop release as complete.
See `apps/desktop/README.md` for the build and publication flow.
