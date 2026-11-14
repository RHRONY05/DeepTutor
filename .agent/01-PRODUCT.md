# 01 — What this change does

> Fork addition (not part of upstream DeepTutor).

**User:** exactly one person (Rony) running DeepTutor locally on his Windows PC for his own studying
(first course: Computer Networks, notes in `E:\Learning\Courses\3-2\CN`). No other users, no hosting.

**Problem:** DeepTutor normally needs paid API keys. Rony pays for Claude Pro (not always) and
Google AI Pro (for the next year). He wants DeepTutor's tutor to run on those subscriptions, within each
provider's terms.

## User stories
- **US1** As Rony, I can pick **Antigravity (Google AI Pro subscription)** as a provider in Settings → Providers with no API key, press "Sync models", and choose a Gemini model.
- **US2** As Rony, I can chat with the tutor on that model. Replies stream in, follow-up questions remember the conversation, and a Stop button actually stops it.
- **US3** As Rony, DeepTutor features that call tools (e.g. web search, knowledge base lookup) still work on that model.
- **US4** As Rony, I can switch the language model and task model between **Claude Code (subscription)** and **Antigravity** in Settings without editing files.
- **US5** As Rony, knowledge-base indexing works with a free embedding model (Gemini free tier or Ollama).
- **US6** As Rony, when `agy` is missing, signed out or out of quota, I see a clear message saying what to do, not a stack trace.

## Course workspaces (feature set 2, V7–V15, design in 10)
- **US7** As Rony, each university course is a workspace listed on a **Courses** page (sidebar → Home → Courses).
- **US8** In a course I keep **exam groups** (CT-01, quiz-viva, mid-term …) with type, date, status, syllabus, a topic checklist (todo/learning/known/skipped) and uploaded files (slides, notes, PYQs, in subfolders). Every chat in the course can read every group's files.
- **US9** When I say "I have CT-02 tomorrow", the tutor follows the **exam-prep** skill: finds the group, asks for missing material, shows a "tick what you know" prerequisite checklist, teaches missing basics first, analyses PYQs, teaches in dependency order with Mermaid diagrams, and always lists **Skipped** topics.
- **US10** The tutor files notes as a folder tree (`<Exam group>/<Chapter>`), can show the tree and move pages.
- **US11** An **Instructions** tab per course shows and edits the course's default persona, the course instructions (with "insert exam-prep defaults"), the exam-prep skill (editable copy) and the read-only base prompt. Course instructions also reach quiz generation and Deep Research.
- **US12** A **YouTube Finder** tool recommends lectures only after checking their captions, with title, channel, link, start timestamp and why. Toggle it in the chat composer's tools.
- Limits: exam-group uploads ≤ 50 MB each; course instructions ≤ 10k chars; Courses UI is English only.
- Deferred: per-course memory (memory stays account-wide; reason in 08 V14). Out of scope: Obsidian link, cloud/mobile notes.

## Out of scope (v1)
- Images or files sent to the Antigravity model (text only).
- Claude/GPT models listed by `agy` (Gemini only).
- Cleaning up Antigravity CLI conversation history that ACP sessions create.
- Picking the Google account from inside DeepTutor. The account is whatever `agy` is signed into. See PROGRESS "Human steps".
- The print-mode (`agy -p`) shim. Only if ACP breaks (07 §9).
- Any other DeepTutor customisation, renaming, Docker, or the desktop build.
- Pushing to GitHub or creating a fork there.
