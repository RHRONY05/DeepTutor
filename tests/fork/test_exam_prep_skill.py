# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"""Unit tests for the exam-prep builtin skill."""

from __future__ import annotations

from pathlib import Path

from deeptutor.services.skill.service import BUILTIN_SKILLS_ROOT, SkillService


def test_exam_prep_skill_listed_from_builtin(tmp_path: Path) -> None:
    """SkillService lists exam-prep from the builtin root with source 'builtin' and non-empty description."""
    service = SkillService(root=tmp_path / "user_skills", builtin_root=BUILTIN_SKILLS_ROOT)
    skills = service.list_skills()
    info = next((s for s in skills if s.name == "exam-prep"), None)

    assert info is not None, "exam-prep skill should be discovered by SkillService"
    assert info.source == "builtin"
    assert len(info.description.strip()) > 0


def test_exam_prep_skill_body_contents(tmp_path: Path) -> None:
    """read_skill_file body mentions ask_user, exams/, dependency order / prerequisites, and Skipped."""
    service = SkillService(root=tmp_path / "user_skills", builtin_root=BUILTIN_SKILLS_ROOT)
    body = service.read_skill_file("exam-prep")

    assert "ask_user" in body
    assert "exams/" in body
    assert "dependency order" in body or "prerequisites" in body
    assert "Skipped" in body
