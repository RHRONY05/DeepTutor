// Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.

import type { ExamType } from "@/lib/courses-api";

interface ExamTypeBadgeProps {
  type: ExamType | string;
  className?: string;
}

const TYPE_CONFIG: Record<
  string,
  { label: string; bg: string; text: string; border: string }
> = {
  class_test: {
    label: "Class Test",
    bg: "bg-blue-500/10",
    text: "text-blue-700 dark:text-blue-300",
    border: "border-blue-500/20",
  },
  quiz: {
    label: "Quiz",
    bg: "bg-purple-500/10",
    text: "text-purple-700 dark:text-purple-300",
    border: "border-purple-500/20",
  },
  viva: {
    label: "Viva",
    bg: "bg-amber-500/10",
    text: "text-amber-700 dark:text-amber-300",
    border: "border-amber-500/20",
  },
  mid_term: {
    label: "Mid-Term",
    bg: "bg-indigo-500/10",
    text: "text-indigo-700 dark:text-indigo-300",
    border: "border-indigo-500/20",
  },
  term_final: {
    label: "Term Final",
    bg: "bg-rose-500/10",
    text: "text-rose-700 dark:text-rose-300",
    border: "border-rose-500/20",
  },
  assignment: {
    label: "Assignment",
    bg: "bg-emerald-500/10",
    text: "text-emerald-700 dark:text-emerald-300",
    border: "border-emerald-500/20",
  },
  practice: {
    label: "Practice",
    bg: "bg-teal-500/10",
    text: "text-teal-700 dark:text-teal-300",
    border: "border-teal-500/20",
  },
  other: {
    label: "Exam",
    bg: "bg-zinc-500/10",
    text: "text-zinc-700 dark:text-zinc-300",
    border: "border-zinc-500/20",
  },
};

export function ExamTypeBadge({ type, className = "" }: ExamTypeBadgeProps) {
  const conf = TYPE_CONFIG[type] ?? {
    label: type || "Exam",
    bg: "bg-zinc-500/10",
    text: "text-zinc-700 dark:text-zinc-300",
    border: "border-zinc-500/20",
  };

  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium leading-none ${conf.bg} ${conf.text} ${conf.border} ${className}`}
    >
      {conf.label}
    </span>
  );
}

export default ExamTypeBadge;
