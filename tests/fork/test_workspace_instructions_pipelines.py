# Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from deeptutor.agents.question.pipeline import (
    QuestionPipeline,
    QuizPlan,
    QuizTemplate,
)
from deeptutor.agents.research.pipeline import (
    ReportOutline,
    ResearchPipeline,
)
from deeptutor.core.context import (
    TurnRuntimeContext,
    UnifiedContext,
    WorkspaceRuntimeContext,
)
from deeptutor.runtime.agentic import LabeledStepResult, LoopOutcome
from deeptutor.runtime.stream_bus import StreamBus
from deeptutor.services.course.instructions import (
    INSTRUCTION_HEADING,
    workspace_instruction_block,
)
from deeptutor.services.llm.config import LLMConfig

# ---------------------------------------------------------------------------
# Test Helpers & Stubs
# ---------------------------------------------------------------------------


class _StubStreamBus:
    """Minimal stream bus stub for capturing pipeline progress/content."""

    def __init__(self) -> None:
        self.contents: list[dict[str, Any]] = []
        self.progress_events: list[dict[str, Any]] = []

    async def content(
        self,
        text: str,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.contents.append({"text": text, "source": source, "stage": stage})

    async def progress(
        self,
        message: str,
        current: int = 0,
        total: int = 0,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.progress_events.append({"message": message, "source": source, "stage": stage})


class _FakeToolRegistry:
    def build_openai_schemas(self, _names):
        return []

    def build_prompt_text(self, _names, **_kwargs):
        return "- none"

    def get(self, _name):
        return None

    def get_enabled(self, _names):
        return []


def _make_context(instructions: str = "") -> UnifiedContext:
    workspace = WorkspaceRuntimeContext(
        workspace_id="test-ws",
        instructions=instructions,
    )
    return UnifiedContext(
        user_message="test query",
        language="en",
        runtime=TurnRuntimeContext(workspace=workspace),
    )


# ---------------------------------------------------------------------------
# 1. Helper Unit Tests
# ---------------------------------------------------------------------------


def test_helper_empty_returns_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    # Passed None with no workspace scope
    monkeypatch.setattr(
        "deeptutor.services.workspace.context.current_workspace_id",
        lambda: "",
    )
    assert workspace_instruction_block(None) == ""

    # Passed UnifiedContext with empty instructions
    ctx = _make_context(instructions="")
    assert workspace_instruction_block(ctx) == ""


def test_helper_with_instructions_returns_formatted_block() -> None:
    text = "Always format answers as clear step-by-step proofs."
    ctx = _make_context(instructions=text)
    block = workspace_instruction_block(ctx)

    assert INSTRUCTION_HEADING in block
    assert text in block
    assert block == f"{INSTRUCTION_HEADING}\n{text}"


def test_helper_error_returns_empty_string() -> None:
    class FailingContext:
        @property
        def runtime(self):
            raise RuntimeError("Database connection exploded")

    # Never raises; logs and returns ""
    assert workspace_instruction_block(FailingContext()) == ""


def test_helper_fallback_to_contextvar_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "deeptutor.services.workspace.context.current_workspace_id",
        lambda: "course-42",
    )

    class FakeWorkspaceService:
        def workspace_instructions(self, ws_id: str | None = None) -> str:
            if ws_id == "course-42":
                return "Course 42: Focus on differential calculus."
            return ""

    monkeypatch.setattr(
        "deeptutor.services.workspace.get_content_workspace_service",
        lambda: FakeWorkspaceService(),
    )

    block = workspace_instruction_block(None)
    assert INSTRUCTION_HEADING in block
    assert "Course 42: Focus on differential calculus." in block


# ---------------------------------------------------------------------------
# 2. Question Pipeline Tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_llm_for_question(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "deeptutor.agents.question.pipeline.get_llm_config",
        lambda: LLMConfig(model="test-model", api_key="test-key"),
    )


@pytest.mark.asyncio
async def test_question_pipeline_plan_system_prompt() -> None:
    pipeline = QuestionPipeline(language="en")
    instructions_text = "Emphasize linear algebra fundamentals."

    captured_prompts: list[str] = []
    valid_plan_json = json.dumps(
        {
            "analysis": "Test plan",
            "templates": [
                {
                    "question_id": "Q1",
                    "topic": "vectors",
                    "question_type": "multiple_choice",
                    "difficulty": "easy",
                }
            ],
        }
    )

    async def _fake_step(**kwargs: Any) -> LabeledStepResult:
        messages = kwargs.get("messages") or []
        system_content = messages[0]["content"] if messages else ""
        captured_prompts.append(system_content)
        return LabeledStepResult(
            label="FINISH",
            text=valid_plan_json,
        )

    with patch.object(QuestionPipeline, "_run_labeled_step", side_effect=_fake_step):
        # 1. Baseline: empty instructions
        ctx_empty = _make_context(instructions="")
        await pipeline._plan(
            context=ctx_empty,
            user_message="vectors",
            exploration_trace="",
            num_questions=1,
            difficulty="easy",
            allowed_types=[],
            per_type_counts={},
            stream=_StubStreamBus(),
            client=object(),
        )
        baseline_prompt = captured_prompts[0]

        # 2. Set instructions
        ctx_with_instr = _make_context(instructions=instructions_text)
        await pipeline._plan(
            context=ctx_with_instr,
            user_message="vectors",
            exploration_trace="",
            num_questions=1,
            difficulty="easy",
            allowed_types=[],
            per_type_counts={},
            stream=_StubStreamBus(),
            client=object(),
        )
        instr_prompt = captured_prompts[1]

    from deeptutor.services.prompt.language import append_language_directive

    # When empty: prompt is byte-identical to baseline prompt
    expected_plan_baseline = append_language_directive(
        pipeline._t("plan.system", num_questions=1), pipeline.language
    )
    assert baseline_prompt == expected_plan_baseline
    assert instructions_text not in baseline_prompt
    assert INSTRUCTION_HEADING not in baseline_prompt

    # When set: contains instructions and heading
    assert instructions_text in instr_prompt
    assert INSTRUCTION_HEADING in instr_prompt


@pytest.mark.asyncio
async def test_question_pipeline_quiz_step_system_prompt() -> None:
    pipeline = QuestionPipeline(language="en")
    instructions_text = "Ensure each question tests asymptotic complexity."
    template = QuizTemplate(
        question_id="Q1",
        question_type="choice",
        topic="Big-O",
        difficulty="medium",
    )
    plan = QuizPlan(analysis="test plan", templates=[template])

    captured_prompts: list[str] = []
    valid_quiz_json = json.dumps(
        {
            "question": "What is the complexity of binary search?",
            "options": {"A": "O(log n)", "B": "O(n)", "C": "O(1)", "D": "O(n^2)"},
            "correct_answer": "A",
            "explanation": "Binary search divides the search space in half each step.",
        }
    )

    async def _fake_run_loop(**kwargs: Any) -> LoopOutcome:
        initial_messages = kwargs.get("initial_messages") or []
        system_content = initial_messages[0]["content"] if initial_messages else ""
        captured_prompts.append(system_content)
        return LoopOutcome(
            final_label="FINISH",
            final_text=valid_quiz_json,
            iterations=1,
        )

    with patch("deeptutor.agents.question.pipeline.run_agentic_loop", side_effect=_fake_run_loop):
        # 1. Baseline: empty instructions
        ctx_empty = _make_context(instructions="")
        await pipeline._quiz_one(
            template=template,
            question_number=1,
            total_questions=1,
            exploration_trace="",
            plan=plan,
            previous_pairs=[],
            image_attachments=[],
            context=ctx_empty,
            stream=_StubStreamBus(),
            client=object(),
        )
        baseline_prompt = captured_prompts[0]

        # 2. Set instructions
        ctx_with_instr = _make_context(instructions=instructions_text)
        await pipeline._quiz_one(
            template=template,
            question_number=1,
            total_questions=1,
            exploration_trace="",
            plan=plan,
            previous_pairs=[],
            image_attachments=[],
            context=ctx_with_instr,
            stream=_StubStreamBus(),
            client=object(),
        )
        instr_prompt = captured_prompts[1]

    from deeptutor.services.prompt.language import append_language_directive

    # When empty: prompt is byte-identical to baseline prompt
    expected_quiz_baseline = append_language_directive(
        pipeline._t(
            "quiz_step.system",
            question_number=1,
            total_questions=1,
            kb_note=pipeline._kb_system_note(),
            tool_list=pipeline._tool_list_text(ctx_empty),
        ),
        pipeline.language,
    )
    assert baseline_prompt == expected_quiz_baseline
    assert instructions_text not in baseline_prompt
    assert INSTRUCTION_HEADING not in baseline_prompt

    # When set: contains instructions and heading
    assert instructions_text in instr_prompt
    assert INSTRUCTION_HEADING in instr_prompt


# ---------------------------------------------------------------------------
# 3. Research Pipeline Tests
# ---------------------------------------------------------------------------


class _FakeResearchLLM:
    binding = "openai"
    model = "test-model"
    api_key = "test-key"
    base_url = "test-url"
    api_version = None
    extra_headers: dict = {}
    reasoning_effort = None


@pytest.fixture(autouse=True)
def _stub_llm_for_research(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "deeptutor.agents.research.pipeline.get_llm_config",
        lambda: _FakeResearchLLM(),
    )
    monkeypatch.setattr(
        "deeptutor.agents.research.pipeline.get_tool_registry",
        lambda: _FakeToolRegistry(),
    )


@pytest.mark.asyncio
async def test_research_pipeline_decompose_system_prompt() -> None:
    pipeline = ResearchPipeline(language="en", runtime_config={})
    instructions_text = "Prioritize peer-reviewed biomedical literature from 2024-2026."

    captured_prompts: list[str] = []

    async def _fake_step(**kwargs: Any) -> LabeledStepResult:
        messages = kwargs.get("messages") or []
        system_content = messages[0]["content"] if messages else ""
        captured_prompts.append(system_content)
        return LabeledStepResult(
            label="OUTLINE",
            text='[{"title": "Subtopic 1", "overview": "Overview 1"}]',
        )

    with patch.object(ResearchPipeline, "_run_labeled_step", side_effect=_fake_step):
        # 1. Baseline: empty instructions
        ctx_empty = _make_context(instructions="")
        await pipeline._decompose(
            topic="Gene therapy",
            context=ctx_empty,
            stream=_StubStreamBus(),
            client=object(),
        )
        baseline_prompt = captured_prompts[0]

        # 2. Set instructions
        ctx_with_instr = _make_context(instructions=instructions_text)
        await pipeline._decompose(
            topic="Gene therapy",
            context=ctx_with_instr,
            stream=_StubStreamBus(),
            client=object(),
        )
        instr_prompt = captured_prompts[1]

    # When empty: prompt is byte-identical to baseline prompt
    assert baseline_prompt == pipeline._t("decompose.system")
    assert instructions_text not in baseline_prompt
    assert INSTRUCTION_HEADING not in baseline_prompt

    # When set: contains instructions and heading
    assert instructions_text in instr_prompt
    assert INSTRUCTION_HEADING in instr_prompt


@pytest.mark.asyncio
async def test_research_pipeline_report_system_prompt() -> None:
    pipeline = ResearchPipeline(language="en", runtime_config={})
    instructions_text = "Write in the voice of a senior research advisor. Keep conclusions actionable."
    outline = ReportOutline(title="Research Summary", sections=())

    captured_prompts: list[str] = []
    report_intro_text = (
        "## 1. Introduction\n\n"
        "This report provides an in-depth analysis of AI ethics and moral philosophy across modern systems. "
        "We investigate key technical, legal, and ethical frameworks governing autonomous decision making."
    )

    async def _fake_step(**kwargs: Any) -> LabeledStepResult:
        messages = kwargs.get("messages") or []
        system_content = messages[0]["content"] if messages else ""
        captured_prompts.append(system_content)
        return LabeledStepResult(
            label="REPORT_INTRO",
            text=report_intro_text,
        )

    with patch.object(ResearchPipeline, "_run_labeled_step", side_effect=_fake_step):
        # 1. Baseline: empty instructions
        ctx_empty = _make_context(instructions="")
        await pipeline._write_intro(
            context=ctx_empty,
            topic="AI Ethics",
            outline=outline,
            stream=_StubStreamBus(),
            client=object(),
        )
        baseline_prompt = captured_prompts[0]

        # 2. Set instructions
        ctx_with_instr = _make_context(instructions=instructions_text)
        await pipeline._write_intro(
            context=ctx_with_instr,
            topic="AI Ethics",
            outline=outline,
            stream=_StubStreamBus(),
            client=object(),
        )
        instr_prompt = captured_prompts[1]

    # When empty: prompt is byte-identical to baseline prompt
    assert baseline_prompt == pipeline._t("report.intro.system", section_number=1)
    assert instructions_text not in baseline_prompt
    assert INSTRUCTION_HEADING not in baseline_prompt

    # When set: contains instructions and heading
    assert instructions_text in instr_prompt
    assert INSTRUCTION_HEADING in instr_prompt
