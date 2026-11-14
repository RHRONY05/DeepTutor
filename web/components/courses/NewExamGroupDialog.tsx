"use client";

// Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.

import { useState } from "react";
import { Dialog } from "@/shared/ui/Dialog";
import { Button } from "@/shared/ui/Button";
import { InlineAlert } from "@/shared/ui/InlineAlert";
import {
  createGroup,
  type ExamGroup,
  type ExamType,
} from "@/lib/courses-api";

interface NewExamGroupDialogProps {
  open: boolean;
  workspaceId: string;
  onClose: () => void;
  onCreated: (group: ExamGroup) => void;
}

const EXAM_TYPES: { value: ExamType; label: string }[] = [
  { value: "class_test", label: "Class Test (CT)" },
  { value: "quiz", label: "Quiz" },
  { value: "viva", label: "Viva" },
  { value: "mid_term", label: "Mid-Term Exam" },
  { value: "term_final", label: "Term Final" },
  { value: "assignment", label: "Assignment" },
  { value: "other", label: "Other / General Exam" },
];

export function NewExamGroupDialog({
  open,
  workspaceId,
  onClose,
  onCreated,
}: NewExamGroupDialogProps) {
  const [name, setName] = useState("");
  const [type, setType] = useState<ExamType>("class_test");
  const [date, setDate] = useState("");
  const [syllabus, setSyllabus] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Please enter a name for the exam group (e.g. CT-01).");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const created = await createGroup(workspaceId, {
        name: name.trim(),
        type,
        date: date || undefined,
        syllabus: syllabus.trim(),
      });
      setName("");
      setType("class_test");
      setDate("");
      setSyllabus("");
      onCreated(created);
      onClose();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to create exam group. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New Exam Group"
      description="Create a syllabus and file bucket for an upcoming test, viva or exam."
      size="md"
      busy={busy}
      footer={
        <div className="flex w-full items-center justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={handleSubmit}
            loading={busy}
          >
            Create exam group
          </Button>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 py-2">
        {error && <InlineAlert tone="danger">{error}</InlineAlert>}

        <div>
          <label className="mb-1 block text-xs font-semibold text-[var(--foreground)]">
            Exam Name <span className="text-rose-500">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. CT-02, Mid-Term, Quiz-1"
            required
            autoFocus
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          />
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold text-[var(--foreground)]">
              Exam Type
            </label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as ExamType)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
            >
              {EXAM_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold text-[var(--foreground)]">
              Exam Date (optional)
            </label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-semibold text-[var(--foreground)]">
            Syllabus / Scope (optional Markdown)
          </label>
          <textarea
            value={syllabus}
            onChange={(e) => setSyllabus(e.target.value)}
            rows={4}
            placeholder="Enter the syllabus topics or scope for this exam..."
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-sm text-[var(--foreground)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          />
        </div>
      </form>
    </Dialog>
  );
}

export default NewExamGroupDialog;
