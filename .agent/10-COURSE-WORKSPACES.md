# 10 — Course workspaces (fork feature set 2)

> Fork addition. Planned by Claude, built by Antigravity (`agy`) task by task (V7 onwards in `08-TASKS.md`).
> Fork markers for this set: `fork(course_workspaces) start` / `fork(course_workspaces) end`.

## Goal
Each university course is one DeepTutor **workspace**. Inside it Rony keeps **exam groups**
(`ct-01`, `quiz-viva`, `mid-term` …) with their syllabus and resources, and the tutor teaches him
for the next exam from those resources, prerequisites first, with notes filed as a folder tree.

## What already exists (do not rebuild)
| Need | Existing piece |
|---|---|
| Workspace = course | `deeptutor/services/workspace/` (catalog in `data/user/.runtime/workspaces.sqlite3`), content root `data/user/workspaces/<ws_id>/`, per-request scope from `?dt_workspace=` (`web/lib/workspace-scope.ts`, `services/workspace/context.py`) |
| Read any workspace file from chat | `workspace_list/search/read` (`deeptutor/tools/workspace.py`), always mounted (`WORKSPACE_BASELINE_TOOLS`) |
| Workspace instructions (≤10k chars) | catalog row `instructions`, injected in `deeptutor/agents/loop/prompt_blocks.py` (chat loop only) |
| Skills | `SKILL.md` playbooks; builtin root `deeptutor/skills/builtin/`, manifest in the prompt, body via `read_skill` |
| Checklist questions | `ask_user` (`deeptutor/tools/ask_user.py`): up to 4 questions × 8 options, `multi_select` |
| Diagrams | Mermaid renders in chat; `visualize` capability; Math Animator |
| Notes tree | Co-Writer pages have `parent_id` (`deeptutor/co_writer/storage.py`); page tree UI exists. Pages live per workspace. |
| Personas | `data/user/workspace/personas/<name>/PERSONA.md`, API `web/lib/personas-api.ts` |

## Data model (new, all fork-owned)
### Exam groups: plain files inside the course folder
```
<workspace root>/exams/<slug>/EXAM.md        # metadata + syllabus
<workspace root>/exams/<slug>/<any files>     # slides, notes, PYQs, photos …
```
`EXAM.md` = YAML frontmatter + Markdown body (the syllabus text):
```yaml
---
name: CT-02
type: class_test        # class_test | quiz | viva | mid_term | term_final | assignment | other
date: 2026-11-15        # ISO date, optional
status: preparing       # planned | preparing | done
topics:                 # progress checklist, optional; the tutor and the UI both edit it
  - {title: "Uninformed search", status: known}     # todo | learning | known | skipped
---
Syllabus text …
```
Why files: the chat agent already reads them with `workspace_list/read/search`, so **every chat in the
course sees every group's resources** with no new retrieval code, and Rony can drop files in with
Explorer. Slug: lowercase `[a-z0-9-]`, max 48, unique per course. No database.

### Course settings sidecar
`data/user/settings/fork_courses.json` → `{"<workspace_id>": {"default_persona": "<name>|''"}}`.
Fork-owned file, so no change to the upstream catalog schema.

## Backend
- `deeptutor/services/course/exam_groups.py` (new): pure functions over a root `Path`:
  `list_groups(root)`, `get_group(root, slug)`, `create_group(root, name, type, date, syllabus)`,
  `update_group(root, slug, **fields)`, `delete_group(root, slug)` (refuses if the folder holds
  files other than `EXAM.md` unless `force=True`), `save_upload(root, slug, filename, bytes)`,
  `file_tree(root, slug)`. Path confinement: resolve and check `is_relative_to(root/exams/slug)`;
  reject `..`, absolute names, reserved Windows names; 50 MB per file.
- `deeptutor/services/course/settings.py` (new): read/write the sidecar.
- `deeptutor/api/routers/courses.py` (new), mounted at `/api/courses` (route entry added to
  `deeptutor/modules/manifests/server.json`, which is JSON so it gets no comment marker; listed in
  `FORK_NOTICE.md`):
  - `GET /api/courses` → workspaces of kind `workspace` (+ General) with group counts and next exam.
  - `GET|POST /api/courses/{ws}/groups`, `GET|PATCH|DELETE /api/courses/{ws}/groups/{slug}`
  - `POST /api/courses/{ws}/groups/{slug}/files` (multipart), `DELETE …/files?path=`
  - `GET|PUT /api/courses/{ws}/settings` (default persona)
  - `GET /api/courses/{ws}/instructions` → `{base_prompt (read-only), workspace_instructions, persona, exam_prep_skill}`
  Workspace root comes from `get_content_workspace_service().binding_by_id(ws).root`.

## Exam-prep teaching flow (skill first, code only where needed)
`deeptutor/skills/builtin/exam-prep/SKILL.md` (new). Triggered by "I have CT-02 tomorrow" etc.
1. Find the group: `workspace_list exams/`, read `exams/<slug>/EXAM.md`. If no group matches, offer to create
   one (tell the user to use Courses → Exam groups, or file it via `workspace` tools if writable).
2. Missing-material check: syllabus, slides/notes, PYQs. Ask for what's missing with `ask_user`; continue with what exists.
3. Prerequisite checklist: build the dependency list (prerequisite → dependent). Ask with `ask_user`,
   `multi_select`, up to 4 grouped questions × 8 options ("Tick what you already know"). More than 32 → ask
   about the foundational ones first.
4. Teach unknown prerequisites first (short, with a Mermaid diagram when structure helps).
5. PYQ analysis: list recurring questions/topics with frequency; teach those concepts first, then the
   most-likely topics, always in dependency order.
6. Keep a **Skipped topics** list in every plan message and at the end, so the user can ask for them.
7. Save notes with `write_note` under folder `<Group name>/<Chapter>` (V10), and update the group's
   `topics` progress when the user confirms they know a topic.
Default workspace instructions template (shown in the Instructions panel as "Insert exam-prep defaults"):
`deeptutor/services/course/templates/exam_prep_instructions.md` (new).
Decision: no new checklist card for now; 4×8 `ask_user` covers a CT syllabus. Revisit if it doesn't.

## Notes tree (V10)
`write_note` gets optional `parent_id` and `folder` (e.g. `"CT-02/Chapter 1"`): each path segment is found by
title among the children of the previous one, or created as an empty page. New tools in
`deeptutor/capabilities/notes/tools.py`: `note_tree` (indented outline of all pages with ids) and
`move_note` (page_id, new parent_id or folder, `""` = top level). Registered in
`deeptutor/modules/manifests/co-writer.json` and added to `WORKSPACE_BASELINE_TOOLS`.

## UI
- Sidebar entry **Courses** (`/courses`) in `web/components/sidebar/nav-entries.ts`.
- `/courses`: cards of courses (workspaces) → click selects the workspace and opens `/courses/[ws]`.
- `/courses/[ws]`: tabs **Exam groups** (list + detail: name/type/date/status, syllabus editor, topic
  progress, upload files, folder tree), **Instructions** (V11).
- New files under `web/app/(workspace)/courses/`, `web/components/courses/`, `web/lib/courses-api.ts`.

## Instructions panel (V11)
Three editable columns + one read-only: Persona (picker + PERSONA.md editor via personas API, plus
"default persona for this course"), Workspace instructions (existing PATCH registrations), Exam-prep
skill (read-only builtin view with "copy to my skills to edit"), Base prompt (read-only).
Default persona applies when a chat in that workspace has no persona chosen.

## Built (as of 2026-11-14)
- `exam_groups` chat tool (`deeptutor/tools/exam_groups.py`, always mounted with the workspace tools) — list/get/create/update/update_topics.
- Default persona: `executor.py` falls back to `default_persona_for_current_workspace()` when the turn requested none.
- Course instructions reach quiz generation (explore, plan, quiz step) and Deep Research (decompose, research blocks, report outline/intro/sections/conclusion) via `deeptutor/services/course/instructions.py`.
- `youtube_find` (`deeptutor/tools/youtube_find.py`): user-toggleable; web search → YouTube candidates → captions via `resolve_youtube_captions` → keyword/timestamp scoring, educator bonus, shorts penalty; unverified videos listed separately.
- Sidebar: Courses link in `CategoryNavigation.tsx` + `page-sections.ts` (`nav-entries.ts` keeps the policy entry).
- V14 per-course memory: deferred (see 08).
