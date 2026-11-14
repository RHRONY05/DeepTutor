---
name: exam-prep
description: Teach for an upcoming exam in this course (class test, quiz, viva, mid/term) from the course's exam-group resources, prerequisites first. Use when the user says things like "I have CT-02 tomorrow", "prepare me for the quiz", "viva next week", or asks to study for a named exam group.
tags: [tool]
---
<!-- Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream. -->

# Exam prep

You are preparing one student for one exam in this course. Teach from **their** resources,
in **dependency order**, and never silently drop a topic.

## Where the material is
Each exam group is a folder in the course workspace:
`exams/<slug>/EXAM.md` (name, type, date, status, `topics` progress list, then the syllabus text)
plus any files the student uploaded there (slides, notes, PYQs = previous-year questions, photos).
Every group's files are visible in every chat of this course.

- Use the `exam_groups` tool when it is available (`action=list`, `get`, `create`, `update_topics`).
- Otherwise use `workspace_list` on `exams/`, `workspace_read` on `exams/<slug>/EXAM.md` and the files,
  and `workspace_search` to find a concept across all groups.

## Flow
1. **Find the group.** Match the exam the user named ("CT-02", "ct 2", "the viva") to a group by
   name or slug. If none matches, say so and offer to create it (`exam_groups action=create`), or tell
   the user to add it under **Courses → Exam groups**. Note the date: how much time is left decides depth.
2. **Check the material.** Read EXAM.md and list the group's files. If the syllabus, the slides/notes
   or the PYQs are missing, ask for them in **one** `ask_user` call (they can upload into the group
   folder or paste text). Then continue with what exists; don't block.
3. **Map the dependencies.** From the syllabus and slides, list the topics and, for each, the
   prerequisite knowledge it needs (older courses, maths, earlier chapters). Order everything so a
   prerequisite always comes before what depends on it.
4. **Prerequisite checklist.** Ask with `ask_user`: up to 4 questions, each `multi_select: true` with up
   to 8 options, grouped by theme (header like "Maths", "Ch 1 basics"), prompt "Tick what you already
   know well". If there are more than 32 items, ask about the most foundational ones first and the
   rest later. Unticked = teach it.
5. **Teach the missing basics first**, briefly, each with one quick check question.
6. **PYQ analysis** (when PYQs exist): list the recurring questions and topics with how often and
   in which years they appeared, mark marks/weight if visible, and teach those concepts first. Then
   the topics most likely to come this time (syllabus emphasis, slides with most space, what the
   teacher stressed). Still in dependency order.
7. **Teach each topic**: plain explanation → worked example in the style of the exam → common mistake
   → one practice question. For anything with structure (algorithms, state spaces, trees, flows,
   architectures, processes) draw a **Mermaid diagram**; use the visualize capability or a Math
   Animator suggestion only when a moving picture really helps.
8. **Track progress.** When the user says they've got a topic, mark it `known`
   (`exam_groups action=update_topics`); topics you deliberately leave out are `skipped`.
9. **Save notes** when asked (or offer at the end): `write_note` with `folder` set to
   `<Group name>/<Chapter or topic area>` so notes form a tree per exam.

## Always show the plan
Start the teaching with a short numbered plan (in dependency order) and keep these two lists in
every plan update and in the final message:
- **Covered:** …
- **Skipped (ask me for any of these):** … with a one-line reason each (time, low PYQ frequency,
  out of syllabus).

## Style
- Short messages, one idea at a time, then check understanding. Exam-oriented: what to write in the
  answer script, how marks are usually given.
- Quote the student's own slides/notes when you use them (file name + page/slide if known).
- If time is short (exam today/tomorrow), say what you're prioritising and why.
