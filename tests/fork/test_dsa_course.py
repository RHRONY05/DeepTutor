# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Tests for the DSA practice course: the dsa-tutor skill, templates and setup script helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from deeptutor.services.skill.service import BUILTIN_SKILLS_ROOT, SkillService

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "deeptutor" / "services" / "course" / "templates"


def _setup_module():
    spec = importlib.util.spec_from_file_location(
        "setup_dsa_course", ROOT / "scripts" / "fork" / "setup_dsa_course.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dsa_tutor_skill_is_builtin(tmp_path: Path) -> None:
    service = SkillService(root=tmp_path / "user_skills", builtin_root=BUILTIN_SKILLS_ROOT)
    info = next((s for s in service.list_skills() if s.name == "dsa-tutor"), None)
    assert info is not None
    assert info.source == "builtin"
    body = service.read_skill_file("dsa-tutor")
    # Hints come before solutions, and progress goes through the pattern groups.
    assert "Never paste a full solution" in body
    assert "update_topics" in body
    assert "learning" in body and "known" in body


def test_dsa_templates_fit_limits() -> None:
    from deeptutor.services.workspace.models import MAX_WORKSPACE_INSTRUCTIONS_CHARS

    instructions = (TEMPLATES / "dsa_instructions.md").read_text(encoding="utf-8")
    assert len(instructions) <= MAX_WORKSPACE_INSTRUCTIONS_CHARS
    assert "dsa-tutor" in instructions
    assert "exam-prep" in instructions  # tells the tutor not to use it here
    assert (TEMPLATES / "dsa_mentor_persona.md").read_text(encoding="utf-8").strip()


def test_group_syllabus_lists_lessons_and_problem_links() -> None:
    module = _setup_module()
    pattern = {
        "name": "Hash Tables",
        "phase": 1,
        "read_first": [{"title": "Introduction to Hash Tables", "url": "https://example.test/ht"}],
        "video": "",
        "problems": [
            {
                "title": "Group Anagrams",
                "difficulty": "Medium",
                "leetcode": "https://leetcode.com/problems/group-anagrams/",
                "lesson": "https://example.test/group-anagrams",
            }
        ],
    }
    text = module.group_syllabus(pattern)
    assert "phase 1" in text
    assert "[Introduction to Hash Tables](https://example.test/ht)" in text
    assert (
        "| 1 | Group Anagrams | Medium | [LeetCode](https://leetcode.com/problems/group-anagrams/)"
        in text
    )


def test_group_syllabus_without_new_lessons() -> None:
    module = _setup_module()
    text = module.group_syllabus(
        {
            "name": "Strings",
            "phase": 1,
            "read_first": [],
            "video": "https://youtu.be/x",
            "problems": [],
        }
    )
    assert "Nothing new" in text
    assert "Video intro: https://youtu.be/x" in text
