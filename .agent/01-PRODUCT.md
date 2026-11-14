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

## Out of scope (v1)
- Images or files sent to the Antigravity model (text only).
- Claude/GPT models listed by `agy` (Gemini only).
- Cleaning up Antigravity CLI conversation history that ACP sessions create.
- Picking the Google account from inside DeepTutor. The account is whatever `agy` is signed into. See PROGRESS "Human steps".
- The print-mode (`agy -p`) shim. Only if ACP breaks (07 §9).
- Any other DeepTutor customisation, renaming, Docker, or the desktop build.
- Pushing to GitHub or creating a fork there.
