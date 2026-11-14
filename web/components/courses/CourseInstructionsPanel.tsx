"use client";

// Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  BookOpen,
  Check,
  Copy,
  ExternalLink,
  FileCode,
  FileText,
  GraduationCap,
  Info,
  Loader2,
  Save,
  Sparkles,
  User,
} from "lucide-react";
import { Button } from "@/shared/ui/Button";
import { InlineAlert } from "@/shared/ui/InlineAlert";
import {
  getCourseInstructions,
  putCourseSettings,
  type CourseInstructions,
} from "@/lib/courses-api";
import {
  getPersona,
  listPersonas,
  updatePersona,
  type PersonaDetail,
  type PersonaInfo,
} from "@/lib/personas-api";
import {
  createSkill,
  getSkill,
  updateSkill,
  type SkillDetail,
} from "@/lib/skills-api";
import { saveWorkspace } from "@/lib/workspaces-api";

interface CourseInstructionsPanelProps {
  workspaceId: string;
}

export function CourseInstructionsPanel({
  workspaceId,
}: CourseInstructionsPanelProps) {
  // Main instructions data state
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [instructionsData, setInstructionsData] =
    useState<CourseInstructions | null>(null);

  // Card A: Persona State
  const [personas, setPersonas] = useState<PersonaInfo[]>([]);
  const [selectedPersona, setSelectedPersona] = useState<string>("");
  const [savedDefaultPersona, setSavedDefaultPersona] = useState<string>("");
  const [personaDetail, setPersonaDetail] = useState<PersonaDetail | null>(null);
  const [personaContent, setPersonaContent] = useState<string>("");
  const [loadingPersonaDetail, setLoadingPersonaDetail] = useState(false);
  const [savingDefaultPersona, setSavingDefaultPersona] = useState(false);
  const [savingPersonaContent, setSavingPersonaContent] = useState(false);
  const [personaSuccessMsg, setPersonaSuccessMsg] = useState<string | null>(null);
  const [personaErrorMsg, setPersonaErrorMsg] = useState<string | null>(null);

  // Card B: Course Instructions State
  const [workspaceInstructions, setWorkspaceInstructions] = useState<string>("");
  const [savingInstructions, setSavingInstructions] = useState(false);
  const [instructionsSuccessMsg, setInstructionsSuccessMsg] =
    useState<string | null>(null);
  const [instructionsErrorMsg, setInstructionsErrorMsg] = useState<string | null>(
    null,
  );

  // Card C: Exam-prep Skill State
  const [skillDetail, setSkillDetail] = useState<SkillDetail | null>(null);
  const [skillContent, setSkillContent] = useState<string>("");
  const [loadingSkill, setLoadingSkill] = useState(false);
  const [copyingSkill, setCopyingSkill] = useState(false);
  const [savingSkill, setSavingSkill] = useState(false);
  const [skillSuccessMsg, setSkillSuccessMsg] = useState<string | null>(null);
  const [skillErrorMsg, setSkillErrorMsg] = useState<string | null>(null);

  // Load Persona detail when selectedPersona changes
  const loadPersonaDetail = useCallback(async (personaName: string) => {
    if (!personaName) {
      setPersonaDetail(null);
      setPersonaContent("");
      return;
    }
    setLoadingPersonaDetail(true);
    setPersonaErrorMsg(null);
    try {
      const detail = await getPersona(personaName);
      setPersonaDetail(detail);
      setPersonaContent(detail.content);
    } catch (err) {
      setPersonaErrorMsg(
        err instanceof Error ? err.message : "Failed to load persona details.",
      );
    } finally {
      setLoadingPersonaDetail(false);
    }
  }, []);

  // Load Exam-prep skill
  const loadExamPrepSkill = useCallback(async () => {
    setLoadingSkill(true);
    setSkillErrorMsg(null);
    try {
      const skill = await getSkill("exam-prep");
      setSkillDetail(skill);
      setSkillContent(skill.content);
    } catch (err) {
      setSkillErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to load exam-prep skill content.",
      );
    } finally {
      setLoadingSkill(false);
    }
  }, []);

  // Initial data fetch
  const fetchAllData = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    setLoadError(null);
    try {
      const [instr, personasList] = await Promise.all([
        getCourseInstructions(workspaceId),
        listPersonas(),
      ]);
      setInstructionsData(instr);
      setPersonas(personasList);
      setWorkspaceInstructions(instr.workspace_instructions || "");
      setSelectedPersona(instr.default_persona || "");
      setSavedDefaultPersona(instr.default_persona || "");

      if (instr.default_persona) {
        void loadPersonaDetail(instr.default_persona);
      }
      void loadExamPrepSkill();
    } catch (err) {
      setLoadError(
        err instanceof Error
          ? err.message
          : "Failed to load course instructions and settings.",
      );
    } finally {
      setLoading(false);
    }
  }, [workspaceId, loadPersonaDetail, loadExamPrepSkill]);

  useEffect(() => {
    void fetchAllData();
  }, [fetchAllData]);

  // Card A: Handler - Change selected persona
  const handleSelectPersona = (name: string) => {
    setSelectedPersona(name);
    setPersonaSuccessMsg(null);
    setPersonaErrorMsg(null);
    void loadPersonaDetail(name);
  };

  // Card A: Handler - Save default persona
  const handleSaveDefaultPersona = async () => {
    setSavingDefaultPersona(true);
    setPersonaSuccessMsg(null);
    setPersonaErrorMsg(null);
    try {
      const updated = await putCourseSettings(workspaceId, {
        default_persona: selectedPersona,
      });
      setSavedDefaultPersona(updated.default_persona);
      setPersonaSuccessMsg(
        updated.default_persona
          ? `Default persona set to "${updated.default_persona}".`
          : "Default persona cleared (using DeepTutor default).",
      );
    } catch (err) {
      setPersonaErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to save default persona setting.",
      );
    } finally {
      setSavingDefaultPersona(false);
    }
  };

  // Card A: Handler - Save persona content
  const handleSavePersonaContent = async () => {
    if (!selectedPersona) return;
    setSavingPersonaContent(true);
    setPersonaSuccessMsg(null);
    setPersonaErrorMsg(null);
    try {
      await updatePersona(selectedPersona, {
        content: personaContent,
        description: personaDetail?.description,
      });
      setPersonaSuccessMsg(`Updated content for persona "${selectedPersona}".`);
    } catch (err) {
      setPersonaErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to update persona content.",
      );
    } finally {
      setSavingPersonaContent(false);
    }
  };

  // Card B: Handler - Insert exam-prep defaults
  const handleInsertExamPrepDefaults = () => {
    const template = instructionsData?.exam_prep_template || "";
    if (!template) return;
    const maxChars = instructionsData?.max_instructions_chars || 10000;
    const combined = workspaceInstructions.trim()
      ? `${workspaceInstructions.trim()}\n\n${template}`
      : template;

    if (combined.length > maxChars) {
      const proceed = window.confirm(
        `Inserting exam-prep defaults will exceed the maximum instruction limit (${maxChars} characters). It will be ${combined.length} characters. Proceed anyway?`,
      );
      if (!proceed) return;
    }
    setWorkspaceInstructions(combined);
    setInstructionsSuccessMsg("Inserted exam-prep template into instructions.");
  };

  // Card B: Handler - Save workspace instructions
  const handleSaveWorkspaceInstructions = async () => {
    setSavingInstructions(true);
    setInstructionsSuccessMsg(null);
    setInstructionsErrorMsg(null);
    try {
      await saveWorkspace(
        { instructions: workspaceInstructions },
        workspaceId,
      );
      setInstructionsSuccessMsg("Course workspace instructions saved.");
    } catch (err) {
      setInstructionsErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to save workspace instructions.",
      );
    } finally {
      setSavingInstructions(false);
    }
  };

  // Card C: Handler - Make editable copy of exam-prep skill
  const handleMakeEditableCopy = async () => {
    if (!skillDetail) return;
    setCopyingSkill(true);
    setSkillSuccessMsg(null);
    setSkillErrorMsg(null);
    try {
      await createSkill({
        name: skillDetail.name,
        description: skillDetail.description,
        content: skillContent,
        tags: skillDetail.tags,
      });
      // Reload skill to get the user-scoped copy
      await loadExamPrepSkill();
      setSkillSuccessMsg(
        "Created user copy of exam-prep skill. It now shadows the built-in skill and is editable.",
      );
    } catch (err) {
      setSkillErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to create editable skill copy.",
      );
    } finally {
      setCopyingSkill(false);
    }
  };

  // Card C: Handler - Save exam-prep skill
  const handleSaveSkill = async () => {
    if (!skillDetail) return;
    setSavingSkill(true);
    setSkillSuccessMsg(null);
    setSkillErrorMsg(null);
    try {
      await updateSkill(skillDetail.name, {
        content: skillContent,
        description: skillDetail.description,
        tags: skillDetail.tags,
      });
      setSkillSuccessMsg("Exam-prep skill content saved.");
    } catch (err) {
      setSkillErrorMsg(
        err instanceof Error ? err.message : "Failed to update skill content.",
      );
    } finally {
      setSavingSkill(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center text-sm text-[var(--muted-foreground)]">
        <Loader2 size={22} className="mr-2 animate-spin text-[var(--primary)]" />
        Loading course instructions and personas...
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-6">
        <InlineAlert tone="danger">{loadError}</InlineAlert>
      </div>
    );
  }

  const maxChars = instructionsData?.max_instructions_chars || 10000;
  const isDefaultPersonaDirty = selectedPersona !== savedDefaultPersona;
  const isPersonaReadOnly = Boolean(personaDetail?.read_only);
  const isSkillReadOnly = skillDetail?.source === "builtin" || Boolean(skillDetail?.read_only);

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
      {/* ─────────────────────────────────────────────────────────────
          CARD A: Persona
      ───────────────────────────────────────────────────────────── */}
      <div className="flex flex-col justify-between rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm">
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-[var(--border)]/70 pb-3">
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--muted)] text-[var(--primary)]">
                <User size={16} />
              </span>
              <div>
                <h3 className="text-sm font-semibold text-[var(--foreground)]">
                  Default Persona
                </h3>
                <p className="text-[11px] text-[var(--muted-foreground)]">
                  Voice and pedagogical character for this course
                </p>
              </div>
            </div>
            <Link
              href="/space/personas"
              className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--primary)] hover:underline"
            >
              Manage personas
              <ExternalLink size={11} />
            </Link>
          </div>

          {personaSuccessMsg && (
            <InlineAlert tone="success">{personaSuccessMsg}</InlineAlert>
          )}
          {personaErrorMsg && (
            <InlineAlert tone="danger">{personaErrorMsg}</InlineAlert>
          )}

          {/* Persona Selector Row */}
          <div className="space-y-1.5">
            <label
              htmlFor="course-default-persona-select"
              className="block text-xs font-medium text-[var(--foreground)]"
            >
              Course Default Persona
            </label>
            <div className="flex gap-2">
              <select
                id="course-default-persona-select"
                value={selectedPersona}
                onChange={(e) => handleSelectPersona(e.target.value)}
                className="flex-1 rounded-xl border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-xs text-[var(--foreground)] focus:border-[var(--ring)] focus:outline-none focus:ring-1 focus:ring-[var(--ring)]"
              >
                <option value="">None (DeepTutor default)</option>
                {personas.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                    {p.description ? ` — ${p.description}` : ""}
                    {p.read_only ? " (built-in)" : ""}
                  </option>
                ))}
              </select>

              <Button
                type="button"
                variant={isDefaultPersonaDirty ? "primary" : "secondary"}
                size="sm"
                loading={savingDefaultPersona}
                disabled={!isDefaultPersonaDirty || savingDefaultPersona}
                onClick={handleSaveDefaultPersona}
                icon={
                  !savingDefaultPersona && !isDefaultPersonaDirty ? (
                    <Check size={13} className="text-emerald-500" />
                  ) : (
                    <Save size={13} />
                  )
                }
                className="shrink-0 text-xs"
              >
                {isDefaultPersonaDirty ? "Set default" : "Default set"}
              </Button>
            </div>
            <p className="text-[11px] leading-relaxed text-[var(--muted-foreground)]">
              {savedDefaultPersona ? (
                <span>
                  Currently active default:{" "}
                  <strong className="text-[var(--foreground)]">
                    {savedDefaultPersona}
                  </strong>
                </span>
              ) : (
                "No default persona set. New chats use the default tutor voice."
              )}
            </p>
          </div>

          {/* Persona Content Textarea */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label
                htmlFor="selected-persona-content"
                className="block text-xs font-medium text-[var(--foreground)]"
              >
                Persona Definition (PERSONA.md)
              </label>
              {isPersonaReadOnly && selectedPersona && (
                <span className="rounded-md bg-[var(--muted)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--muted-foreground)]">
                  Read-only
                </span>
              )}
            </div>

            {loadingPersonaDetail ? (
              <div className="flex h-36 items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--muted)]/20 text-xs text-[var(--muted-foreground)]">
                <Loader2 size={16} className="mr-2 animate-spin" />
                Loading persona...
              </div>
            ) : selectedPersona ? (
              <textarea
                id="selected-persona-content"
                rows={9}
                value={personaContent}
                readOnly={isPersonaReadOnly}
                onChange={(e) => setPersonaContent(e.target.value)}
                placeholder="Persona system prompt instructions..."
                className={`w-full resize-y rounded-xl border border-[var(--border)] bg-[var(--background)] p-3 font-mono text-xs leading-relaxed text-[var(--foreground)] focus:border-[var(--ring)] focus:outline-none focus:ring-1 focus:ring-[var(--ring)] ${
                  isPersonaReadOnly ? "cursor-not-allowed opacity-75" : ""
                }`}
              />
            ) : (
              <div className="flex h-36 flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] p-4 text-center text-xs text-[var(--muted-foreground)]">
                <Info size={18} className="mb-1 text-[var(--muted-foreground)]" />
                Select a persona above to inspect or edit its prompt content.
              </div>
            )}
          </div>
        </div>

        {/* Card A Footer */}
        {selectedPersona && !isPersonaReadOnly && (
          <div className="mt-4 flex justify-end border-t border-[var(--border)]/70 pt-3">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              loading={savingPersonaContent}
              disabled={savingPersonaContent}
              onClick={handleSavePersonaContent}
              icon={<Save size={13} />}
              className="text-xs"
            >
              Save persona content
            </Button>
          </div>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────
          CARD B: Course Instructions
      ───────────────────────────────────────────────────────────── */}
      <div className="flex flex-col justify-between rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm">
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-[var(--border)]/70 pb-3">
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--muted)] text-[var(--primary)]">
                <FileText size={16} />
              </span>
              <div>
                <h3 className="text-sm font-semibold text-[var(--foreground)]">
                  Course Instructions
                </h3>
                <p className="text-[11px] text-[var(--muted-foreground)]">
                  Custom instructions injected into every capability in this course
                </p>
              </div>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              icon={<Sparkles size={12} className="text-amber-500" />}
              onClick={handleInsertExamPrepDefaults}
              className="text-[11px] text-[var(--primary)]"
              title="Append exam-prep instructions template"
            >
              Insert exam-prep defaults
            </Button>
          </div>

          {instructionsSuccessMsg && (
            <InlineAlert tone="success">{instructionsSuccessMsg}</InlineAlert>
          )}
          {instructionsErrorMsg && (
            <InlineAlert tone="danger">{instructionsErrorMsg}</InlineAlert>
          )}

          <div className="space-y-1.5">
            <label
              htmlFor="workspace-instructions-textarea"
              className="block text-xs font-medium text-[var(--foreground)]"
            >
              Workspace Prompt Instructions
            </label>
            <textarea
              id="workspace-instructions-textarea"
              rows={12}
              value={workspaceInstructions}
              onChange={(e) => setWorkspaceInstructions(e.target.value)}
              placeholder="e.g. Always emphasize proof methods and derive equations from first principles..."
              className="w-full resize-y rounded-xl border border-[var(--border)] bg-[var(--background)] p-3 font-mono text-xs leading-relaxed text-[var(--foreground)] focus:border-[var(--ring)] focus:outline-none focus:ring-1 focus:ring-[var(--ring)]"
            />
            <div className="flex items-center justify-between text-[11px] text-[var(--muted-foreground)]">
              <span>Applied to Chat, Questions, Solve &amp; Research</span>
              <span
                className={
                  workspaceInstructions.length > maxChars
                    ? "font-semibold text-rose-500"
                    : ""
                }
              >
                {workspaceInstructions.length} / {maxChars} characters
              </span>
            </div>
          </div>
        </div>

        {/* Card B Footer */}
        <div className="mt-4 flex justify-end border-t border-[var(--border)]/70 pt-3">
          <Button
            type="button"
            variant="primary"
            size="sm"
            loading={savingInstructions}
            disabled={savingInstructions}
            onClick={handleSaveWorkspaceInstructions}
            icon={<Save size={13} />}
            className="text-xs"
          >
            Save course instructions
          </Button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          CARD C: Exam-prep Skill
      ───────────────────────────────────────────────────────────── */}
      <div className="flex flex-col justify-between rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm">
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-[var(--border)]/70 pb-3">
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--muted)] text-[var(--primary)]">
                <GraduationCap size={16} />
              </span>
              <div>
                <h3 className="text-sm font-semibold text-[var(--foreground)]">
                  Exam-Prep Skill
                </h3>
                <p className="text-[11px] text-[var(--muted-foreground)]">
                  Playbook triggered by exam prep prompts (&quot;I have CT-01 tomorrow&quot;)
                </p>
              </div>
            </div>
            <span
              className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
                isSkillReadOnly
                  ? "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
                  : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
              }`}
            >
              {isSkillReadOnly ? "Built-in" : "User copy"}
            </span>
          </div>

          {skillSuccessMsg && (
            <InlineAlert tone="success">{skillSuccessMsg}</InlineAlert>
          )}
          {skillErrorMsg && (
            <InlineAlert tone="danger">{skillErrorMsg}</InlineAlert>
          )}

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label
                htmlFor="exam-prep-skill-content"
                className="block text-xs font-medium text-[var(--foreground)]"
              >
                SKILL.md Definition
              </label>
              {isSkillReadOnly && (
                <span className="text-[11px] text-[var(--muted-foreground)]">
                  Read-only (built-in)
                </span>
              )}
            </div>

            {loadingSkill ? (
              <div className="flex h-36 items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--muted)]/20 text-xs text-[var(--muted-foreground)]">
                <Loader2 size={16} className="mr-2 animate-spin" />
                Loading exam-prep skill...
              </div>
            ) : (
              <textarea
                id="exam-prep-skill-content"
                rows={12}
                value={skillContent}
                readOnly={isSkillReadOnly}
                onChange={(e) => setSkillContent(e.target.value)}
                placeholder="Skill playbook markdown..."
                className={`w-full resize-y rounded-xl border border-[var(--border)] bg-[var(--background)] p-3 font-mono text-xs leading-relaxed text-[var(--foreground)] focus:border-[var(--ring)] focus:outline-none focus:ring-1 focus:ring-[var(--ring)] ${
                  isSkillReadOnly ? "cursor-not-allowed opacity-80" : ""
                }`}
              />
            )}
            <p className="text-[11px] leading-relaxed text-[var(--muted-foreground)]">
              {isSkillReadOnly
                ? "This is DeepTutor's built-in exam prep playbook. Make a user copy to customize its teaching flow."
                : "This is your customized user copy of the exam-prep skill. It overrides the built-in playbook."}
            </p>
          </div>
        </div>

        {/* Card C Footer */}
        <div className="mt-4 flex justify-end border-t border-[var(--border)]/70 pt-3">
          {isSkillReadOnly ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              loading={copyingSkill}
              disabled={copyingSkill || loadingSkill}
              onClick={handleMakeEditableCopy}
              icon={<Copy size={13} />}
              className="text-xs"
            >
              Make an editable copy
            </Button>
          ) : (
            <Button
              type="button"
              variant="primary"
              size="sm"
              loading={savingSkill}
              disabled={savingSkill || loadingSkill}
              onClick={handleSaveSkill}
              icon={<Save size={13} />}
              className="text-xs"
            >
              Save skill
            </Button>
          )}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          CARD D: Built-in Base Prompt
      ───────────────────────────────────────────────────────────── */}
      <div className="flex flex-col justify-between rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm">
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-[var(--border)]/70 pb-3">
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--muted)] text-[var(--muted-foreground)]">
                <FileCode size={16} />
              </span>
              <div>
                <h3 className="text-sm font-semibold text-[var(--foreground)]">
                  Built-in Base Prompt
                </h3>
                <p className="text-[11px] text-[var(--muted-foreground)]">
                  Core agentic chat system prompt
                </p>
              </div>
            </div>
            <span className="rounded-md bg-[var(--muted)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--muted-foreground)]">
              Read-only
            </span>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs text-[var(--muted-foreground)]">
              <span>agentic_chat.yaml &bull; general</span>
            </div>
            <pre className="max-h-72 overflow-y-auto whitespace-pre-wrap select-text rounded-xl border border-[var(--border)] bg-[var(--muted)]/40 p-3 font-mono text-xs leading-relaxed text-[var(--foreground)]">
              {instructionsData?.base_prompt ||
                "You are DeepTutor, an interactive tutor and learning companion."}
            </pre>
            <p className="flex items-center gap-1.5 text-[11px] text-[var(--muted-foreground)]">
              <Info size={12} className="shrink-0" />
              Built into DeepTutor; always applied first.
            </p>
          </div>
        </div>

        <div className="mt-4 border-t border-[var(--border)]/70 pt-3 text-right">
          <span className="text-[11px] italic text-[var(--muted-foreground)]">
            Static reference
          </span>
        </div>
      </div>
    </div>
  );
}
