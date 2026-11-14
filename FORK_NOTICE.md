# Fork notice

This is a personal fork of **[DeepTutor](https://github.com/HKUDS/DeepTutor)** by HKUDS and its
contributors, licensed under the
[Apache License 2.0](./LICENSE). All credit for DeepTutor itself goes to its authors and contributors.

Fork maintained by **RH.RONY** (Muhammad Rony). It was forked from upstream `main` at commit `60fb3bdfd`
(2026-11-06, v1.7.2). Upstream remote: `upstream` → `https://github.com/HKUDS/DeepTutor.git`.

## What the fork adds
- **`antigravity_acp` provider:** DeepTutor's tutor can run on Gemini through a Google AI Pro
  subscription, by driving the official Antigravity CLI in its documented ACP server mode (`agy acp`).
  No API key. Design: [.agent/07-ACP-PROVIDER.md](./.agent/07-ACP-PROVIDER.md).
- **Course workspaces:** each workspace is a university course with exam groups (`exams/<slug>/`),
  an exam-prep teaching skill, notes as a folder tree, and a Courses page. Design:
  [.agent/10-COURSE-WORKSPACES.md](./.agent/10-COURSE-WORKSPACES.md).
- Setup notes for upstream's built-in **Claude Code (subscription)** provider and free embeddings.

## Changed files (Apache-2.0 §4b)
Modified upstream files carry a `Modified in the RH.RONY fork` header line, and their edits sit between
`fork(antigravity_acp)` markers. Added files carry an `Added in the RH.RONY fork` header.

| File | Status | Why |
|---|---|---|
| `AGENTS.md` | modified | Fork block at the top pointing builders to `.agent/` |
| `CLAUDE.md` | added | `@AGENTS.md` so Claude Code reads the same file |
| `FORK_NOTICE.md` | added | This notice |
| `.agent/` | added | Fork plan, rules and progress for AI builders |
| `deeptutor/services/llm/provider_core/acp_client.py` | added | Minimal ACP (JSON-RPC over stdio) client |
| `deeptutor/services/llm/provider_core/antigravity_acp_provider.py` | added | The Antigravity provider (`agy acp`) |
| `deeptutor/services/settings/quick_connect.py` | added | One-click connect for Claude Code / Antigravity |
| `web/components/settings/SubscriptionConnectCard.tsx` | added | "Connect Claude Code / Connect Antigravity" buttons |
| `tests/services/llm/test_antigravity_acp_provider.py`, `tests/services/llm/fake_acp_agent.py` | added | Unit tests with a fake `agy` |
| `scripts/fork/agy_acp_smoke.py` | added | Manual live smoke test |
| `deeptutor/services/provider_registry.py` | modified | `antigravity_acp` spec + aliases (`agy`, `antigravity`) |
| `deeptutor/services/llm/provider_factory.py` | modified | Backend branch |
| `deeptutor/services/llm/provider_core/__init__.py` | modified | Lazy export |
| `deeptutor/runtime/agentic/client.py` | modified | Agent-loop adapter, tool-capable backend |
| `deeptutor/services/llm/capabilities.py` | modified | Capabilities + session-scoped binding |
| `deeptutor/multi_user/model_access.py` | modified | Owner-bound binding |
| `deeptutor/services/llm/factory.py` | modified | Model listing |
| `deeptutor/services/settings/provider_probe.py` | modified | CLI-login providers list models without a URL (also fixes "Get model list" for Claude Code) |
| `deeptutor/api/routers/settings.py` | modified | No base URL needed; catalog branch; `POST /api/settings/quick-connect` |
| `web/components/settings/ServiceConfigEditor.tsx` | modified | `antigravity_acp` is a CLI-login binding |
| `web/components/settings/ProvidersWorkspace.tsx` | modified | Shows the connect card on Settings → Providers |
| `web/lib/provider-branding.ts` | modified | Antigravity icon |
| `scripts/fork/start-deeptutor.cmd` | added | One-click local launcher |
| `deeptutor/services/course/` (`exam_groups.py`, `settings.py`) | added | Exam groups as folders + per-course settings sidecar |
| `deeptutor/api/routers/courses.py` | added | `/api/courses` (courses, exam groups, uploads, settings) |
| `deeptutor/modules/manifests/server.json` | modified | Route entry for `/api/courses` (JSON, no comment marker) |
| `deeptutor/capabilities/notes/tree.py` | added | Folder paths, tree outline and move for notebook pages |
| `deeptutor/capabilities/notes/tools.py` | modified | `write_note` folder/parent, new `note_tree` and `move_note` tools |
| `deeptutor/modules/manifests/co-writer.json` | modified | Registers `note_tree`, `move_note` (JSON, no comment marker) |
| `deeptutor/agents/_shared/tool_composition.py` | modified | Fork note/exam tools are always-available workspace tools |
| `tests/capabilities/test_obsidian_capability.py`, `tests/capabilities/test_subagent_capability.py`, `tests/tools/test_kb_files_tool.py` | modified | Pinned baseline tool lists include the fork tools |
| `web/app/(workspace)/courses/`, `web/components/courses/`, `web/lib/courses-api.ts` | added | Courses page, exam-group list/detail, uploads, folder tree |
| `web/components/sidebar/nav-entries.ts`, `CategoryNavigation.tsx`, `page-sections.ts` | modified | "Courses" link in the sidebar Home shelf |
| `deeptutor/skills/builtin/exam-prep/SKILL.md` | added | Exam-prep teaching playbook (prerequisites first, PYQs, skipped list) |
| `deeptutor/services/course/templates/exam_prep_instructions.md` | added | Default course instructions template |
| `deeptutor/tools/exam_groups.py` | added | `exam_groups` tool: list/get/create/update groups and topic progress from chat |
| `deeptutor/modules/manifests/core.json` | modified | Registers `exam_groups` (JSON, no comment marker) |
| `tests/fork/` | added | Tests for the course-workspace features |

## Test-only settings
- `DEEPTUTOR_LIVE_AGY=1` (set in the shell) runs the live Antigravity tests. They spend real quota.

## Using the subscription providers
1. Sign in once in a terminal: `claude` (Claude Pro/Max) and/or `agy` (Google AI Pro).
2. Settings → Providers → **Connect a subscription** → *Connect Claude Code* or *Connect Antigravity*.
   This creates the provider plus a main and a light model, and makes them the chat model and the task model.
3. Switch between them any time with the same buttons, or under Settings → Language models / Task models.

Antigravity uses whichever Google account `agy` is signed into (the same login the Antigravity
desktop app uses). Each turn costs ~19–20k input tokens of Antigravity overhead and takes ~10–20 s.
